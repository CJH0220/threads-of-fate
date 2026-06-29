extends Control

## HUD 主界面控制器。
## 职责：地图渲染、NPC/事件列表切换、详情弹窗、缘线/业线视图路由、时间推进触发、干预执行。
## 结构：顶栏（时间/资源/菜单）+ 主区域（地图）+ 底栏（Tab 按钮 + 列表 + 详情面板）
## 内建覆盖层：BondView / DestinyView / DialogueEventScreen / TimeTransition

signal toast_requested(message: String)
signal return_to_menu_requested()
signal settlement_requested(settlement_data: Dictionary)
signal run_finished(ending_data: Dictionary)
signal week_finished(week_data: Dictionary)

const CHARACTER_PANEL_SCENE: PackedScene = preload("res://scenes/ui/CharacterPanel.tscn")
const EVENT_PANEL_SCENE: PackedScene = preload("res://scenes/ui/EventPanel.tscn")
const LOCATION_PANEL_SCENE: PackedScene = preload("res://scenes/ui/LocationPanel.tscn")
const MAP_LOCATION_TILE_SCENE: PackedScene = preload("res://scenes/ui/MapLocationTile.tscn")
const DANGER_WARNING_ITEM_SCENE: PackedScene = preload("res://scenes/ui/DangerWarningItem.tscn")

## 上下文列表视图模式：NPC 列表
const VIEW_CHARACTERS := "characters"
## 上下文列表视图模式：事件列表
const VIEW_EVENTS := "events"

## 顶栏：当前天/时段显示
@onready var time_label: Label = $Root/TopBar/TimeLabel
## 顶栏：资源数值显示（香火/神力/阳德/阴德）
@onready var resource_label: Label = $Root/TopBar/ResourceLabel
## 地图区域：地点图块容器
@onready var locations_container: Control = $Root/MainArea/MapContent/MapScroll/MapArea/LocationsContainer
## 底栏 Tab：NPC 列表按钮
@onready var characters_tab_button: Button = $Root/BottomPanel/BottomContent/TabButtons/CharactersTabButton
## 底栏 Tab：事件列表按钮
@onready var events_tab_button: Button = $Root/BottomPanel/BottomContent/TabButtons/EventsTabButton
## 底栏 Tab：缘线视图按钮
@onready var bond_view_button: Button = $Root/BottomPanel/BottomContent/TabButtons/BondViewButton
## 底栏 Tab：业线视图按钮
@onready var destiny_view_button: Button = $Root/BottomPanel/BottomContent/TabButtons/DestinyViewButton
## 底栏 Tab：推进时间按钮
@onready var advance_time_button: Button = $Root/BottomPanel/BottomContent/TabButtons/AdvanceTimeButton
## 顶栏：返回主菜单按钮
@onready var menu_button: Button = $Root/TopBar/MenuButton
## 上下文列表容器（NPC/事件列表）
@onready var context_list: VBoxContainer = $Root/BottomPanel/BottomContent/ContextBody/ContextListScroll/ContextListContainer/ContextList
## 详情面板容器（当前选中 NPC/事件的详情）
@onready var detail_panel_container: MarginContainer = $Root/BottomPanel/BottomContent/ContextBody/DetailPanelContainer
## 空/加载/错误状态组件
@onready var detail_state: UiState = $Root/BottomPanel/BottomContent/ContextBody/DetailPanelContainer/DetailState
## 通用详情弹窗（NPC/地点/事件）
@onready var detail_popup: Control = $DetailPopup
## 地图上方：危险事件警告条容器
@onready var danger_warnings: VBoxContainer = $Root/MainArea/MapContent/DangerWarnings
## 确认对话框：未查看危险事件仍要推进时间
@onready var danger_confirm: ConfirmationDialog = $DangerConfirm
## 确认对话框：消耗神力执行干预
@onready var intervention_confirm: ConfirmationDialog = $InterventionConfirm
## 确认对话框：确认返回主菜单
@onready var menu_confirm: ConfirmationDialog = $MenuConfirm
## 缘线视图覆盖层
@onready var bond_view: Control = $BondView
## 业线视图覆盖层
@onready var destiny_view: Control = $DestinyView
## 角色结局界面（从业线进度满触发）
@onready var character_ending_screen: Control = $CharacterEndingScreen
## VN 事件演出界面（从事件详情进入 / Intro 开场）
@onready var dialogue_event_screen: Control = $DialogueEventScreen
## 时间推进过渡动画（织线生长 + 时段变化）
@onready var time_transition: Control = $TimeTransition

## 绑定的游戏状态实例
var state: MockGameState
## 当前上下文列表视图模式（VIEW_CHARACTERS / VIEW_EVENTS）
var active_view := VIEW_CHARACTERS
## 当前选中的 NPC ID
var selected_character_id := ""
## 当前选中的事件 ID
var selected_event_id := ""
## 当前详情面板实例（动态创建）
var current_detail_panel: Control
## 地图地点图块实例数组
var location_tiles: Array = []
## 已查看的危险事件 ID 集合（避免重复警告）
var viewed_danger_event_ids: Dictionary = {}
## 待确认干预的事件 ID
var _pending_intervention_event_id := ""
## 待确认干预的干预 ID
var _pending_intervention_id := ""
## 时间推进防重入标记
var _advancing := false

func _ready() -> void:
	# 连接 Tab 切换信号
	characters_tab_button.pressed.connect(func() -> void: _open_characters())
	events_tab_button.pressed.connect(func() -> void: _open_events())
	# 连接缘线/业线视图按钮
	bond_view_button.pressed.connect(func() -> void: bond_view.open(state.get_characters()))
	destiny_view_button.pressed.connect(func() -> void: destiny_view.open(state.get_characters()))
	# 连接时间推进和主菜单按钮
	advance_time_button.pressed.connect(_advance_time)
	menu_button.pressed.connect(func() -> void: menu_confirm.popup_centered())
	menu_confirm.confirmed.connect(func() -> void: return_to_menu_requested.emit())
	danger_confirm.confirmed.connect(_do_advance_time)
	intervention_confirm.confirmed.connect(_on_intervention_confirmed)
	detail_state.button_pressed.connect(_on_detail_state_button)
	bond_view.character_selected.connect(_on_view_character_selected)
	destiny_view.character_selected.connect(_on_view_character_selected)
	destiny_view.ending_requested.connect(_on_view_ending_requested)

func bind_state(next_state: MockGameState) -> void:
	state = next_state
	state.state_changed.connect(_refresh)
	_refresh()

func _refresh() -> void:
	if state == null:
		return
	var game_state: Dictionary = state.get_game_state()
	time_label.text = "第 %d 天 · %s" % [game_state.get("day", 1), game_state.get("time_slot_label", "早上")]
	resource_label.text = "香火 %d  神力 %d  阳德 %d  阴德 %d" % [
		game_state.get("incense", 0),
		game_state.get("divine_power", 0),
		game_state.get("yang_de", 0),
		game_state.get("yin_de", 0),
	]
	_refresh_map_locations()
	_refresh_danger_warnings()
	_update_tab_highlight()
	match active_view:
		VIEW_CHARACTERS:
			_show_characters()
		VIEW_EVENTS:
			_show_events()
	_update_detail_state()

func _update_detail_state() -> void:
	if state.has_load_error():
		detail_state.set_error("数据读取失败", "镇上的命运档案似乎损坏了，请重试。", "⚠️")
		return
	match active_view:
		VIEW_CHARACTERS:
			if state.get_characters().is_empty():
				detail_state.set_empty("尚无居民", "命运尚未在此展开居民。", "🙍")
			else:
				detail_state.set_empty("尚未选择居民", "点击左侧或地图上的居民查看命运。", "🙍")
		VIEW_EVENTS:
			if state.get_events().is_empty():
				detail_state.set_empty("此刻风平浪静", "当前时段没有可查看事件。", "🌊")
			else:
				detail_state.set_empty("尚未选择事件", "点击左侧事件查看详情。", "📜")

func _on_detail_state_button(button_id: String) -> void:
	if button_id == "retry":
		state.reset_to_new_game()

func _update_tab_highlight() -> void:
	characters_tab_button.button_pressed = (active_view == VIEW_CHARACTERS)
	events_tab_button.button_pressed = (active_view == VIEW_EVENTS)

func _refresh_map_locations() -> void:
	for tile in location_tiles:
		tile.queue_free()
	location_tiles.clear()

	var locations: Array = state.get_locations()
	var events: Array = state.get_events()
	var location_events_map: Dictionary = {}

	for event in events:
		var loc_id: String = String(event.get("location_id", ""))
		if not location_events_map.has(loc_id):
			location_events_map[loc_id] = []
		var event_array: Array = location_events_map[loc_id]
		event_array.append(event)

	var positions: Array[Vector2] = [
		Vector2(200, 150),
		Vector2(450, 100),
		Vector2(700, 150),
		Vector2(950, 100),
		Vector2(300, 350),
		Vector2(550, 300),
		Vector2(800, 350),
		Vector2(1050, 300),
		Vector2(400, 550),
		Vector2(650, 500),
		Vector2(900, 550),
		Vector2(500, 750),
		Vector2(750, 700),
		Vector2(1000, 750),
		Vector2(600, 950),
	]

	var max_count: int = min(locations.size(), positions.size())
	for i in range(max_count):
		var location: Dictionary = locations[i]
		var loc_id: String = String(location.get("location_id", ""))
		var events_at_loc: Array = location_events_map.get(loc_id, [])
		var has_event: bool = not events_at_loc.is_empty()

		var tile: MapLocationTile = MAP_LOCATION_TILE_SCENE.instantiate()
		tile.setup(location, has_event)
		tile.position = positions[i]
		tile.clicked.connect(_on_location_tile_clicked)
		locations_container.add_child(tile)
		location_tiles.append(tile)

func _on_location_tile_clicked(location_id: String) -> void:
	_show_location_popup(location_id)

func _is_danger_event(event: Dictionary) -> bool:
	var risk: String = String(event.get("risk_level", "Low"))
	return risk == "High" or risk == "Fatal"

func _danger_events() -> Array:
	var result: Array = []
	for event in state.get_events():
		if _is_danger_event(event):
			result.append(event)
	return result

func _unviewed_danger_events() -> Array:
	var result: Array = []
	for event in _danger_events():
		var event_id: String = String(event.get("event_id", ""))
		if not viewed_danger_event_ids.has(event_id):
			result.append(event)
	return result

func _refresh_danger_warnings() -> void:
	for child in danger_warnings.get_children():
		child.queue_free()
	var dangers: Array = _danger_events()
	danger_warnings.visible = not dangers.is_empty()
	for event in dangers:
		var event_id: String = String(event.get("event_id", ""))
		var location_id: String = String(event.get("location_id", ""))
		var viewed: bool = viewed_danger_event_ids.has(event_id)
		var item: DangerWarningItem = DANGER_WARNING_ITEM_SCENE.instantiate()
		danger_warnings.add_child(item)
		item.setup(event_id, location_id, _danger_message(event, viewed), viewed)
		item.clicked.connect(_on_danger_warning_clicked)

func _danger_message(event: Dictionary, viewed: bool) -> String:
	var location_label: String = String(event.get("location_label", "镇上某处"))
	if viewed:
		return "%s 的危险征兆已查看" % location_label
	return "%s 出现危险征兆，建议尽快查看" % location_label

func _on_danger_warning_clicked(event_id: String, _location_id: String) -> void:
	viewed_danger_event_ids[event_id] = true
	_select_event(event_id)
	_refresh_danger_warnings()

func _open_characters(selected_id := "") -> void:
	selected_character_id = selected_id
	active_view = VIEW_CHARACTERS
	selected_event_id = ""
	_show_characters()  # 内部已包含 _clear_context_list()

func _open_events(selected_id := "") -> void:
	selected_event_id = selected_id
	active_view = VIEW_EVENTS
	selected_character_id = ""
	_show_events()  # 内部已包含 _clear_context_list()

func _show_characters() -> void:
	_clear_context_list()  # 必须先清空，否则推进时间会重复添加
	var characters: Array = state.get_characters()
	if characters.is_empty():
		return
	if selected_character_id == "":
		var first_char: Dictionary = characters[0]
		selected_character_id = String(first_char.get("npc_id", ""))
	for character in characters:
		var npc_id: String = String(character.get("npc_id", ""))
		var button: Button = Button.new()
		var display_name: String = String(character.get("display_name", "未知居民"))
		var prefix: String = "▶ " if npc_id == selected_character_id else ""
		button.text = "%s%s" % [prefix, display_name]
		button.pressed.connect(func() -> void: _select_character(npc_id))
		context_list.add_child(button)

func _select_character(npc_id: String) -> void:
	selected_character_id = npc_id
	_show_character_popup(npc_id)
	_open_characters(npc_id)

func _on_view_character_selected(npc_id: String) -> void:
	bond_view.close()
	destiny_view.close()
	_select_character(npc_id)

func _on_view_ending_requested(npc_id: String) -> void:
	character_ending_screen.open(state.get_character_ending(npc_id))

func _show_character_popup(character_id: String) -> void:
	var character: Dictionary = state.find_character(character_id)
	if character.is_empty():
		return

	detail_popup.call("show_popup", "人物详情")
	var panel: Control = CHARACTER_PANEL_SCENE.instantiate()
	detail_popup.call("add_child_node", panel)
	panel.call("show_character", character, Callable(func(location_id: String) -> String: return state.get_location_label(location_id)))

func _show_location_popup(location_id: String) -> void:
	var location: Dictionary = state.find_location(location_id)
	if location.is_empty():
		return

	detail_popup.call("show_popup", "地点详情")
	var panel: LocationPanel = LOCATION_PANEL_SCENE.instantiate()
	detail_popup.call("add_child_node", panel)
	panel.show_location(
		location,
		Callable(func(slot_id: String) -> String: return state.get_time_slot_label(slot_id)),
		_format_characters_at_location,
		_events_at_location
	)

func _show_events() -> void:
	_clear_context_list()  # 必须先清空，否则推进时间会重复添加
	var events: Array = state.get_events()
	if events.is_empty():
		return
	if selected_event_id == "":
		var first_event: Dictionary = events[0]
		selected_event_id = String(first_event.get("event_id", ""))
	for event in events:
		var event_id: String = String(event.get("event_id", ""))
		var event_button: Button = Button.new()
		var prefix: String = "▶ " if event_id == selected_event_id else ""
		var event_name: String = String(event.get("event_name", "未知事件"))
		event_button.text = "%s%s" % [prefix, event_name]
		event_button.pressed.connect(func() -> void: _select_event(event_id))
		context_list.add_child(event_button)

func _select_event(event_id: String) -> void:
	selected_event_id = event_id
	_show_event_popup(event_id)
	_open_events(event_id)

func _show_event_popup(event_id: String) -> void:
	var event: Dictionary = _find_event(event_id)
	if event.is_empty():
		return

	if _is_danger_event(event) and not viewed_danger_event_ids.has(event_id):
		viewed_danger_event_ids[event_id] = true
		_refresh_danger_warnings()

	detail_popup.call("show_popup", "事件详情")
	var panel: Control = EVENT_PANEL_SCENE.instantiate()
	detail_popup.call("add_child_node", panel)

	var event_interventions: Array = state.get_interventions_for_event(event)
	var game_dict: Dictionary = state.get_game_state()
	var divine_power: int = int(game_dict.get("divine_power", 0))

	panel.call("show_event", event, event_interventions, divine_power)
	if panel.has_signal("intervention_applied") and not panel.intervention_applied.is_connected(_on_intervention_applied):
		panel.intervention_applied.connect(_on_intervention_applied)
	if panel.has_signal("enter_requested") and not panel.enter_requested.is_connected(_on_event_enter_requested):
		panel.enter_requested.connect(_on_event_enter_requested)

func _on_event_enter_requested(event_id: String) -> void:
	var event: Dictionary = _find_event(event_id)
	if event.is_empty():
		return
	detail_popup.call("hide_popup")
	if not dialogue_event_screen.finished.is_connected(_on_dialogue_finished):
		dialogue_event_screen.finished.connect(_on_dialogue_finished)
	dialogue_event_screen.open(event)

func _on_dialogue_finished() -> void:
	# 演出结束后回到事件详情，保留干预入口。
	_show_event_popup(selected_event_id)

func _find_event(event_id: String) -> Dictionary:
	for event in state.get_events():
		var evt_id: String = String(event.get("event_id", ""))
		if evt_id == event_id:
			return event
	return {}

func _clear_context_list() -> void:
	# 先移除所有子节点再删除，确保立即生效，避免推进时间时列表重复
	for child in context_list.get_children():
		context_list.remove_child(child)
		child.queue_free()

func _format_characters_at_location(location_id: String, slot_id: String) -> String:
	var names: Array[String] = []
	for character in state.get_characters():
		var schedule: Dictionary = character.get("schedule", {})
		var slot_value: String = String(schedule.get(slot_id, ""))
		if slot_value == location_id:
			var display_name: String = String(character.get("display_name", "未知居民"))
			names.append(display_name)
	if names.is_empty():
		return "无人停留"
	return "、".join(names)

func _events_at_location(location_id: String) -> Array:
	var result: Array = []
	for event in state.get_events():
		var event_loc_id: String = String(event.get("location_id", ""))
		if event_loc_id == location_id:
			result.append(event)
	return result

func _find_intervention(event: Dictionary, intervention_id: String) -> Dictionary:
	for intervention in state.get_interventions_for_event(event):
		if String(intervention.get("intervention_id", "")) == intervention_id:
			return intervention
	return {}

func _on_intervention_applied(event_id: String, intervention_id: String) -> void:
	var event: Dictionary = _find_event(event_id)
	if event.is_empty():
		return
	var intervention: Dictionary = _find_intervention(event, intervention_id)
	var display_name: String = String(intervention.get("display_name", "干预"))
	var cost: int = int(intervention.get("cost_divine_power", 0))
	_pending_intervention_event_id = event_id
	_pending_intervention_id = intervention_id
	intervention_confirm.dialog_text = "确认消耗 %d 点神力进行【%s】吗？\n命运只会被轻推，结果未必如愿。" % [cost, display_name]
	intervention_confirm.popup_centered()

func _on_intervention_confirmed() -> void:
	var event_id: String = _pending_intervention_event_id
	var intervention_id: String = _pending_intervention_id
	_pending_intervention_event_id = ""
	_pending_intervention_id = ""
	if event_id == "" or intervention_id == "":
		return

	detail_popup.call("hide_popup")
	var result: Dictionary = state.apply_intervention(event_id, intervention_id)
	if bool(result.get("success", false)):
		var event: Dictionary = _find_event(event_id)
		var event_name: String = String(event.get("event_name", "未知事件") if not event.is_empty() else "未知事件")
		var settlement_data: Dictionary = {
			"title": "干预结算",
			"summary": result.get("summary", "命运线产生了变化。"),
			"resource_delta": result.get("resource_delta", {}),
			"character_changes": [],
			"event_changes": [
				{
					"event_name": event_name,
					"outcome": "已干预"
				}
			]
		}
		settlement_requested.emit(settlement_data)
	else:
		toast_requested.emit(result.get("summary", "干预失败。"))

func _advance_time() -> void:
	var unviewed: Array = _unviewed_danger_events()
	if not unviewed.is_empty():
		danger_confirm.dialog_text = "仍有 %d 处危险征兆尚未查看，确定要推进时间吗？" % unviewed.size()
		danger_confirm.popup_centered()
		return
	_do_advance_time()

func _do_advance_time() -> void:
	if _advancing:
		return
	_advancing = true
	viewed_danger_event_ids.clear()

	var before_state: Dictionary = state.get_game_state()
	var before_label: String = "第 %d 天 · %s" % [before_state.get("day", 1), before_state.get("time_slot_label", "早上")]

	var result: Dictionary = state.advance_time()

	var after_state: Dictionary = state.get_game_state()
	var after_label: String = "第 %d 天 · %s" % [after_state.get("day", 1), after_state.get("time_slot_label", "早上")]

	await time_transition.play(before_label, after_label)
	_advancing = false

	if bool(result.get("run_finished", false)):
		run_finished.emit(result.get("ending", {}))
		return
	if bool(result.get("week_finished", false)):
		week_finished.emit(result.get("week_data", {}))
		return
	var settlement_data: Dictionary = {
		"title": "时间结算",
		"summary": result.get("summary", "时间已推进，命运线产生了新的变化。"),
		"resource_delta": result.get("resource_delta", {}),
		"character_changes": [],
		"event_changes": []
	}
	settlement_requested.emit(settlement_data)
