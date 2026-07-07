extends Control

## 教程提示覆盖层。首次接触关键系统时显示简短说明。
## 显示状态由 TutorialState autoload 持久化；「不再提示」全局关闭后续教程。
## MVP：静态高亮（不做闪烁动效），点空白 / 知道了 关闭并记录已看。

@onready var dim: ColorRect = $Dim
@onready var highlight_frame: Panel = $HighlightFrame
@onready var title_label: Label = $TooltipPanel/VBox/TitleLabel
@onready var body_text: Label = $TooltipPanel/VBox/BodyText
@onready var ok_button: Button = $TooltipPanel/VBox/ButtonRow/OkButton
@onready var dont_show_button: Button = $TooltipPanel/VBox/ButtonRow/DontShowButton

var _current_id := ""

func _ready() -> void:
	visible = false
	ok_button.pressed.connect(_on_ok)
	dont_show_button.pressed.connect(_on_dont_show)
	dim.gui_input.connect(_on_dim_input)

## 若该教程尚未看过且未全局关闭，则显示。target_rect 为空时不显示高亮框。
func try_show(tutorial_id: String, title: String, body: String, target_rect: Rect2 = Rect2()) -> bool:
	if not TutorialState.should_show(tutorial_id):
		return false
	_current_id = tutorial_id
	title_label.text = title
	body_text.text = body
	if target_rect.size == Vector2.ZERO:
		highlight_frame.visible = false
	else:
		highlight_frame.visible = true
		highlight_frame.position = target_rect.position
		highlight_frame.size = target_rect.size
	visible = true
	ok_button.grab_focus()
	return true

func _on_ok() -> void:
	if _current_id != "":
		TutorialState.mark_seen(_current_id)
	_close()

func _on_dont_show() -> void:
	if _current_id != "":
		TutorialState.mark_seen(_current_id)
	TutorialState.suppress_all()
	_close()

func _on_dim_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_on_ok()

func _close() -> void:
	visible = false
	_current_id = ""

func _unhandled_input(event: InputEvent) -> void:
	# 教程期间消费 Esc 作为「知道了」，避免误触发暂停菜单。
	if visible and event.is_action_pressed("ui_cancel"):
		_on_ok()
		get_viewport().set_input_as_handled()
