extends Control

## 游戏失败 / Game Over 覆盖层。
## 触发：第 60 天后香火 < 100，或强硬不幸结局 / 特殊终局。
## 出口：读取存档(无档时灰化) / 重新开始(需确认) / 返回主菜单。Esc 不跳过。

signal load_requested()
signal restart_requested()
signal return_to_menu_requested()
signal review_requested()

@onready var title_label: Label = $Dim/Panel/VBox/TitleLabel
@onready var failure_text: RichTextLabel = $Dim/Panel/VBox/TextScroll/FailureText
@onready var load_button: Button = $Dim/Panel/VBox/ButtonRow/LoadButton
@onready var review_button: Button = $Dim/Panel/VBox/ButtonRow/ReviewButton
@onready var restart_button: Button = $Dim/Panel/VBox/ButtonRow/RestartButton
@onready var menu_button: Button = $Dim/Panel/VBox/ButtonRow/MenuButton
@onready var restart_confirm: ConfirmationDialog = $RestartConfirm

func _ready() -> void:
	visible = false
	load_button.pressed.connect(func() -> void: load_requested.emit())
	review_button.pressed.connect(func() -> void: review_requested.emit())
	restart_button.pressed.connect(func() -> void: restart_confirm.popup_centered())
	menu_button.pressed.connect(func() -> void: return_to_menu_requested.emit())
	restart_confirm.confirmed.connect(func() -> void: restart_requested.emit())

func open(ending_data: Dictionary, has_save := false) -> void:
	title_label.text = String(ending_data.get("title", "香火熄灭"))
	failure_text.text = _build_text(ending_data)
	# 无可读存档时读档按钮灰化（规格 §6）。
	load_button.disabled = not has_save
	visible = true
	restart_button.grab_focus()

func close() -> void:
	visible = false

func _build_text(data: Dictionary) -> String:
	var lines: Array[String] = []
	lines.append(String(data.get("description", "土地庙前最后一缕香火散去。")))
	lines.append("")
	lines.append("[b]失败原因[/b]：%s" % String(data.get("reason", "香火不足")))
	lines.append("[b]触发时间[/b]：%s" % String(data.get("trigger_time", "第 60 天 · 夜")))
	var resources: Dictionary = data.get("resources", {})
	lines.append("[b]最终香火[/b]：%d" % int(resources.get("incense", 0)))
	return "\n".join(lines)

func _unhandled_input(event: InputEvent) -> void:
	# Esc 不直接退出失败界面，仅消费事件。
	if visible and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
