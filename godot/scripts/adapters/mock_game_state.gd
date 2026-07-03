extends RefCounted
class_name MockGameState

## MVP 阶段游戏状态模拟层（前端竖切数据适配器）。
## 从本地 JSON 文件读取 mock 数据，提供统一的游戏状态 API 供 HUD 消费。
## 真实后端接入后，替换此类实现即可，无需修改前端 UI 代码。
## 核心功能：资源管理、时间推进、NPC/地点/事件查询、干预执行、结局判定、事件历史。

signal state_changed

const GAME_STATE_PATH := "res://data/mock/game_state.json"
const CHARACTERS_PATH := "res://data/mock/characters.json"
const LOCATIONS_PATH := "res://data/mock/locations.json"
const EVENTS_PATH := "res://data/mock/events.json"
const INTERVENTIONS_PATH := "res://data/mock/interventions.json"

## MVP 结局定义（简化自 design/data/结局判定表.csv）。
## 真实结局系统接入后由数据层替换；此处仅前端竖切占位。
const ENDING_DEFS := {
	"game_over_incense_out": {
		"title": "香火熄灭",
		"ending_type": "Failure",
		"is_failure": true,
		"route_label": "失败结局",
		"evaluation": "旧神已逝",
		"description": "土地庙前最后一缕香火散去。\n归潮镇不再记得你的名字，\n潮水照旧涨落，只是再没有人来上香。",
		"reason": "第 60 天香火低于 100",
	},
	"legend_guardian": {
		"title": "归潮传说",
		"ending_type": "Legend",
		"is_failure": false,
		"route_label": "传奇结局",
		"evaluation": "传说",
		"description": "灾后的小镇重新升起炊烟。\n人们说不清是谁守住了这片海岸，\n却仍有人在清晨低声念起岛爷的名字。",
	},
	"righteous_god": {
		"title": "天界善神",
		"ending_type": "Righteous",
		"is_failure": false,
		"route_label": "正神结局",
		"evaluation": "守护者",
		"description": "归潮镇的人们仍会在清晨点燃第一炷香。\n他们不知道是谁改变了命运，\n但他们记得风从海边吹来时的安宁。",
	},
	"evil_god": {
		"title": "地府邪神",
		"ending_type": "Evil",
		"is_failure": false,
		"route_label": "邪神结局",
		"evaluation": "腐化者",
		"description": "小镇依旧供奉着你，\n香火比从前更旺，\n只是人们低头上香时，眼里多了一分畏惧。",
	},
	"neutral_god": {
		"title": "旧庙余香",
		"ending_type": "Neutral",
		"is_failure": false,
		"route_label": "中性结局",
		"evaluation": "旁观者",
		"description": "土地公勉强通过了考核。\n归潮镇的日子照常继续，\n许多问题仍没有答案，潮水来了又去。",
	},
}


var game_state: Dictionary = {}
var characters: Array = []
var locations: Array = []
var events: Array = []
var interventions: Array = []
var load_error: bool = false
var event_history: Array = []
## 已应用干预的事件锁定表：event_id -> {intervention_id, display_name}
## 每个事件仅可干预一次；命中锁定的事件在 UI 上显示「已干预」并禁用全部干预按钮。
var _applied_interventions: Dictionary = {}

func _init() -> void:
	reset_to_new_game()

func reset_to_new_game() -> void:
	load_error = false
	game_state = _load_dictionary(GAME_STATE_PATH)
	characters = _load_array(CHARACTERS_PATH)
	locations = _load_array(LOCATIONS_PATH)
	events = _load_array(EVENTS_PATH)
	interventions = _load_array(INTERVENTIONS_PATH)
	event_history.clear()
	_applied_interventions.clear()
	state_changed.emit()

func get_event_history() -> Array:
	return event_history

func _record_event(event: Dictionary) -> void:
	var event_id: String = String(event.get("event_id", ""))
	for entry in event_history:
		if String(entry.get("event_id", "")) == event_id:
			return
	var day := int(game_state.get("day", 1))
	var slot_id := String(game_state.get("time_slot", "Morning"))
	event_history.append({
		"day": day,
		"time_slot": slot_id,
		"time_slot_label": get_time_slot_label(slot_id),
		"location_id": String(event.get("location_id", "")),
		"location_label": String(event.get("location_label", "未知地点")),
		"event_id": event_id,
		"event_name": String(event.get("event_name", "未知事件")),
		"summary": String(event.get("description", "")),
		"risk_level": String(event.get("risk_level", "Low")),
		"participant_names": event.get("participant_display_names", []),
	})

func _day_in_range(day_range: String, day: int) -> bool:
	var s := day_range.replace("Day", "")
	if s.contains("-"):
		var parts := s.split("-")
		return day >= int(parts[0]) and day <= int(parts[1])
	return day == int(s)

func has_load_error() -> bool:
	return load_error

func get_game_state() -> Dictionary:
	return game_state

func get_characters() -> Array:
	return characters

func get_locations() -> Array:
	return locations

func get_events() -> Array:
	var intervention_labels_by_id: Dictionary = {}
	for intervention in interventions:
		var intervention_id: String = String(intervention.get("intervention_id", ""))
		var display_name: String = String(intervention.get("display_name", "未知干预"))
		intervention_labels_by_id[intervention_id] = display_name
	for event in events:
		var labels: Array[String] = []
		var available_ids: Array = Array(event.get("available_intervention_ids", []))
		for intervention_id in available_ids:
			var id_str: String = String(intervention_id)
			labels.append(String(intervention_labels_by_id.get(id_str, id_str)))
		event["available_intervention_labels"] = labels
	return events

func find_character(npc_id: String) -> Dictionary:
	return _find_by_id(characters, "npc_id", npc_id)

func find_location(location_id: String) -> Dictionary:
	return _find_by_id(locations, "location_id", location_id)

func get_location_label(location_id: String) -> String:
	var location := find_location(location_id)
	if location.is_empty():
		return "未知地点" if location_id == "" else location_id
	return location.get("display_name", "未知地点")

func get_time_slot_label(slot_id: String) -> String:
	match slot_id:
		"Morning":
			return "早上"
		"Afternoon":
			return "下午"
		"Night":
			return "晚上"
		_:
			return slot_id

func get_interventions_for_event(event: Dictionary) -> Array:
	var available_ids: Array = event.get("available_intervention_ids", [])
	var result: Array = []
	for intervention in interventions:
		if available_ids.has(intervention.get("intervention_id", "")) and bool(intervention.get("mvp_enabled", true)):
			result.append(intervention)
	return result

func apply_intervention(event_id: String, intervention_id: String, context: Dictionary = {}) -> Dictionary:
	var event: Dictionary = _find_by_id(events, "event_id", event_id)
	var intervention: Dictionary = _find_by_id(interventions, "intervention_id", intervention_id)
	if event.is_empty() or intervention.is_empty():
		return {
			"success": false,
			"error": "未知事件或干预。",
			"summary": "命运织线器没有找到对应的事件。",
			"changed_fields": [],
		}
	if _applied_interventions.has(event_id):
		var prev: Dictionary = _applied_interventions[event_id]
		var prev_name: String = String(prev.get("display_name", "干预"))
		return {
			"success": false,
			"error": "事件已干预。",
			"summary": "「%s」已被【%s】影响，命运线不再接受二次干预。" % [event.get("event_name", "未知事件"), prev_name],
			"changed_fields": [],
		}
	var cost := int(intervention.get("cost_divine_power", 0))
	var divine_power := int(game_state.get("divine_power", 0))
	if divine_power < cost:
		return {
			"success": false,
			"error": "神力不足，无法执行该干预。",
			"summary": "神力不足，无法执行该干预。",
			"changed_fields": [],
		}

	## 命运硬币结算：赐福 +1 硬币，托梦不加成（文字只入历史）
	var base_coins: int = int(event.get("base_coins", 1))
	var difficulty: int = int(event.get("difficulty", 1))
	var bonus_coins: int = 1 if intervention_id == "blessing" else 0
	var coin_result: Dictionary = _roll_coins(base_coins, bonus_coins, difficulty)
	var success_label: String = String(event.get("coin_success_label", "命运线出现了微小的偏转。"))
	var failure_label: String = String(event.get("coin_failure_label", "命运线纹丝不动，干预未能奏效。"))
	coin_result["outcome_label"] = success_label if bool(coin_result.get("success", false)) else failure_label

	## 资源变化：神力必扣；阳德仅在成功时 +1；阴德在失败且是阴德倾向干预时 +1（MVP：托梦/赐福均阳德倾向，失败不产生阴德）
	game_state["divine_power"] = divine_power - cost
	var yang_gain: int = 1 if bool(coin_result.get("success", false)) else 0
	if yang_gain > 0:
		game_state["yang_de"] = int(game_state.get("yang_de", 0)) + yang_gain

	## 托梦文字（<=100 字，超出截断）
	var dream_text: String = String(context.get("dream_text", ""))
	if dream_text.length() > 100:
		dream_text = dream_text.substr(0, 100)

	game_state["current_hint"] = "%s 已影响「%s」。" % [intervention.get("display_name", "未知干预"), event.get("event_name", "未知事件")]
	_applied_interventions[event_id] = {
		"intervention_id": intervention_id,
		"display_name": String(intervention.get("display_name", "干预")),
		"dream_text": dream_text,
		"coin_result": coin_result,
	}

	## 事件历史注入干预痕迹
	for entry in event_history:
		if String(entry.get("event_id", "")) == event_id:
			entry["intervention_id"] = intervention_id
			entry["intervention_display_name"] = String(intervention.get("display_name", "干预"))
			if dream_text != "":
				entry["dream_text"] = dream_text
			entry["coin_result_success"] = bool(coin_result.get("success", false))
			break

	state_changed.emit()

	var resource_delta: Dictionary = {"divine_power": -cost}
	if yang_gain > 0:
		resource_delta["yang_de"] = yang_gain

	return {
		"success": true,
		"summary": "%s：%s" % [event.get("event_name", "未知事件"), coin_result.get("outcome_label", "")],
		"resource_delta": resource_delta,
		"coin_result": coin_result,
		"dream_text": dream_text,
		"changed_fields": ["divine_power", "yang_de", "events"],
	}

## 查询事件是否已被干预（用于 UI 锁定显示）。
## 返回 {intervention_id, display_name, dream_text, coin_result}；未干预则返回空字典。
func get_applied_intervention(event_id: String) -> Dictionary:
	return _applied_interventions.get(event_id, {})

## 命运硬币投掷（正面 50%）。返回 {coins_thrown, heads, flips, difficulty, base_coins, bonus_coins, success}。
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

func advance_time() -> Dictionary:
	var slot_id := String(game_state.get("time_slot", "Morning"))
	var day := int(game_state.get("day", 1))
	var max_day := int(game_state.get("max_day", 60))
	var resource_delta: Dictionary = {}

	# 局终判定：第 max_day 天夜晚后继续推进即结束本局。
	if slot_id == "Night" and day >= max_day:
		game_state["run_finished"] = true
		game_state["current_hint"] = "命运织线已到尽头，归潮镇的故事走向终局。"
		state_changed.emit()
		return {
			"run_finished": true,
			"ending": evaluate_ending(),
		}

	if slot_id == "Morning":
		game_state["time_slot"] = "Afternoon"
		game_state["time_slot_label"] = "下午"
	elif slot_id == "Afternoon":
		game_state["time_slot"] = "Night"
		game_state["time_slot_label"] = "晚上"
	else:
		game_state["day"] = min(day + 1, int(game_state.get("max_day", 60)))
		game_state["time_slot"] = "Morning"
		game_state["time_slot_label"] = "早上"
		var old_power: int = int(game_state.get("divine_power", 0))
		var new_power: int = min(old_power + 1, int(game_state.get("divine_power_max", 99)))
		game_state["divine_power"] = new_power
		if new_power != old_power:
			resource_delta["divine_power"] = new_power - old_power
		# 周结算判定：刚结束的「day」为 7 的倍数且未到 max_day（第 60 天走总评）。
		if day % 7 == 0 and day < max_day:
			game_state["current_hint"] = "新的一周开始，归潮镇又过了七日。"
			state_changed.emit()
			return {
				"week_finished": true,
				"week_data": _build_week_data(day),
				"resource_delta": resource_delta,
			}

	# MVP：按当前天数和时段匹配 mock 事件并记录到历史。
	var current_day := int(game_state.get("day", 1))
	var current_slot := String(game_state.get("time_slot", "Morning"))
	for event in events:
		var dr: String = String(event.get("day_range", ""))
		var ts: String = String(event.get("time_slot", ""))
		if dr != "" and _day_in_range(dr, current_day):
			if ts == current_slot or ts == "Any":
				_record_event(event)

	game_state["current_hint"] = "命运线轻轻震动，新的时段已经开始。"
	state_changed.emit()
	return {
		"summary": "时间推进：第 %d 天 · %s" % [game_state.get("day", 1), game_state.get("time_slot_label", "早上")],
		"resource_delta": resource_delta,
		"changed_fields": ["day", "time_slot", "divine_power"],
	}

func is_run_finished() -> bool:
	return bool(game_state.get("run_finished", false))

## 单个角色结局数据（MVP 占位）。按 risk_level 简化推导结局类型与文案。
func get_character_ending(npc_id: String) -> Dictionary:
	var character := find_character(npc_id)
	if character.is_empty():
		return {
			"name": "未知居民",
			"ending_type": "中性结局",
			"ending_text": "命运的织线没有找到这个人的归宿。",
			"reasons": [],
			"resource_impact": {},
		}
	var risk: String = String(character.get("risk_level", "Low"))
	var ending_type := "中性结局"
	var ending_text := "命运在此落下帷幕，归潮镇的日子照常继续。"
	var resource_impact := {"incense": 1}
	match risk:
		"Low":
			ending_type = "好结局"
			ending_text = "在你的轻推之下，TA 走出了阴影，\n以自己的方式继续生活。"
			resource_impact = {"yang_de": 10, "incense": 3}
		"Medium":
			ending_type = "中性结局"
			ending_text = "命运没有大起大落，\nTA 平静地接受了眼前的生活。"
			resource_impact = {"incense": 2}
		"High", "Fatal":
			ending_type = "坏结局"
			ending_text = "尽管命运被轻推，\nTA 最终仍走向了不愿见到的结局。"
			resource_impact = {"yin_de": 8}
	return {
		"name": String(character.get("display_name", "居民")),
		"ending_type": ending_type,
		"ending_text": ending_text,
		"reasons": [
			"主业线：%s" % String(character.get("karma_summary", "未知业线")),
			"业线完成度 %d%%" % int(character.get("karma_progress", 0)),
			"最终风险等级：%s" % risk,
		],
		"resource_impact": resource_impact,
	}

## 周结算数据（MVP 占位）。真实系统接入后由数据层提供按周差值。
func _build_week_data(completed_day: int) -> Dictionary:
	var week_number := int(completed_day / 7.0)
	var events_this_week: Array = []
	for event in events:
		events_this_week.append(String(event.get("event_name", "未知事件")))
	var destiny_progress: Array = []
	for character in characters:
		if not bool(character.get("is_unlocked", true)):
			continue
		if String(character.get("karma_summary", "")) == "":
			continue
		destiny_progress.append({
			"name": String(character.get("display_name", "居民")),
			"karma_summary": String(character.get("karma_summary", "")),
			"progress": int(character.get("karma_progress", 0)),
			"risk_level": String(character.get("risk_level", "Low")),
		})
	return {
		"week_number": week_number,
		"day_range": "第 %d–%d 天" % [completed_day - 6, completed_day],
		"resources": {
			"incense": int(game_state.get("incense", 0)),
			"divine_power": int(game_state.get("divine_power", 0)),
			"yang_de": int(game_state.get("yang_de", 0)),
			"yin_de": int(game_state.get("yin_de", 0)),
		},
		"major_events": events_this_week,
		"destiny_progress": destiny_progress,
		"next_hint": "下一周，归潮镇的命运仍在流动。",
	}

func evaluate_ending() -> Dictionary:
	var incense := int(game_state.get("incense", 0))
	var yang := int(game_state.get("yang_de", 0))
	var yin := int(game_state.get("yin_de", 0))
	var diff := yang - yin
	var ending_id := "neutral_god"
	if incense < 100:
		ending_id = "game_over_incense_out"
	elif incense >= 150 and yang >= 80:
		ending_id = "legend_guardian"
	elif diff >= 20:
		ending_id = "righteous_god"
	elif -diff >= 20:
		ending_id = "evil_god"
	return _build_ending_data(ending_id)

func _build_ending_data(ending_id: String) -> Dictionary:
	var def: Dictionary = ENDING_DEFS.get(ending_id, ENDING_DEFS["neutral_god"])
	var data: Dictionary = def.duplicate(true)
	data["ending_id"] = ending_id
	data["resources"] = {
		"incense": int(game_state.get("incense", 0)),
		"yang_de": int(game_state.get("yang_de", 0)),
		"yin_de": int(game_state.get("yin_de", 0)),
		"divine_power": int(game_state.get("divine_power", 0)),
	}
	data["trigger_time"] = "第 %d 天 · %s" % [
		int(game_state.get("day", 60)),
		String(game_state.get("time_slot_label", "夜")),
	]
	data["character_endings"] = _build_character_endings(ending_id)
	data["key_events"] = _build_key_events()
	return data

func _build_character_endings(ending_id: String) -> Array:
	var label := "中性结局"
	match ending_id:
		"righteous_god", "legend_guardian":
			label = "好结局"
		"evil_god":
			label = "坏结局"
		"game_over_incense_out":
			label = "无人记得"
	var result: Array = []
	for character in characters:
		result.append({
			"name": String(character.get("display_name", "居民")),
			"ending": label,
		})
	return result

func _build_key_events() -> Array:
	var result: Array = []
	for event in events:
		result.append(String(event.get("event_name", "未知事件")))
	return result

func _find_by_id(items: Array, id_field: String, id_value: String) -> Dictionary:
	for item in items:
		if item.get(id_field, "") == id_value:
			return item
	return {}

func _load_dictionary(path: String) -> Dictionary:
	var data: Variant = _load_json(path)
	if typeof(data) == TYPE_DICTIONARY:
		return data
	push_warning("Mock dictionary load failed: %s" % path)
	load_error = true
	return {}

func _load_array(path: String) -> Array:
	var data: Variant = _load_json(path)
	if typeof(data) == TYPE_ARRAY:
		return data
	push_warning("Mock array load failed: %s" % path)
	load_error = true
	return []

func _load_json(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		push_warning("Mock file missing: %s" % path)
		return null
	var file := FileAccess.open(path, FileAccess.READ)
	var text := file.get_as_text()
	var parsed: Variant = JSON.parse_string(text)
	if parsed == null:
		push_warning("Mock JSON parse failed: %s" % path)
	return parsed
