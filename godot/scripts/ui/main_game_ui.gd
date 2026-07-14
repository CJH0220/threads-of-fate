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
@onready var time_label: Label = $Root/TopBar/H/TimeLabel
## 顶栏：资源数值显示（香火/神力/阳德/阴德）
@onready var resource_label: Label = $Root/TopBar/H/ResourceLabel
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
@onready var menu_button: Button = $Root/TopBar/H/MenuButton
## 上下文列表容器（NPC/事件横向卡片列表）
@onready var context_list: HBoxContainer = $Root/BottomPanel/BottomContent/ContextBody/ContextList
## 上下文列表标题（当前 Tab 名称）
@onready var context_title: Label = $Root/BottomPanel/BottomContent/ContextTitleRow/ContextTitle
## 上下文列表副提示
@onready var context_hint: Label = $Root/BottomPanel/BottomContent/ContextTitleRow/ContextHint
## 通用详情弹窗（NPC/地点/事件）
@onready var detail_popup: Control = $DetailPopup
## 地图上方：危险事件警告条容器（横向紧凑筹码）
@onready var danger_warnings: HBoxContainer = $Root/MainArea/MapContent/DangerWarnings
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
## 托梦文字输入弹窗
@onready var dream_text_dialog: Control = $DreamTextDialog
@onready var npc_chat_dialog: Control = $NpcChatDialog

## 绑定的游戏状态实例（可能是 MockGameState 或 BackendGameState —
## 两者签名一致，通过鸭子类型互换，故静态类型放宽为 RefCounted）
var state: RefCounted
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
## 当前打开的详情弹窗类型："" | "character" | "event"
var _open_popup_kind := ""
## 当前打开的详情弹窗目标 ID（npc_id 或 event_id）
var _open_popup_target_id := ""
## 待确认托梦的目标 NPC ID（角色框托梦入口发起）
var _pending_dream_npc_id := ""
## 待确认托梦的目标 NPC 显示名
var _pending_dream_display_name := ""
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
	dream_text_dialog.connect("confirmed", _on_dream_text_confirmed)
	dream_text_dialog.connect("cancelled", _on_dream_text_cancelled)
	detail_popup.connect("closed", _on_detail_popup_closed)
	bond_view.character_selected.connect(_on_view_character_selected)
	destiny_view.character_selected.connect(_on_view_character_selected)
	destiny_view.ending_requested.connect(_on_view_ending_requested)

	# 后端故事编排 Agent（土地公旁白）：仅在真实后端接入时才有信号
	var backend: Node = get_node_or_null("/root/Backend")
	if backend != null and backend.has_signal("narrator_beat"):
		if not backend.narrator_beat.is_connected(_on_narrator_beat):
			backend.narrator_beat.connect(_on_narrator_beat)

func bind_state(next_state: RefCounted) -> void:
	state = next_state
	state.state_changed.connect(_refresh)
	if state.has_signal("npc_updated") and not state.is_connected("npc_updated", _on_state_npc_updated):
		state.connect("npc_updated", _on_state_npc_updated)
	if state.has_signal("event_completed") and not state.is_connected("event_completed", _on_state_event_completed):
		state.connect("event_completed", _on_state_event_completed)
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

func _update_tab_highlight() -> void:
	characters_tab_button.button_pressed = (active_view == VIEW_CHARACTERS)
	events_tab_button.button_pressed = (active_view == VIEW_EVENTS)
	if context_title != null:
		context_title.text = "人物" if active_view == VIEW_CHARACTERS else "事件"
	if context_hint != null:
		if active_view == VIEW_CHARACTERS:
			context_hint.text = "· 点击卡片查看命运"
		else:
			context_hint.text = "· 点击卡片查看事件"

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
		return "%s 已阅" % location_label
	return location_label

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
	_clear_context_list()
	var characters: Array = state.get_characters()
	if characters.is_empty():
		_add_empty_placeholder("🙍 命运尚未在此展开居民。")
		return
	if selected_character_id == "":
		var first_char: Dictionary = characters[0]
		selected_character_id = String(first_char.get("npc_id", ""))
	for character in characters:
		var npc_id: String = String(character.get("npc_id", ""))
		var display_name: String = String(character.get("display_name", "未知居民"))
		var role_text: String = String(character.get("role", ""))
		var card := _make_character_card(npc_id, display_name, role_text, npc_id == selected_character_id)
		context_list.add_child(card)

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

	_open_popup_kind = "character"
	_open_popup_target_id = character_id
	detail_popup.call("show_popup", "人物详情")
	var panel: Control = CHARACTER_PANEL_SCENE.instantiate()
	detail_popup.call("add_child_node", panel)
	var dream_ctx: Dictionary = _build_dream_ctx()
	panel.call(
		"show_character",
		character,
		Callable(func(location_id: String) -> String: return state.get_location_label(location_id)),
		dream_ctx,
	)
	if panel.has_signal("chat_requested"):
		panel.connect("chat_requested", _on_character_chat_requested)
	if panel.has_signal("dream_requested"):
		panel.connect("dream_requested", _on_character_dream_requested)

## 构造 CharacterPanel 需要的托梦上下文。dream_cost 与 mock/interventions.json 保持一致。
func _build_dream_ctx() -> Dictionary:
	if state == null:
		return {}
	var game_dict: Dictionary = state.get_game_state()
	var dream_cost: int = 3
	if "DREAM_COST" in state:
		dream_cost = int(state.DREAM_COST)
	var used_today: bool = false
	if "dream_used_today" in state:
		used_today = bool(state.dream_used_today)
	return {
		"time_slot": String(game_dict.get("time_slot", "Morning")),
		"divine_power": int(game_dict.get("divine_power", 0)),
		"dream_used_today": used_today,
		"dream_cost": dream_cost,
	}

func _on_character_chat_requested(npc_id: String, display_name: String) -> void:
	if npc_id == "":
		return
	var backend: Node = get_node_or_null("/root/Backend")
	if backend == null or backend.use_mock_fallback:
		toast_requested.emit("离线模式无法呼唤 %s。" % display_name)
		return
	detail_popup.call("hide_popup")
	_open_popup_kind = ""
	_open_popup_target_id = ""
	var game_state: Dictionary = state.get_game_state()
	var day: int = int(game_state.get("day", 1))
	npc_chat_dialog.call("open", npc_id, display_name, day)

func _on_narrator_beat(payload: Dictionary) -> void:
	var text: String = String(payload.get("text", "")).strip_edges()
	if text == "":
		return
	var day: int = int(payload.get("day", 0))
	if day > 0:
		toast_requested.emit("土地公（第 %d 夜）：%s" % [day, text])
	else:
		toast_requested.emit("土地公：%s" % text)

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
	_clear_context_list()
	var events: Array = state.get_events()
	if events.is_empty():
		_add_empty_placeholder("🌊 此刻风平浪静，无事发生。")
		return
	if selected_event_id == "":
		var first_event: Dictionary = events[0]
		selected_event_id = String(first_event.get("event_id", ""))
	for event in events:
		var event_id: String = String(event.get("event_id", ""))
		var event_name: String = String(event.get("event_name", "未知事件"))
		var location_id: String = String(event.get("location_id", ""))
		var location_label: String = String(event.get("location_label", state.get_location_label(location_id)))
		var risk: String = String(event.get("risk_level", "Low"))
		var is_completed: bool = state.has_method("is_event_completed") and state.is_event_completed(event_id)
		var card := _make_event_card(event_id, event_name, location_id, location_label, risk, event_id == selected_event_id, is_completed)
		context_list.add_child(card)

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

	_open_popup_kind = "event"
	_open_popup_target_id = event_id
	detail_popup.call("show_popup", "事件详情")
	var panel: Control = EVENT_PANEL_SCENE.instantiate()
	detail_popup.call("add_child_node", panel)

	var is_completed: bool = false
	if state.has_method("is_event_completed"):
		is_completed = bool(state.is_event_completed(event_id))
	var snapshot: Dictionary = {}
	if state.has_method("get_event_snapshot"):
		snapshot = state.get_event_snapshot(event_id)

	panel.call("show_event", event, is_completed, snapshot)
	if panel.has_signal("enter_requested") and not panel.enter_requested.is_connected(_on_event_enter_requested):
		panel.enter_requested.connect(_on_event_enter_requested)

func _on_event_enter_requested(event_id: String) -> void:
	var event: Dictionary = _find_event(event_id)
	if event.is_empty():
		return
	detail_popup.call("hide_popup")
	_open_popup_kind = ""
	_open_popup_target_id = ""
	if not dialogue_event_screen.finished.is_connected(_on_dialogue_finished):
		dialogue_event_screen.finished.connect(_on_dialogue_finished)
	dialogue_event_screen.open(event, state)

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

## 底栏空态占位（居中文字）。
func _add_empty_placeholder(text: String) -> void:
	var label := Label.new()
	label.text = text
	label.add_theme_color_override("font_color", Color(0.72, 0.75, 0.82, 1))
	label.add_theme_font_size_override("font_size", 14)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	label.custom_minimum_size = Vector2(320, 0)
	context_list.add_child(label)

const CARD_CHAR_W: int = 96
const CARD_CHAR_H: int = 118
const CARD_EVENT_W: int = 176
const CARD_EVENT_H: int = 118

## 人物卡片：竖排头像 + 姓名 + 身份，选中态加高亮边框。
func _make_character_card(npc_id: String, display_name: String, role_text: String, is_selected: bool) -> Control:
	var button := Button.new()
	button.custom_minimum_size = Vector2(CARD_CHAR_W, CARD_CHAR_H)
	button.tooltip_text = "%s · %s" % [display_name, role_text] if role_text != "" else display_name
	button.focus_mode = Control.FOCUS_NONE
	button.add_theme_stylebox_override("normal", _make_card_style(is_selected))
	button.add_theme_stylebox_override("hover", _make_card_style(true))
	button.add_theme_stylebox_override("pressed", _make_card_style(true))
	button.add_theme_stylebox_override("focus", _make_card_style(is_selected))

	var vbox := VBoxContainer.new()
	vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	vbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vbox.add_theme_constant_override("separation", 4)
	vbox.alignment = BoxContainer.ALIGNMENT_CENTER
	button.add_child(vbox)

	## 头像圆框（56×56）
	const AV: int = 56
	var portrait_panel := PanelContainer.new()
	portrait_panel.custom_minimum_size = Vector2(AV, AV)
	portrait_panel.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	portrait_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var pstyle := StyleBoxFlat.new()
	pstyle.set_corner_radius_all(AV / 2)
	pstyle.set_border_width_all(1)
	pstyle.border_color = Color(0.82, 0.72, 0.48, 0.85)
	pstyle.bg_color = Color(0.09, 0.11, 0.14, 1)
	portrait_panel.add_theme_stylebox_override("panel", pstyle)
	var tex: Texture2D = PortraitService.get_portrait(npc_id)
	if tex != null:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		portrait_panel.add_child(tr)
	else:
		var initial := Label.new()
		initial.text = PortraitService.get_initial(display_name)
		initial.add_theme_font_size_override("font_size", 24)
		initial.add_theme_color_override("font_color", PortraitService.get_color(npc_id))
		initial.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		initial.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		initial.mouse_filter = Control.MOUSE_FILTER_IGNORE
		initial.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		initial.size_flags_vertical = Control.SIZE_EXPAND_FILL
		portrait_panel.add_child(initial)
	vbox.add_child(portrait_panel)

	var name_label := Label.new()
	name_label.text = display_name
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.add_theme_font_size_override("font_size", 13)
	name_label.add_theme_color_override("font_color", Color(1, 0.92, 0.7, 1))
	name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vbox.add_child(name_label)

	if role_text != "":
		var role_label := Label.new()
		role_label.text = role_text
		role_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		role_label.add_theme_font_size_override("font_size", 11)
		role_label.add_theme_color_override("font_color", Color(0.75, 0.8, 0.88, 1))
		role_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		vbox.add_child(role_label)

	button.pressed.connect(func() -> void: _select_character(npc_id))
	return button

## 事件卡片：地点图标 + 事件名 + 地点标签 + 风险等级色标。
## is_completed=true 时降饱和度并把风险标签替换为「✓ 已完成」。
func _make_event_card(event_id: String, event_name: String, location_id: String, location_label: String, risk: String, is_selected: bool, is_completed: bool = false) -> Control:
	var button := Button.new()
	button.custom_minimum_size = Vector2(CARD_EVENT_W, CARD_EVENT_H)
	var tooltip_suffix: String = "  · 已演出" if is_completed else ""
	button.tooltip_text = "%s · %s · %s%s" % [event_name, location_label, risk, tooltip_suffix]
	button.focus_mode = Control.FOCUS_NONE
	var border: Color = Color(0.55, 0.72, 0.6, 1) if is_completed else _risk_border_color(risk)
	button.add_theme_stylebox_override("normal", _make_card_style(is_selected, border))
	button.add_theme_stylebox_override("hover", _make_card_style(true, border))
	button.add_theme_stylebox_override("pressed", _make_card_style(true, border))
	button.add_theme_stylebox_override("focus", _make_card_style(is_selected, border))
	if is_completed:
		button.modulate = Color(0.78, 0.82, 0.85, 1)

	var vbox := VBoxContainer.new()
	vbox.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	vbox.add_theme_constant_override("separation", 4)
	vbox.mouse_filter = Control.MOUSE_FILTER_IGNORE
	button.add_child(vbox)

	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 6)
	top_row.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var icon_label := Label.new()
	icon_label.text = _location_icon(location_id, location_label)
	icon_label.add_theme_font_size_override("font_size", 22)
	icon_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top_row.add_child(icon_label)

	var name_label := Label.new()
	name_label.text = event_name
	name_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	name_label.add_theme_font_size_override("font_size", 14)
	name_label.add_theme_color_override("font_color", Color(1, 0.92, 0.7, 1))
	name_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	name_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	name_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	top_row.add_child(name_label)
	vbox.add_child(top_row)

	var meta_row := HBoxContainer.new()
	meta_row.add_theme_constant_override("separation", 6)
	meta_row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var loc_label := Label.new()
	loc_label.text = location_label
	loc_label.add_theme_font_size_override("font_size", 11)
	loc_label.add_theme_color_override("font_color", Color(0.75, 0.8, 0.88, 1))
	loc_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	loc_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	meta_row.add_child(loc_label)

	var risk_label := Label.new()
	if is_completed:
		risk_label.text = "✓ 已完成"
		risk_label.add_theme_color_override("font_color", Color(0.6, 0.85, 0.7, 1))
	else:
		risk_label.text = risk
		risk_label.add_theme_color_override("font_color", _risk_border_color(risk))
	risk_label.add_theme_font_size_override("font_size", 11)
	risk_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	meta_row.add_child(risk_label)
	vbox.add_child(meta_row)

	button.pressed.connect(func() -> void: _select_event(event_id))
	return button

func _make_card_style(highlighted: bool, override_border: Color = Color(0, 0, 0, 0)) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.09, 0.11, 0.14, 0.95) if not highlighted else Color(0.16, 0.14, 0.10, 1)
	style.set_corner_radius_all(6)
	style.set_border_width_all(2 if highlighted else 1)
	if override_border.a > 0.01:
		style.border_color = override_border if highlighted else Color(override_border.r, override_border.g, override_border.b, 0.5)
	else:
		style.border_color = Color(1, 0.85, 0.5, 0.95) if highlighted else Color(0.82, 0.72, 0.48, 0.35)
	style.set_content_margin_all(8)
	return style

func _risk_border_color(risk: String) -> Color:
	match risk:
		"Fatal", "Critical":
			return Color(0.9, 0.4, 0.35, 1)
		"High":
			return Color(0.92, 0.6, 0.35, 1)
		"Medium":
			return Color(0.85, 0.8, 0.4, 1)
		_:
			return Color(0.55, 0.75, 0.6, 1)

func _location_icon(location_id: String, _location_label: String) -> String:
	var loc: Dictionary = state.find_location(location_id) if location_id != "" else {}
	var category: String = String(loc.get("category", ""))
	match category:
		"Faith", "Religion":
			return "⛩️"
		"Daily":
			return "🏫"
		"Family", "Home":
			return "🏠"
		"Commerce":
			return "⚓"
		"Public":
			return "📢"
		"Nature":
			return "🌲"
		"Shop":
			return "🏪"
		"Work":
			return "🏭"
		"Leisure":
			return "🎮"
		_:
			return "📍"

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

func _on_character_dream_requested(npc_id: String, display_name: String) -> void:
	if npc_id == "":
		return
	_pending_dream_npc_id = npc_id
	_pending_dream_display_name = display_name
	dream_text_dialog.call("open", display_name)

func _on_dream_text_confirmed(dream_text: String) -> void:
	var npc_id: String = _pending_dream_npc_id
	var display_name: String = _pending_dream_display_name
	_pending_dream_npc_id = ""
	_pending_dream_display_name = ""
	if npc_id == "":
		return
	if not state.has_method("apply_dream"):
		toast_requested.emit("此适配器暂不支持托梦。")
		return
	var result: Dictionary = state.apply_dream(npc_id, dream_text)
	if bool(result.get("success", false)):
		var summary: String = String(result.get("summary", "梦已递出。"))
		toast_requested.emit("托梦 · %s：%s" % [display_name, summary])
	else:
		toast_requested.emit(String(result.get("summary", "托梦未能奏效。")))

func _on_dream_text_cancelled() -> void:
	_pending_dream_npc_id = ""
	_pending_dream_display_name = ""

## 详情弹窗关闭时清空跟踪状态，供 npc_updated / event_completed 判断是否需要刷新。
func _on_detail_popup_closed() -> void:
	_open_popup_kind = ""
	_open_popup_target_id = ""

## 角色数据发生变化：若当前弹窗正显示该角色，则重建面板以刷新头像/羁绊/托梦状态。
func _on_state_npc_updated(npc_id: String) -> void:
	if _open_popup_kind == "character" and _open_popup_target_id == npc_id:
		_show_character_popup(npc_id)

## 事件演出完成：刷新事件卡列表 + 若弹窗正显示该事件则重建为回看态；给一条提示。
func _on_state_event_completed(event_id: String, _snapshot: Dictionary) -> void:
	var event: Dictionary = _find_event(event_id)
	var event_name: String = String(event.get("event_name", "该事件") if not event.is_empty() else "该事件")
	toast_requested.emit("%s · 演出已定" % event_name)
	if active_view == VIEW_EVENTS:
		_show_events()
	if _open_popup_kind == "event" and _open_popup_target_id == event_id:
		_show_event_popup(event_id)

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

	## 真实后端路径为异步（内部 await settlement_complete）；Mock 路径 await 会立即返回。
	## state 静态类型为 MockGameState，静态分析器看不到 BackendGameState 的 await，
	## 此处 await 在运行时对两种适配器都必要。
	@warning_ignore("redundant_await")
	var result: Dictionary = await state.advance_time()

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
