extends PanelContainer
class_name MapLocationTile

signal clicked(location_id: String)

@onready var icon_label: Label = $Content/IconLabel
@onready var name_label: Label = $Content/NameLabel
@onready var portrait_row: HBoxContainer = $Content/PortraitRow

## 地图 tile 上叠加显示的 NPC 头像最大数量（超出显示 +N）
const MAX_PORTRAITS: int = 3
const PORTRAIT_SIZE: int = 32

var location_id: String = ""
var location_data: Dictionary = {}
var has_event: bool = false
var is_setup: bool = false

func _ready() -> void:
	gui_input.connect(_on_gui_input)
	if is_setup:
		_update_ui()

func setup(location: Dictionary, has_active_event: bool = false) -> void:
	location_id = String(location.get("location_id", ""))
	location_data = location
	has_event = has_active_event
	is_setup = true

	if is_node_ready():
		_update_ui()

func _update_ui() -> void:
	name_label.text = String(location_data.get("display_name", "未知"))

	var category: String = String(location_data.get("category", "Daily"))
	match category:
		"Faith", "Religion":
			icon_label.text = "⛩️"
		"Daily":
			icon_label.text = "🏫"
		"Family", "Home":
			icon_label.text = "🏠"
		"Commerce":
			icon_label.text = "⚓"
		"Public":
			icon_label.text = "📢"
		"Nature":
			icon_label.text = "🌲"
		"Shop":
			icon_label.text = "🏪"
		"Work":
			icon_label.text = "🏭"
		"Leisure":
			icon_label.text = "🎮"
		_:
			icon_label.text = "📍"

	if has_event:
		add_theme_stylebox_override("panel", _make_style(Color(0.3, 0.15, 0.15, 0.9), Color(0.85, 0.4, 0.3, 1.0)))
	else:
		add_theme_stylebox_override("panel", _make_style(Color(0.15, 0.18, 0.22, 0.9), Color(0.3, 0.34, 0.4, 1.0)))

	_update_portraits()

## 用当前地点的 NPC 头像堆叠更新 PortraitRow（最多 3 个，超出显示 +N）。
func _update_portraits() -> void:
	if portrait_row == null:
		return
	for child in portrait_row.get_children():
		child.queue_free()
	var ids: Array = location_data.get("present_npc_ids", [])
	var names: Array = location_data.get("present_npc_names", [])
	if ids.is_empty():
		portrait_row.visible = false
		return
	portrait_row.visible = true
	var shown: int = min(ids.size(), MAX_PORTRAITS)
	for i in range(shown):
		var npc_id: String = String(ids[i])
		var display_name: String = String(names[i]) if i < names.size() else npc_id
		portrait_row.add_child(_make_portrait_avatar(npc_id, display_name))
	if ids.size() > MAX_PORTRAITS:
		var more_label := Label.new()
		more_label.text = "+%d" % (ids.size() - MAX_PORTRAITS)
		more_label.add_theme_font_size_override("font_size", 12)
		more_label.add_theme_color_override("font_color", Color(0.85, 0.85, 0.85, 1))
		more_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
		portrait_row.add_child(more_label)

func _make_portrait_avatar(npc_id: String, display_name: String) -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(PORTRAIT_SIZE, PORTRAIT_SIZE)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.set_corner_radius_all(PORTRAIT_SIZE / 2)
	style.set_border_width_all(1)
	style.border_color = Color(0.82, 0.72, 0.48, 0.75)
	style.bg_color = Color(0.09, 0.11, 0.14, 1)
	panel.add_theme_stylebox_override("panel", style)
	panel.tooltip_text = display_name

	var tex: Texture2D = PortraitService.get_portrait(npc_id)
	if tex != null:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		panel.add_child(tr)
	else:
		var initial := Label.new()
		initial.text = PortraitService.get_initial(display_name)
		initial.add_theme_font_size_override("font_size", 14)
		initial.add_theme_color_override("font_color", PortraitService.get_color(npc_id))
		initial.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		initial.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		initial.mouse_filter = Control.MOUSE_FILTER_IGNORE
		initial.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		initial.size_flags_vertical = Control.SIZE_EXPAND_FILL
		panel.add_child(initial)
	return panel

func _make_style(bg: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = bg
	style.set_corner_radius_all(6)
	style.set_content_margin_all(8)
	style.set_border_width_all(2)
	style.border_color = border
	return style

func _on_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_LEFT:
			clicked.emit(location_id)
