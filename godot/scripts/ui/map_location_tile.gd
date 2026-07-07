extends PanelContainer
class_name MapLocationTile

signal clicked(location_id: String)

@onready var icon_label: Label = $Content/IconLabel
@onready var name_label: Label = $Content/NameLabel

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
