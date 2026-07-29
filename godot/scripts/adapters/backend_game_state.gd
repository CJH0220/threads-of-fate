extends RefCounted
class_name BackendGameState

## 后端游戏状态适配器（替换 MockGameState 的后端实现）。
## 实现与 MockGameState 完全相同的 API 接口，前端 UI 代码无需修改即可切换。
## 职责：
##   - 调用 BackendClient HTTP / WebSocket 接口
##   - 转换后端数据契约为前端内部格式
##   - 维护本地状态缓存（减少重复请求）
##   - 事件历史记录（同 Mock 逻辑）

signal state_changed
## 单个 NPC 动态字段变化时发射（细粒度刷新用）。
signal npc_updated(npc_id: String)
## 事件演出完成并锁定时发射。
signal event_completed(event_id: String, snapshot: Dictionary)

## 托梦消耗（对齐总策划案 §10.2）
const DREAM_COST := 3

## 静态数据文件（与 Mock 共用同一份 JSON，保证内容一致）。
## 后端目前只推送动态位置/情绪，静态描述/日程/结局文案等仍来自本地静态资源。
const LOCATIONS_PATH := "res://data/mock/locations.json"
const CHARACTERS_PATH := "res://data/mock/characters.json"
const EVENTS_PATH := "res://data/mock/events.json"
const INTERVENTIONS_PATH := "res://data/mock/interventions.json"

## 静态地点数据（display_name / description / core_npc_ids / primary_time_slots 等）
var _static_locations: Array = []
## 静态角色数据（description / schedule / bond_summaries 等，backend 无法提供的富字段）
var _static_characters: Array = []
## 静态角色 id -> dict 查表
var _static_character_index: Dictionary = {}
## 静态干预列表（intervention_id -> display_name / cost 等）
var _static_interventions: Array = []

## 本地状态缓存（来自 /state 或 settlement_complete 推送）
var _state_cache: Dictionary = {}

## NPC 列表缓存
var _characters: Array = []

## 地点列表缓存（从后端 npc.location 或静态配置派生）
var _locations: Array = []

## 当前时段触发的事件列表
var _events: Array = []

## 干预选项缓存
var _interventions: Array = []

## 事件历史（同 Mock 记录逻辑）
var event_history: Array = []

## 当前时段等待结算的事件队列
var _pending_events: Array = []

## 时间推进结果缓存（供 UI 同步读取）
var _last_advance_result: Dictionary = {}

## 已应用干预的事件锁定表：event_id -> {intervention_id, display_name}
var _applied_interventions: Dictionary = {}

## 当天是否已托梦过（每次切到 Morning / new_day 时重置）
var dream_used_today: bool = false
## 已演出完成的事件集合：event_id -> true
var _completed_events: Dictionary = {}
## 事件演出快照：event_id -> {finished_at, blessings, summary}
var _event_snapshots: Dictionary = {}
## 当前时段内的逐条资源变化日志（每次干预/赐福/托梦追加一条）。
var _resource_change_log: Array = []
## advance_time() 等待 settlement_complete 的标志位。由 _on_settlement_complete 置 true。
var _settlement_arrived: bool = false

func _init() -> void:
	## 连接 Backend 信号
	Backend.new_game_completed.connect(_on_new_game)
	Backend.state_completed.connect(_on_state_updated)
	Backend.time_advanced.connect(_on_time_advanced)
	Backend.event_triggered.connect(_on_event_triggered)
	Backend.settlement_complete.connect(_on_settlement_complete)
	Backend.save_completed.connect(_on_save_completed)
	Backend.load_completed.connect(_on_load_completed)
	Backend.npc_response.connect(_on_npc_response)
	## 打印后端 Agent 交互进度到 Godot output（不改状态，仅可视化）
	Backend.npc_actions_start.connect(_on_npc_actions_start)
	Backend.npc_action.connect(_on_npc_action_log)
	Backend.narrator_beat.connect(_on_narrator_beat_log)
	## 加载与 Mock 共用的静态数据（描述、日程、干预定义等 backend 不推送的字段）
	_load_static_data()
	## 初始化缓存
	_pending_events.clear()
	_last_advance_result.clear()
	_applied_interventions.clear()
	dream_used_today = false
	_completed_events.clear()
	_event_snapshots.clear()
	_resource_change_log.clear()

## 加载静态 JSON（locations/characters/events/interventions），backend 模式复用 Mock 内容。
func _load_static_data() -> void:
	_static_locations = _load_json_array(LOCATIONS_PATH)
	_static_characters = _load_json_array(CHARACTERS_PATH)
	_static_interventions = _load_json_array(INTERVENTIONS_PATH)
	_static_character_index.clear()
	for c in _static_characters:
		var cid: String = String(c.get("npc_id", ""))
		if cid != "":
			_static_character_index[cid] = c

func _load_json_array(path: String) -> Array:
	if not FileAccess.file_exists(path):
		push_warning("[BackendGameState] 静态文件缺失: %s" % path)
		return []
	var file := FileAccess.open(path, FileAccess.READ)
	var text := file.get_as_text()
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_ARRAY:
		push_warning("[BackendGameState] 静态文件解析失败: %s" % path)
		return []
	return parsed as Array

## 保存游戏到指定槽位。
func save_game(slot: int = 1) -> void:
	Backend.send_save(slot)

## 从指定槽位加载游戏。
func load_game(slot: int = 1) -> void:
	Backend.send_load(slot)

func _on_save_completed(data: Dictionary) -> void:
	## 保存成功，可以弹出提示
	print("游戏已保存: 槽位 %d" % int(data.get("slot", 1)))

func _on_load_completed(data: Dictionary) -> void:
	## 加载成功，刷新全部状态
	_state_cache = _normalize_state(data)
	_characters = _normalize_npcs(data.get("npcs", []))
	_locations.clear()
	_events.clear()
	event_history.clear()
	_pending_events.clear()
	_applied_interventions.clear()
	dream_used_today = false
	_completed_events.clear()
	_event_snapshots.clear()
	_resource_change_log.clear()
	state_changed.emit()

## NPC 对话响应（暂存，供 UI 读取）。
var _last_npc_response: Dictionary = {}

func _on_npc_response(data: Dictionary) -> void:
	_last_npc_response = data
	## 可添加信号通知 UI 对话已响应

## 打印后端 Agent 交互到 Godot output，便于调试 LLM 决策链。
func _on_npc_actions_start(_data: Dictionary) -> void:
	print("[Agent] === NPC 开始并发思考 ===")

func _on_npc_action_log(data: Dictionary) -> void:
	var name := String(data.get("npc_name", data.get("npc_id", "?")))
	var action := String(data.get("action", ""))
	print("[Agent] %s → %s" % [name, action])

func _on_narrator_beat_log(data: Dictionary) -> void:
	var day := int(data.get("day", 0))
	var slot := String(data.get("slot", ""))
	var text := String(data.get("text", ""))
	print("[Narrator] Day%d %s: %s" % [day, slot, text])

func reset_to_new_game() -> void:
	## 通过后端创建新局
	event_history.clear()
	_applied_interventions.clear()
	Backend.new_game()

func _on_new_game(state: Dictionary) -> void:
	if Backend.use_mock_fallback:
		## Mock 降级：创建初始状态占位
		_state_cache = {
			"day": 1,
			"time_slot": "Morning",
			"time_slot_label": "早上",
			"incense": 100,
			"divine_power": 10,
			"divine_power_max": 10,
			"yin_de": 0,
			"yang_de": 0,
		}
		_characters = _get_mock_characters()
	else:
		## 从后端响应填充
		_state_cache = _normalize_state(state)
		_characters = _normalize_npcs(state.get("npcs", []))
	## 重置所有缓存
	_pending_events.clear()
	_locations.clear()
	_events.clear()
	event_history.clear()
	_last_advance_result.clear()
	_applied_interventions.clear()
	dream_used_today = false
	_completed_events.clear()
	_event_snapshots.clear()
	_resource_change_log.clear()
	## Mock 降级：初始化事件列表（匹配 Day1 Morning 的事件）
	if Backend.use_mock_fallback:
		_populate_initial_events()
	state_changed.emit()

func _on_state_updated(state: Dictionary) -> void:
	_state_cache = _normalize_state(state)
	_characters = _normalize_npcs(state.get("npcs", []))
	state_changed.emit()

## 规范化后端状态字段名与枚举值。
func _normalize_state(raw: Dictionary) -> Dictionary:
	var result = raw.duplicate()
	## 时段命名对齐：后端 morning/noon/night -> 前端 Morning/Afternoon/Night
	var slot = String(raw.get("slot", "morning"))
	if slot == "noon":
		result["time_slot"] = "Afternoon"
	elif slot == "night":
		result["time_slot"] = "Night"
	else:
		result["time_slot"] = "Morning"
	## 神力字段名对齐
	if result.has("divine_power") and not result.has("divine_power_max"):
		result["divine_power_max"] = 10
	## 确保 day 存在
	if not result.has("day"):
		result["day"] = raw.get("day", 1)
	return result

## 规范化 NPC 列表。
func _normalize_npcs(raw_list: Array) -> Array:
	var result: Array = []
	for raw in raw_list:
		var npc = raw.duplicate()
		## 后端 NpcSnapshot: {static: NpcStatic, dynamic: NpcDynamic}
		## 注意：static 是 GDScript 4 保留字，用 npc_static 命名。
		var npc_static = npc.get("static", {}) as Dictionary
		var dynamic = npc.get("dynamic", {}) as Dictionary
		## 扁平化供前端 UI 消费
		var npc_id: String = String(npc_static.get("id", ""))
		npc["npc_id"] = npc_id
		npc["display_name"] = npc_static.get("name", "")  # 与 mock 字段对齐
		npc["name"] = npc_static.get("name", "")
		npc["occupation"] = npc_static.get("occupation", "")
		npc["tier"] = npc_static.get("tier", "C")
		npc["age"] = npc_static.get("age", 30)
		npc["background"] = npc_static.get("background", "")
		npc["core_wish"] = npc_static.get("core_wish", "")
		npc["personality"] = npc_static.get("personality", {})
		npc["attributes"] = npc_static.get("attributes", {})
		var loc_id: String = String(dynamic.get("location", "plaza"))
		npc["location"] = loc_id
		npc["current_location_id"] = loc_id
		npc["current_location_label"] = _location_label(loc_id)
		npc["happiness"] = dynamic.get("happiness", 50)
		npc["energy"] = dynamic.get("energy", 100)
		npc["emotion"] = dynamic.get("emotion", "neutral")
		npc["current_goal"] = dynamic.get("current_goal", "")
		npc["karma_main_progress"] = dynamic.get("karma_main_progress", 0.0)
		npc["karma_side_progress"] = dynamic.get("karma_side_progress", {})
		## 合并静态角色富字段（description / schedule / bond_summaries / karma_summary / risk_level 等）
		var static_data: Dictionary = _static_character_index.get(npc_id, {}) as Dictionary
		if not static_data.is_empty():
			for key in ["description", "schedule", "bond_summaries", "karma_summary", "karma_progress",
					"risk_level", "role", "age_range", "current_state", "stats", "story_priority",
					"agent_tier", "is_unlocked",
					## v1.2：身份 / 特质 / 背景钩子（策划案见 UI/ui-spec-character-panel.md §13）
					"identity_tag", "traits", "backstory_hint"]:
				if static_data.has(key) and not npc.has(key):
					npc[key] = static_data[key]
			## 兜底 display_name / occupation，避免后端字段缺失时空白
			if String(npc.get("display_name", "")) == "":
				npc["display_name"] = String(static_data.get("display_name", ""))
				npc["name"] = npc["display_name"]
			if String(npc.get("occupation", "")) == "":
				npc["occupation"] = String(static_data.get("role", ""))
		result.append(npc)
	return result

## Mock 降级时的备用 NPC 数据（合并静态富字段以便 UI 显示描述/日程）。
func _get_mock_characters() -> Array:
	if not _static_characters.is_empty():
		var result: Array = []
		for c in _static_characters:
			var npc = c.duplicate(true)
			## 兼容前端字段命名
			npc["name"] = npc.get("display_name", "")
			npc["location"] = npc.get("current_location_id", "plaza")
			npc["happiness"] = 60
			npc["energy"] = 100
			npc["emotion"] = "neutral"
			result.append(npc)
		return result
	## 静态文件缺失时的最小兜底
	return [
		{"npc_id": "lin_chaoyin", "display_name": "林潮音", "name": "林潮音", "location": "beach", "tier": "S", "age": 17, "happiness": 60},
		{"npc_id": "chen_haisheng", "display_name": "陈海生", "name": "陈海生", "location": "seafood_shop", "tier": "S", "age": 45, "happiness": 40},
		{"npc_id": "gu_chenzhou", "display_name": "顾沉舟", "name": "顾沉舟", "location": "port", "tier": "S", "age": 30, "happiness": 70},
		{"npc_id": "jiang_xueyi", "display_name": "江雪仪", "name": "江雪仪", "location": "clinic", "tier": "S", "age": 35, "happiness": 65},
	]

# ──────────────────────────────────────────
# 状态查询 API（与 MockGameState 签名一致）
# ──────────────────────────────────────────

func get_game_state() -> Dictionary:
	return _state_cache

func get_characters() -> Array:
	return _characters

func get_locations() -> Array:
	## 以静态地点为主干（包含 display_name / description / function / primary_time_slots 等富字段），
	## 叠加当前 NPC 分布（present_npc_ids / npc_count），生成 Mock 结构一致的列表。
	## NPC 位置优先取 schedule[当前时段]，缺失时回落到 npc.location / npc.current_location_id。
	_locations.clear()
	var current_slot: String = String(_state_cache.get("time_slot", "Morning"))
	## 先统计每个地点当前有哪些 NPC
	var present_by_loc: Dictionary = {}
	for npc in _characters:
		var loc_id: String = ""
		var schedule: Dictionary = npc.get("schedule", {})
		if schedule.has(current_slot):
			loc_id = String(schedule.get(current_slot, ""))
		if loc_id == "":
			loc_id = String(npc.get("current_location_id", npc.get("location", "")))
		if loc_id == "":
			continue
		if not present_by_loc.has(loc_id):
			present_by_loc[loc_id] = []
		present_by_loc[loc_id].append({
			"npc_id": String(npc.get("npc_id", "")),
			"display_name": String(npc.get("display_name", npc.get("name", ""))),
		})

	var seen: Dictionary = {}
	## 1) 静态地点：合并动态 npc 分布
	for loc in _static_locations:
		var entry: Dictionary = loc.duplicate(true)
		var loc_id: String = String(entry.get("location_id", ""))
		var present: Array = present_by_loc.get(loc_id, [])
		entry["present_npc_ids"] = present.map(func(x): return x["npc_id"])
		entry["present_npc_names"] = present.map(func(x): return x["display_name"])
		entry["npc_count"] = present.size()
		## 兼容旧 UI 字段
		entry["location_label"] = String(entry.get("display_name", loc_id))
		_locations.append(entry)
		seen[loc_id] = true

	## 2) 若 NPC 出现在静态未列出的地点，追加一个最简条目（避免 UI 丢地点）
	for loc_id in present_by_loc.keys():
		if seen.has(loc_id):
			continue
		var extra_present: Array = present_by_loc[loc_id]
		_locations.append({
			"location_id": loc_id,
			"display_name": _location_label(loc_id),
			"location_label": _location_label(loc_id),
			"description": "",
			"npc_count": extra_present.size(),
			"present_npc_ids": extra_present.map(func(x): return x["npc_id"]),
			"present_npc_names": extra_present.map(func(x): return x["display_name"]),
		})
	return _locations

func get_events() -> Array:
	## MVP：返回空列表，完整实现从后端拉取
	## 事件数据通过 settlement_complete 流式推送
	return _events

func get_event_history() -> Array:
	return event_history

func get_time_slot_label(slot_id: String) -> String:
	match slot_id:
		"Morning": return "早晨"
		"Afternoon": return "下午"
		"Night": return "夜晚"
	return slot_id

func _location_label(loc_id: String) -> String:
	## 优先从静态地点表读取（display_name），无匹配再退化到硬编码兜底。
	for loc in _static_locations:
		if String(loc.get("location_id", "")) == loc_id:
			return String(loc.get("display_name", loc_id))
	## 静态未收录的地点兜底
	match loc_id:
		"temple": return "土地庙"
		"plaza": return "广场"
		"beach": return "沙滩"
		"school": return "学校"
		"clinic": return "诊所"
		"shopping_street": return "商业街"
		"bookstore": return "书店"
		"cafe": return "咖啡馆"
		"police_station": return "警局"
		"mountain_forest": return "山林"
		"port": return "港口"
		"residence": return "住所"
		"coffee_shop": return "咖啡店"
		"wine_bar": return "酒吧"
		"seafood_shop": return "海鲜店"
	return loc_id

func find_character(npc_id: String) -> Dictionary:
	for npc in _characters:
		if String(npc.get("npc_id", "")) == npc_id:
			return npc
	## 兜底：backend 未推送但静态存在的角色（例如未加载状态）
	if _static_character_index.has(npc_id):
		return (_static_character_index[npc_id] as Dictionary).duplicate(true)
	return {}

func find_location(location_id: String) -> Dictionary:
	## 优先在合并后的动态列表里找（已经含静态富字段 + present_npc）；
	## 若 _locations 尚未构建，则回落到静态列表；再无则空字典。
	if _locations.is_empty():
		get_locations()
	for loc in _locations:
		if String(loc.get("location_id", "")) == location_id:
			return loc
	for loc in _static_locations:
		if String(loc.get("location_id", "")) == location_id:
			return (loc as Dictionary).duplicate(true)
	return {}

func get_location_label(location_id: String) -> String:
	return _location_label(location_id)

# ──────────────────────────────────────────
# 游戏操作 API
# ──────────────────────────────────────────

## 推进一个时段（通过 WebSocket），返回结算结果（与 Mock API 一致）。
## 注意：真实后端路径为异步 —— 内部 await settlement_complete 后返回。
## HUD 调用侧需使用 `await state.advance_time()`（Mock 路径 await 立即返回，无副作用）。
func advance_time() -> Dictionary:
	_events.clear()
	_pending_events.clear()
	_last_advance_result.clear()

	if Backend.use_mock_fallback:
		## Mock 降级：本地模拟时间推进
		return _mock_advance_time()

	## WebSocket 未连通时降级到本地 Mock，避免 await 永久挂起
	if not Backend.is_ws_connected():
		printerr("[BackendGameState] advance_time: WebSocket 未连接，降级到本地 Mock")
		return _mock_advance_time()

	## 发送 WebSocket 请求，等待结算完成信号后再返回结果
	Backend.send_advance_time()

	## 超时兜底：LLM 全链路（NPC思考 + 编剧编排 + 对白管线 + 日常事件对白）可能耗时较长，
	## 给 300s 冗余；到时未收到 settlement_complete 才降级到 Mock。
	var timeout_sec: float = 300.0
	_settlement_arrived = false
	var start_time: float = Time.get_ticks_msec()
	var tree: SceneTree = Engine.get_main_loop() as SceneTree
	var last_log_bucket: int = 0
	while not _settlement_arrived:
		await tree.process_frame
		# WebSocket disconnect -> immediate fallback
		if not Backend.is_ws_connected():
			printerr("[BackendGameState] advance_time: WS disconnected, fallback to Mock")
			break
		var elapsed: float = (Time.get_ticks_msec() - start_time) / 1000.0
		var bucket: int = int(elapsed / 10.0)
		if bucket != last_log_bucket:
			last_log_bucket = bucket
			print("[BackendGameState] advance_time waiting %ds..." % int(elapsed))
		if elapsed >= timeout_sec:
			break
	if not _settlement_arrived:
		printerr("[BackendGameState] advance_time: timeout/fallback after %ds" % int((Time.get_ticks_msec() - start_time) / 1000.0))
		return _mock_advance_time()
	return _last_advance_result.duplicate()

## Mock 降级模式的本地时间推进（保持前端可独立测试）。
## 对齐 MockGameState.advance_time 的事件匹配逻辑，确保第一天早上也能推进事件。
func _mock_advance_time() -> Dictionary:
	var day = int(_state_cache.get("day", 1))
	var slot = String(_state_cache.get("time_slot", "Morning"))
	var resource_delta: Dictionary = {}

	## 时段轮转
	if slot == "Morning":
		_state_cache["time_slot"] = "Afternoon"
		_state_cache["time_slot_label"] = "下午"
	elif slot == "Afternoon":
		_state_cache["time_slot"] = "Night"
		_state_cache["time_slot_label"] = "晚上"
	else:
		_state_cache["time_slot"] = "Morning"
		_state_cache["time_slot_label"] = "早上"
		day += 1
		_state_cache["day"] = day
		## 新的一天：托梦额度刷新 + 神力回复
		dream_used_today = false
		var old_power: int = int(_state_cache.get("divine_power", 10))
		var max_power: int = int(_state_cache.get("divine_power_max", 10))
		if old_power < max_power:
			_state_cache["divine_power"] = old_power + 1
			resource_delta["divine_power"] = 1
			_resource_change_log.append({"resource": "divine_power", "change": 1, "reason": "新的一天 · 神力回复"})

	## 第60天局终检测
	if day >= 60:
		var slot_changes_end: Array = _resource_change_log.duplicate()
		_resource_change_log.clear()
		return {"run_finished": true, "ending": evaluate_ending(), "summary": "命运的织线已完成编织。", "resource_change_log": slot_changes_end}

	## 周结算检测（每周日晚）
	var week = (day - 1) / 7 + 1
	if day % 7 == 0 and slot == "Night":
		var slot_changes_w: Array = _resource_change_log.duplicate()
		_resource_change_log.clear()
		state_changed.emit()
		return {"week_finished": true, "week_data": {"week": week, "summary": "第 %d 周结束" % week}, "summary": "一周结束，命运产生了新的变化。", "resource_change_log": slot_changes_w}

	## 事件匹配（对齐 MockGameState：按当前天数和时段匹配静态事件）
	var current_day := int(_state_cache.get("day", 1))
	var current_slot := String(_state_cache.get("time_slot", "Morning"))
	_events.clear()
	var static_events: Array = _load_json_array(EVENTS_PATH)
	for event in static_events:
		var dr: String = String(event.get("day_range", ""))
		var ts: String = String(event.get("time_slot", ""))
		if dr != "" and _mock_day_in_range(dr, current_day):
			if ts == current_slot or ts == "Any":
				var evt = event.duplicate(true)
				evt["location_label"] = get_location_label(String(event.get("location_id", "")))
				_events.append(evt)
				## 记录到事件历史
				event_history.append({
					"day": current_day,
					"time_slot": current_slot,
					"time_slot_label": get_time_slot_label(current_slot),
					"location_id": String(event.get("location_id", "")),
					"location_label": get_location_label(String(event.get("location_id", ""))),
					"event_id": String(event.get("event_id", "")),
					"event_name": String(event.get("event_name", "未知事件")),
					"summary": String(event.get("description", "")),
					"risk_level": String(event.get("risk_level", "Low")),
					"participant_names": event.get("participant_display_names", []),
				})

	var slot_changes: Array = _resource_change_log.duplicate()
	_resource_change_log.clear()
	state_changed.emit()
	return {
		"summary": "时间已推进，命运线产生了新的变化。",
		"resource_delta": resource_delta,
		"resource_change_log": slot_changes,
	}

## Mock 天数范围判定（对齐 MockGameState._day_in_range）。
func _mock_day_in_range(day_range: String, day: int) -> bool:
	var s := day_range.replace("Day", "")
	if s.contains("-"):
		var parts := s.split("-")
		return day >= int(parts[0]) and day <= int(parts[1])
	return day == int(s)

## 初始化事件列表（Mock 降级用）：按当前天/时段匹配静态事件。
func _populate_initial_events() -> void:
	_events.clear()
	var current_day := int(_state_cache.get("day", 1))
	var current_slot := String(_state_cache.get("time_slot", "Morning"))
	var static_events: Array = _load_json_array(EVENTS_PATH)
	for event in static_events:
		var dr: String = String(event.get("day_range", ""))
		var ts: String = String(event.get("time_slot", ""))
		if dr != "" and _mock_day_in_range(dr, current_day):
			if ts == current_slot or ts == "Any":
				var evt = event.duplicate(true)
				evt["location_label"] = get_location_label(String(event.get("location_id", "")))
				_events.append(evt)

## 响应时间推进推送（先于事件和结算）。
func _on_time_advanced(data: Dictionary) -> void:
	_state_cache["day"] = data.get("day", _state_cache.get("day", 1))
	## 后端 slot -> 前端 time_slot
	var slot = String(data.get("slot", "morning"))
	if slot == "noon":
		_state_cache["time_slot"] = "Afternoon"
		_state_cache["time_slot_label"] = "下午"
	elif slot == "night":
		_state_cache["time_slot"] = "Night"
		_state_cache["time_slot_label"] = "晚上"
	else:
		_state_cache["time_slot"] = "Morning"
		_state_cache["time_slot_label"] = "早上"
	_state_cache["week"] = data.get("week", 1)
	## 保留 is_new_day / is_new_week 标记
	_state_cache["is_new_day"] = bool(data.get("is_new_day", false))
	_state_cache["is_new_week"] = bool(data.get("is_new_week", false))
	## 新的一天：托梦额度刷新
	if bool(data.get("is_new_day", false)):
		dream_used_today = false
	## 暂不触发 state_changed，等结算完成后统一刷新

## 响应事件触发推送（一个时段可能触发多个事件，累积到待处理队列）。
## 后端 ws_game._handle_advance_time 发送的字段：
##   event_id / event_name / outcome_name / resource_changes / npc_changes / bonds_queued / karma_queued
## 前端 UI 语义映射：outcome_name→outcome, resource_changes→resource_delta。
## 后端未提供 location_id / risk_level / description / available_interventions 字段，此处置默认值。
func _on_event_triggered(data: Dictionary) -> void:
	print("[Event] %s @ %s (%s)" % [
		String(data.get("event_name", "?")),
		String(data.get("location_id", "?")),
		String(data.get("outcome_name", data.get("outcome", "-")))
	])
	## 转换为前端事件格式
	var event_data: Dictionary = {
		"event_id": String(data.get("event_id", "")),
		"event_name": String(data.get("event_name", "未知事件")),
		"location_id": String(data.get("location_id", "")),
		"location_label": get_location_label(String(data.get("location_id", ""))),
		"risk_level": String(data.get("risk_level", "Low")),
		"description": String(data.get("description", "")),
		"outcome": String(data.get("outcome_name", data.get("outcome", ""))),
		"resource_delta": data.get("resource_changes", data.get("resource_delta", {})),
		"available_interventions": data.get("available_interventions", []),
	}
	## 后端对白管线可能附带 dialogue: {location, lines:[{actor, type, text}]}
	## 转换为前端 VN 期望的 dialogue_segments 格式（speaker_id/line_type/position/text）。
	var raw_dialogue = data.get("dialogue", null)
	if raw_dialogue is Dictionary:
		var segs: Array = _dialogue_to_segments(raw_dialogue as Dictionary)
		if not segs.is_empty():
			event_data["dialogue_segments"] = segs
	_pending_events.append(event_data)
	_events.append(event_data)

	## 记录到事件历史
	var day = int(_state_cache.get("day", 1))
	var slot_id = String(_state_cache.get("time_slot", "Morning"))
	event_history.append({
		"day": day,
		"time_slot": slot_id,
		"time_slot_label": get_time_slot_label(slot_id),
		"location_id": String(data.get("location_id", "")),
		"location_label": get_location_label(String(data.get("location_id", ""))),
		"event_id": String(data.get("event_id", "")),
		"event_name": String(data.get("event_name", "未知事件")),
		"summary": String(data.get("description", data.get("outcome_name", ""))),
		"risk_level": String(data.get("risk_level", "Low")),
		"participant_names": data.get("participants", []),
	})

## 将后端对白管线产出的 dialogue（{location, lines:[{actor,type,text}]}）
## 转换为前端 VN 期望的 dialogue_segments（[{speaker_id, speaker_name, line_type, position, text}]）。
## 类型映射：action→narration；dialogue→speech；thought→thought。
## position 分配：叙述固定 center；首个出场角色 left，第二个 right，之后按首次分配复用。
func _dialogue_to_segments(dialogue: Dictionary) -> Array:
	var lines: Array = dialogue.get("lines", []) if dialogue.get("lines") is Array else []
	if lines.is_empty():
		return []
	var segs: Array = []
	var slot_map: Dictionary = {}  # actor_id → "left" | "right"
	for line in lines:
		if not (line is Dictionary):
			continue
		var actor_id: String = String(line.get("actor", ""))
		var ltype_raw: String = String(line.get("type", "dialogue"))
		var text: String = String(line.get("text", ""))
		if text.is_empty():
			continue
		var line_type: String
		match ltype_raw:
			"action":
				line_type = "narration"
			"thought":
				line_type = "thought"
			_:
				line_type = "speech"
		var position: String = "center"
		var speaker_name: String = ""
		var is_narrator: bool = actor_id.is_empty() or actor_id == "narrator" or actor_id == "?"
		if line_type != "narration" and not is_narrator:
			if not slot_map.has(actor_id):
				slot_map[actor_id] = "left" if slot_map.size() % 2 == 0 else "right"
			position = String(slot_map[actor_id])
			var static_data: Dictionary = _static_character_index.get(actor_id, {}) as Dictionary
			speaker_name = String(static_data.get("display_name", actor_id))
		segs.append({
			"speaker_id": "" if is_narrator else actor_id,
			"speaker_name": speaker_name,
			"line_type": line_type,
			"position": position,
			"text": text,
		})
	return segs

## 响应结算完成推送（时间推进流程最后一步）。
## 后端 ws_game._handle_advance_time 发送的 settlement_complete payload：
##   {day, slot, resource:{incense, divine_power, divine_power_max}}
## 注意资源字段嵌在 resource 子对象里；yin_de/yang_de 后端目前未在此消息推送，保留缓存值。
func _on_settlement_complete(data: Dictionary) -> void:
	print("[BackendGameState] settlement_complete signal received! data keys=" + str(data.keys()))
	print("[BackendGameState] settlement_complete signal received!")
	## 后端字段兼容：优先读嵌套 resource，缺失时回退到扁平字段，最后回退到缓存。
	var res: Dictionary = data.get("resource", {}) if data.get("resource") is Dictionary else {}
	_state_cache["incense"] = int(res.get("incense", data.get("incense", _state_cache.get("incense", 0))))
	_state_cache["divine_power"] = int(res.get("divine_power", data.get("divine_power", _state_cache.get("divine_power", 0))))
	_state_cache["divine_power_max"] = int(res.get("divine_power_max", data.get("divine_power_max", _state_cache.get("divine_power_max", 10))))
	_state_cache["yin_de"] = int(res.get("yin_de", data.get("yin_de", _state_cache.get("yin_de", 0))))
	_state_cache["yang_de"] = int(res.get("yang_de", data.get("yang_de", _state_cache.get("yang_de", 0))))

	## 同步天/时段（settlement_complete 会带最新 day/slot）
	if data.has("day"):
		_state_cache["day"] = int(data.get("day", _state_cache.get("day", 1)))
	if data.has("slot"):
		var slot_val = String(data.get("slot", "morning"))
		if slot_val == "noon":
			_state_cache["time_slot"] = "Afternoon"
			_state_cache["time_slot_label"] = "下午"
		elif slot_val == "night":
			_state_cache["time_slot"] = "Night"
			_state_cache["time_slot_label"] = "晚上"
		else:
			_state_cache["time_slot"] = "Morning"
			_state_cache["time_slot_label"] = "早上"

	## 更新 NPC 状态（位置/幸福度等可能变化）
	if data.has("npcs"):
		_characters = _normalize_npcs(data.get("npcs", []))
	## 地点缓存需要重新聚合
	_locations.clear()

	## 构造结算结果（与 Mock 格式一致）
	var event_changes: Array = []
	for evt in _pending_events:
		event_changes.append({
			"event_name": String(evt.get("event_name", "未知事件")),
			"outcome": String(evt.get("outcome", "已发生"))
		})

	_last_advance_result = {
		"summary": data.get("summary", "命运线产生了新的变化。"),
		"resource_delta": data.get("resource_delta", {}),
		"resource_change_log": _resource_change_log.duplicate(),
		"event_changes": event_changes,
		"character_changes": [],
	}

	## 局终和周结算标记（由后端判断）
	if data.has("run_finished") and bool(data.get("run_finished", false)):
		_last_advance_result["run_finished"] = true
		_last_advance_result["ending"] = data.get("ending", {})
	if data.has("week_finished") and bool(data.get("week_finished", false)):
		_last_advance_result["week_finished"] = true
		_last_advance_result["week_data"] = data.get("week_data", {})

	## 清空待处理事件队列和资源日志
	_pending_events.clear()
	_resource_change_log.clear()
	## 注意：不在此处触发 state_changed —— 由 UI 在过场动画结束后统一刷新，
	## 避免 HUD 在结算面板显示前就变到新状态（视觉上"抢跑"）。
	## HUD 刷新入口：main_game_ui._do_advance_time 在 time_transition.play() await 完成后手动调用。
	print("[BackendGameState] _settlement_arrived = true")
	_settlement_arrived = true

func get_interventions_for_event(event: Dictionary) -> Array:
	var event_id = String(event.get("event_id", ""))
	for evt in _events:
		if String(evt.get("event_id", "")) == event_id:
			return evt.get("available_interventions", [])
	return []

## 执行干预（通过 WebSocket 发送到后端）。
## context: {dream_text?: String} — 托梦文字仅入历史，不影响硬币结算。
func apply_intervention(event_id: String, intervention_id: String, context: Dictionary = {}) -> Dictionary:
	## 事件级锁定：同一事件只能干预一次
	if _applied_interventions.has(event_id):
		var prev: Dictionary = _applied_interventions[event_id]
		var prev_name: String = String(prev.get("display_name", "干预"))
		return {
			"success": false,
			"summary": "此事件已被【%s】干预，命运线不再接受二次干预。" % prev_name,
		}

	## 从事件缓存中查找 display_name、base_coins、difficulty
	var display_name: String = intervention_id
	var event_name: String = ""
	var base_coins: int = 1
	var difficulty: int = 1
	var success_label: String = "命运线出现了微小的偏转。"
	var failure_label: String = "命运线纹丝不动，干预未能奏效。"
	for evt in _events:
		if String(evt.get("event_id", "")) == event_id:
			event_name = String(evt.get("event_name", ""))
			base_coins = int(evt.get("base_coins", 1))
			difficulty = int(evt.get("difficulty", 1))
			success_label = String(evt.get("coin_success_label", success_label))
			failure_label = String(evt.get("coin_failure_label", failure_label))
			for iv in evt.get("available_interventions", []):
				if String(iv.get("intervention_id", "")) == intervention_id:
					display_name = String(iv.get("display_name", intervention_id))
					break
			break

	## 消耗神力（对齐 Mock：托梦 2、赐福 3、默认 2）
	var cost: int = 3 if intervention_id == "blessing" else 2
	var current_power: int = int(_state_cache.get("divine_power", 0))
	if current_power < cost:
		return {"success": false, "summary": "神力不足"}

	## 命运硬币结算
	var bonus_coins: int = 1 if intervention_id == "blessing" else 0
	var coin_result: Dictionary = _roll_coins(base_coins, bonus_coins, difficulty)
	coin_result["outcome_label"] = success_label if bool(coin_result.get("success", false)) else failure_label

	_state_cache["divine_power"] = current_power - cost
	_resource_change_log.append({
		"resource": "divine_power",
		"change": -cost,
		"reason": "%s · %s" % [display_name, event_name],
	})
	var yang_gain: int = 1 if bool(coin_result.get("success", false)) else 0
	if yang_gain > 0:
		_state_cache["yang_de"] = int(_state_cache.get("yang_de", 0)) + yang_gain
		_resource_change_log.append({
			"resource": "yang_de",
			"change": yang_gain,
			"reason": "%s 成功" % display_name,
		})

	## 托梦文字（<=100 字，超出截断）
	var dream_text: String = String(context.get("dream_text", ""))
	if dream_text.length() > 100:
		dream_text = dream_text.substr(0, 100)

	_applied_interventions[event_id] = {
		"intervention_id": intervention_id,
		"display_name": display_name,
		"dream_text": dream_text,
		"coin_result": coin_result,
	}

	## 事件历史注入干预痕迹
	for entry in event_history:
		if String(entry.get("event_id", "")) == event_id:
			entry["intervention_id"] = intervention_id
			entry["intervention_display_name"] = display_name
			if dream_text != "":
				entry["dream_text"] = dream_text
			entry["coin_result_success"] = bool(coin_result.get("success", false))
			break

	state_changed.emit()

	## 通过 WebSocket 发送干预请求（后端会把托梦/赐福写入对应 NPC 记忆）
	if not Backend.use_mock_fallback:
		var target_ids: Array = _collect_event_participant_ids(event_id)
		Backend.send_intervention(event_id, intervention_id, dream_text, target_ids, coin_result)

	var resource_delta: Dictionary = {"divine_power": -cost}
	if yang_gain > 0:
		resource_delta["yang_de"] = yang_gain

	return {
		"success": true,
		"event_id": event_id,
		"intervention_id": intervention_id,
		"cost": cost,
		"summary": "%s：%s" % [event_name if event_name != "" else "事件", coin_result.get("outcome_label", "")],
		"resource_delta": resource_delta,
		"coin_result": coin_result,
		"dream_text": dream_text,
	}

## 查询事件是否已被干预（用于 UI 锁定显示）。
func get_applied_intervention(event_id: String) -> Dictionary:
	return _applied_interventions.get(event_id, {})

## 从事件缓存中收集参与 NPC 的 ID（用于把托梦/赐福写入对应 NPC 记忆）。
## 后端 event_triggered 目前未推送参与者，先从事件历史 participant_names 兜底，
## 找不到就退化为空数组 —— 后端在收到空数组时会走全局氛围记忆写入。
func _collect_event_participant_ids(event_id: String) -> Array:
	for evt in _events:
		if String(evt.get("event_id", "")) == event_id:
			var direct: Array = evt.get("participant_ids", [])
			if not direct.is_empty():
				return direct
			var names: Array = evt.get("participant_names", [])
			if not names.is_empty():
				return _npc_ids_by_names(names)
	for entry in event_history:
		if String(entry.get("event_id", "")) == event_id:
			var names2: Array = entry.get("participant_names", [])
			return _npc_ids_by_names(names2)
	return []

func _npc_ids_by_names(names: Array) -> Array:
	var result: Array = []
	for nm in names:
		var nm_str: String = String(nm)
		for npc in _characters:
			if String(npc.get("name", "")) == nm_str or String(npc.get("display_name", "")) == nm_str:
				result.append(String(npc.get("npc_id", "")))
				break
	return result

## 命运硬币投掷（对齐 Mock 实现）。
func _roll_coins(base_coins: int, bonus_coins: int, difficulty: int) -> Dictionary:
	var total: int = max(1, base_coins + bonus_coins)
	var flips: Array = []
	var heads: int = 0
	for i in range(total):
		var head: bool = randi() % 2 == 0
		flips.append(head)
		if head:
			heads += 1
	return {
		"base_coins": base_coins,
		"bonus_coins": bonus_coins,
		"coins_thrown": total,
		"flips": flips,
		"heads": heads,
		"difficulty": difficulty,
		"success": heads >= difficulty,
	}

## 结局判定：从状态缓存计算（由后端在第60天推送最终结局）。
func evaluate_ending() -> Dictionary:
	if _state_cache.has("ending"):
		return _state_cache.get("ending", {})

	## 本地兜底计算（后端未推送时使用）
	var incense = int(_state_cache.get("incense", 0))
	var yang_de = int(_state_cache.get("yang_de", 0))
	var yin_de = int(_state_cache.get("yin_de", 0))
	var ending_id: String
	if incense <= 0:
		ending_id = "game_over_incense_out"
	elif yang_de >= 80 and incense >= 300:
		ending_id = "legend_guardian"
	elif yang_de >= yin_de and yang_de >= 40:
		ending_id = "righteous_god"
	elif yin_de > yang_de and yin_de >= 40:
		ending_id = "evil_god"
	else:
		ending_id = "neutral_god"
	return {
		"ending_id": ending_id,
		"is_failure": ending_id == "game_over_incense_out",
	}

## 检查是否有加载错误（与 Mock API 对齐）。
func has_load_error() -> bool:
	return false

# ──────────────────────────────────────────
# 托梦 / 赐福 / 事件锁定（角色维度 + 演出内决策）
# 与 MockGameState API 完全对齐，UI 侧鸭子类型互换。
# ──────────────────────────────────────────

## 托梦：仅夜晚可用、每日一次、消耗 DREAM_COST 神力。
## 语义：把梦写入目标 NPC 的运行时 dream_memories；真实后端下同时通过 send_intervention
## 走 dream_hint 通道，让后端把这段文字写入 NPC 记忆库。
func apply_dream(npc_id: String, dream_text: String) -> Dictionary:
	var slot: String = String(_state_cache.get("time_slot", "Morning"))
	if slot != "Night":
		return {"success": false, "summary": "托梦须在夜晚。"}
	if dream_used_today:
		return {"success": false, "summary": "今日已托过一梦，明夜再来。"}
	var current_power: int = int(_state_cache.get("divine_power", 0))
	if current_power < DREAM_COST:
		return {"success": false, "summary": "神力不足，托梦需 %d 点神力。" % DREAM_COST}
	var character: Dictionary = find_character(npc_id)
	if character.is_empty():
		return {"success": false, "summary": "找不到这位居民。"}

	var text: String = dream_text.strip_edges()
	if text.length() > 100:
		text = text.substr(0, 100)

	## 前端本地内存：写入运行时 dream_memories
	var memories: Array = character.get("dream_memories", [])
	memories.append({
		"day": int(_state_cache.get("day", 1)),
		"time_slot": slot,
		"text": text,
	})
	character["dream_memories"] = memories
	## 同步回缓存
	for i in range(_characters.size()):
		if String(_characters[i].get("npc_id", "")) == npc_id:
			_characters[i]["dream_memories"] = memories
			break

	_state_cache["divine_power"] = current_power - DREAM_COST
	_resource_change_log.append({
		"resource": "divine_power",
		"change": -DREAM_COST,
		"reason": "托梦 · %s" % String(character.get("display_name", "居民")),
	})
	dream_used_today = true

	## 真实后端：走 dream_hint 通道把文字写入后端 NPC 记忆库
	if not Backend.use_mock_fallback:
		Backend.send_intervention("", "dream_hint", text, [npc_id], {})

	state_changed.emit()
	npc_updated.emit(npc_id)

	return {
		"success": true,
		"summary": "托梦已入 %s 的梦境。" % String(character.get("display_name", "居民")),
		"resource_delta": {"divine_power": -DREAM_COST},
		"dream_text": text,
	}

## 演出内赐福（键点决策）。与 Mock 语义对齐。
func apply_blessing(event_id: String, seg_index: int, prompt: Dictionary, choice: bool) -> Dictionary:
	if not choice:
		_append_blessing_snapshot(event_id, seg_index, false, {})
		return {"success": true, "blessed": false, "summary": "命运未被打扰。"}

	var cost: int = int(prompt.get("cost", 3))
	var current_power: int = int(_state_cache.get("divine_power", 0))
	if current_power < cost:
		return {"success": false, "blessed": false, "summary": "神力不足，赐福需 %d 点神力。" % cost}

	var base_coins: int = 1
	for evt in _events:
		if String(evt.get("event_id", "")) == event_id:
			base_coins = int(evt.get("base_coins", 1))
			break
	var difficulty: int = int(prompt.get("difficulty_value", 1))
	var coin_result: Dictionary = _roll_coins(base_coins, 1, difficulty)
	var success_label: String = String(prompt.get("success_effect", "命运线出现了微小的偏转。"))
	var failure_label: String = String(prompt.get("failure_effect", "命运线纹丝不动，赐福未能奏效。"))
	coin_result["outcome_label"] = success_label if bool(coin_result.get("success", false)) else failure_label

	_state_cache["divine_power"] = current_power - cost
	var resource_delta: Dictionary = {"divine_power": -cost}
	_resource_change_log.append({
		"resource": "divine_power",
		"change": -cost,
		"reason": "赐福",
	})
	if bool(coin_result.get("success", false)):
		_state_cache["yang_de"] = int(_state_cache.get("yang_de", 0)) + 1
		resource_delta["yang_de"] = 1
		_resource_change_log.append({
			"resource": "yang_de",
			"change": 1,
			"reason": "赐福成功",
		})

	_append_blessing_snapshot(event_id, seg_index, true, coin_result)

	## 真实后端：赐福同步走 blessing 通道（后端只需硬币结果，seg_index 是前端快照维度不上报）
	if not Backend.use_mock_fallback:
		Backend.send_intervention(event_id, "blessing", "", [], coin_result)

	state_changed.emit()

	return {
		"success": true,
		"blessed": true,
		"coin_result": coin_result,
		"resource_delta": resource_delta,
		"summary": coin_result.get("outcome_label", ""),
	}

func _append_blessing_snapshot(event_id: String, seg_index: int, blessed: bool, coin_result: Dictionary) -> void:
	var snap: Dictionary = _event_snapshots.get(event_id, {})
	var blessings: Array = snap.get("blessings", [])
	blessings.append({
		"seg_index": seg_index,
		"bless": blessed,
		"coin_result": coin_result,
	})
	snap["blessings"] = blessings
	_event_snapshots[event_id] = snap

## 事件演出结束：标记为已完成并落定最终快照。
func mark_event_completed(event_id: String, extra_snapshot: Dictionary = {}) -> void:
	if event_id == "":
		return
	if _completed_events.has(event_id):
		return
	var snap: Dictionary = _event_snapshots.get(event_id, {})
	for key in extra_snapshot.keys():
		snap[key] = extra_snapshot[key]
	snap["finished_at"] = {
		"day": int(_state_cache.get("day", 1)),
		"time_slot": String(_state_cache.get("time_slot", "Morning")),
	}
	_event_snapshots[event_id] = snap
	_completed_events[event_id] = true
	state_changed.emit()
	event_completed.emit(event_id, snap)

func is_event_completed(event_id: String) -> bool:
	return _completed_events.has(event_id)

func get_event_snapshot(event_id: String) -> Dictionary:
	return _event_snapshots.get(event_id, {})
