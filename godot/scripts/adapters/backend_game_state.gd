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
	## 加载与 Mock 共用的静态数据（描述、日程、干预定义等 backend 不推送的字段）
	_load_static_data()
	## 初始化缓存
	_pending_events.clear()
	_last_advance_result.clear()
	_applied_interventions.clear()

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
	state_changed.emit()

## NPC 对话响应（暂存，供 UI 读取）。
var _last_npc_response: Dictionary = {}

func _on_npc_response(data: Dictionary) -> void:
	_last_npc_response = data
	## 可添加信号通知 UI 对话已响应

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
					"agent_tier", "is_unlocked"]:
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
	_locations.clear()
	## 先统计每个地点当前有哪些 NPC
	var present_by_loc: Dictionary = {}
	for npc in _characters:
		var loc_id: String = String(npc.get("location", ""))
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

	## 发送 WebSocket 请求，等待结算完成信号后再返回结果
	Backend.send_advance_time()
	## 等待后端推送 settlement_complete；_on_settlement_complete 会填充 _last_advance_result
	await Backend.settlement_complete
	return _last_advance_result.duplicate()

## Mock 降级模式的本地时间推进（保持前端可独立测试）。
func _mock_advance_time() -> Dictionary:
	var day = int(_state_cache.get("day", 1))
	var slot = String(_state_cache.get("time_slot", "Morning"))

	## 时段轮转
	if slot == "Morning":
		_state_cache["time_slot"] = "Afternoon"
	elif slot == "Afternoon":
		_state_cache["time_slot"] = "Night"
	else:
		_state_cache["time_slot"] = "Morning"
		day += 1
		_state_cache["day"] = day

	## 资源变化
	_state_cache["incense"] = int(_state_cache.get("incense", 100)) + randi_range(-5, 10)
	_state_cache["divine_power"] = min(int(_state_cache.get("divine_power", 10)) + 1, int(_state_cache.get("divine_power_max", 10)))

	## 第60天局终检测
	if day >= 60:
		return {"run_finished": true, "ending": evaluate_ending(), "summary": "命运的织线已完成编织。"}

	## 周结算检测（每周日晚）
	var week = (day - 1) / 7 + 1
	if day % 7 == 0 and slot == "Night":
		return {"week_finished": true, "week_data": {"week": week, "summary": "第 %d 周结束" % week}, "summary": "一周结束，命运产生了新的变化。"}

	state_changed.emit()
	return {"summary": "时间已推进，命运线产生了新的变化。", "resource_delta": {}}

## 响应时间推进推送（先于事件和结算）。
func _on_time_advanced(data: Dictionary) -> void:
	_state_cache["day"] = data.get("day", _state_cache.get("day", 1))
	## 后端 slot -> 前端 time_slot
	var slot = String(data.get("slot", "morning"))
	if slot == "noon":
		_state_cache["time_slot"] = "Afternoon"
	elif slot == "night":
		_state_cache["time_slot"] = "Night"
	else:
		_state_cache["time_slot"] = "Morning"
	_state_cache["week"] = data.get("week", 1)
	## 保留 is_new_day / is_new_week 标记
	_state_cache["is_new_day"] = bool(data.get("is_new_day", false))
	_state_cache["is_new_week"] = bool(data.get("is_new_week", false))
	## 暂不触发 state_changed，等结算完成后统一刷新

## 响应事件触发推送（一个时段可能触发多个事件，累积到待处理队列）。
## 后端 ws_game._handle_advance_time 发送的字段：
##   event_id / event_name / outcome_name / resource_changes / npc_changes / bonds_queued / karma_queued
## 前端 UI 语义映射：outcome_name→outcome, resource_changes→resource_delta。
## 后端未提供 location_id / risk_level / description / available_interventions 字段，此处置默认值。
func _on_event_triggered(data: Dictionary) -> void:
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

## 响应结算完成推送（时间推进流程最后一步）。
## 后端 ws_game._handle_advance_time 发送的 settlement_complete payload：
##   {day, slot, resource:{incense, divine_power, divine_power_max}}
## 注意资源字段嵌在 resource 子对象里；yin_de/yang_de 后端目前未在此消息推送，保留缓存值。
func _on_settlement_complete(data: Dictionary) -> void:
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
		elif slot_val == "night":
			_state_cache["time_slot"] = "Night"
		else:
			_state_cache["time_slot"] = "Morning"

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

	## 清空待处理事件队列
	_pending_events.clear()
	## 最后触发状态刷新，UI 收到信号后读取新状态
	state_changed.emit()

## 获取事件可用的干预选项（从缓存事件中查询）。
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
	var yang_gain: int = 1 if bool(coin_result.get("success", false)) else 0
	if yang_gain > 0:
		_state_cache["yang_de"] = int(_state_cache.get("yang_de", 0)) + yang_gain

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
