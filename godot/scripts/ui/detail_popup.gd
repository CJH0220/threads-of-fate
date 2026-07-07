extends PanelContainer
class_name DetailPopup

signal closed()

@onready var title_label: Label = $CenterContainer/MainPanel/VBoxContainer/HeaderBar/TitleLabel
@onready var content_container: VBoxContainer = $CenterContainer/MainPanel/VBoxContainer/ContentScroll/ContentContainer
@onready var close_button: Button = $CenterContainer/MainPanel/VBoxContainer/HeaderBar/CloseButton
@onready var overlay: ColorRect = $Overlay

func _ready() -> void:
	close_button.pressed.connect(_on_close_pressed)
	overlay.gui_input.connect(_on_overlay_input)

func show_popup(title: String = "详情") -> void:
	_clear_content()
	title_label.text = title
	visible = true

func hide_popup() -> void:
	visible = false
	_clear_content()

func _clear_content() -> void:
	for child in content_container.get_children():
		child.queue_free()

func add_label(text: String, autowrap: bool = true) -> Label:
	var label := Label.new()
	label.text = text
	if autowrap:
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	content_container.add_child(label)
	return label

func add_separator() -> HSeparator:
	var separator := HSeparator.new()
	content_container.add_child(separator)
	return separator

func add_button(text: String) -> Button:
	var button := Button.new()
	button.text = text
	content_container.add_child(button)
	return button

func add_child_node(node: Node) -> void:
	content_container.add_child(node)

func _on_close_pressed() -> void:
	hide_popup()
	closed.emit()

func _on_overlay_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		hide_popup()
		closed.emit()
