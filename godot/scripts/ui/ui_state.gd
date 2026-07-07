extends Control
class_name UiState

enum State {
	EMPTY,
	LOADING,
	ERROR,
	CUSTOM
}

signal button_pressed(button_id: String)

@onready var icon_label: Label = $Content/IconLabel
@onready var title_label: Label = $Content/TitleLabel
@onready var message_label: Label = $Content/MessageLabel
@onready var button_container: HBoxContainer = $Content/ButtonContainer

var current_state := State.EMPTY

func _ready() -> void:
	set_empty()

func set_empty(
	title: String = "暂无内容",
	message: String = "选择左侧条目或等待数据加载。",
	icon_text: String = "📭"
) -> void:
	current_state = State.EMPTY
	_show_content(icon_text, title, message)
	_clear_buttons()

func set_loading(
	title: String = "加载中...",
	message: String = "请稍候，命运织线正在整理。",
	icon_text: String = "⏳"
) -> void:
	current_state = State.LOADING
	_show_content(icon_text, title, message)
	_clear_buttons()

func set_error(
	title: String = "加载失败",
	message: String = "命运织线出现了紊乱，请稍后重试。",
	icon_text: String = "⚠️",
	retry_button_text: String = "重试",
	retry_button_id: String = "retry"
) -> void:
	current_state = State.ERROR
	_show_content(icon_text, title, message)
	_clear_buttons()
	_add_button(retry_button_text, retry_button_id)

func set_custom(
	icon_text: String,
	title: String,
	message: String,
	buttons: Array = []
) -> void:
	current_state = State.CUSTOM
	_show_content(icon_text, title, message)
	_clear_buttons()
	for btn in buttons:
		_add_button(btn.get("text", "确定"), btn.get("id", "ok"))

func _show_content(icon: String, title: String, message: String) -> void:
	icon_label.text = icon
	title_label.text = title
	message_label.text = message
	visible = true

func _clear_buttons() -> void:
	for child in button_container.get_children():
		child.queue_free()

func _add_button(text: String, button_id: String) -> void:
	var btn := Button.new()
	btn.text = text
	btn.pressed.connect(func() -> void: button_pressed.emit(button_id))
	button_container.add_child(btn)
