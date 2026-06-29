extends PanelContainer
class_name DangerWarningItem

signal clicked(event_id: String, location_id: String)

@onready var icon_label: Label = $Content/IconLabel
@onready var text_label: Label = $Content/TextLabel

var _event_id := ""
var _location_id := ""

func _ready() -> void:
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	gui_input.connect(_on_gui_input)

func setup(event_id: String, location_id: String, message: String, viewed: bool) -> void:
	_event_id = event_id
	_location_id = location_id
	text_label.text = message
	icon_label.text = "✓" if viewed else "⚠"
	add_theme_stylebox_override("panel", _make_style(viewed))

func _on_gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		clicked.emit(_event_id, _location_id)

func _make_style(viewed: bool) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.set_corner_radius_all(4)
	style.set_content_margin_all(8)
	style.set_border_width_all(2)
	if viewed:
		style.bg_color = Color(0.16, 0.18, 0.16, 0.9)
		style.border_color = Color(0.4, 0.55, 0.4, 1.0)
	else:
		style.bg_color = Color(0.3, 0.12, 0.12, 0.92)
		style.border_color = Color(0.85, 0.35, 0.3, 1.0)
	return style
