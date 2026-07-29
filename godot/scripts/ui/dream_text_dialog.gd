extends Control
class_name DreamTextDialog

## 托梦文字输入弹窗。玩家输入 100 字以内文字，作为神力干预的托梦内容。
## 文字不影响硬币结算，只写入事件历史/日志。

signal confirmed(dream_text: String)
signal cancelled()

const MAX_LENGTH: int = 100

@onready var title_label: Label = $Panel/VBox/TitleLabel
@onready var hint_label: Label = $Panel/VBox/HintLabel
@onready var text_edit: TextEdit = $Panel/VBox/DreamTextEdit
@onready var counter_label: Label = $Panel/VBox/CounterLabel
@onready var confirm_button: Button = $Panel/VBox/ButtonRow/ConfirmButton
@onready var cancel_button: Button = $Panel/VBox/ButtonRow/CancelButton

var _target_label: String = ""

func _ready() -> void:
	text_edit.text_changed.connect(_on_text_changed)
	confirm_button.pressed.connect(_on_confirm)
	cancel_button.pressed.connect(_on_cancel)
	_update_counter()

## 打开弹窗。target_label 用于标题显示目标 NPC/事件名。
func open(target_label: String = "") -> void:
	text_edit.editable = true
	confirm_button.text = "确定"
	cancel_button.visible = true
	_target_label = target_label
	if target_label == "":
		title_label.text = "托梦"
	else:
		title_label.text = "托梦 · %s" % target_label
	text_edit.text = ""
	_update_counter()
	visible = true
	text_edit.grab_focus()

func close() -> void:
	visible = false

func _on_text_changed() -> void:
	var content: String = text_edit.text
	if content.length() > MAX_LENGTH:
		var caret_line: int = text_edit.get_caret_line()
		var caret_col: int = text_edit.get_caret_column()
		text_edit.text = content.substr(0, MAX_LENGTH)
		text_edit.set_caret_line(caret_line)
		text_edit.set_caret_column(min(caret_col, text_edit.text.length()))
	_update_counter()

func _update_counter() -> void:
	counter_label.text = "%d / %d" % [text_edit.text.length(), MAX_LENGTH]

func _on_confirm() -> void:
	visible = false
	confirmed.emit(text_edit.text)

func _on_cancel() -> void:
	visible = false
	cancelled.emit()

## 展示 NPC 收到托梦后的内心思考（只读弹窗，不可编辑）。
func show_reflection(npc_name: String, dream_text: String, reflection: String) -> void:
	_target_label = npc_name
	title_label.text = "%s 的内心回响" % npc_name
	hint_label.text = "你向 %s 托梦：\n「%s」" % [npc_name, dream_text]
	text_edit.text = reflection
	text_edit.editable = false
	_update_counter()
	visible = true
	confirm_button.text = "继续"
	cancel_button.visible = false

func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		_on_cancel()
		get_viewport().set_input_as_handled()
