extends Control

## 最终结局界面覆盖层。承接 60 天总评「查看最终结局」。
## 展示结局标题、像素插图占位、结局文本、最终评价。
## 出口：结局回顾(占位) / 重新开始(需确认) / 返回主菜单。Esc 不跳过。

signal restart_requested()
signal return_to_menu_requested()
signal review_requested()

const STYLE_COLORS := {
	"Righteous": Color(0.86, 0.70, 0.30),
	"Evil": Color(0.38, 0.12, 0.20),
	"Neutral": Color(0.44, 0.41, 0.37),
	"Legend": Color(0.55, 0.40, 0.72),
	"Failure": Color(0.20, 0.20, 0.23),
}

@onready var title_label: Label = $Dim/Panel/VBox/TitleLabel
@onready var illustration: ColorRect = $Dim/Panel/VBox/Illustration
@onready var illustration_label: Label = $Dim/Panel/VBox/Illustration/IllustrationLabel
@onready var ending_text: RichTextLabel = $Dim/Panel/VBox/TextScroll/EndingText
@onready var evaluation_label: Label = $Dim/Panel/VBox/EvaluationLabel
@onready var review_button: Button = $Dim/Panel/VBox/ButtonRow/ReviewButton
@onready var restart_button: Button = $Dim/Panel/VBox/ButtonRow/RestartButton
@onready var menu_button: Button = $Dim/Panel/VBox/ButtonRow/MenuButton
@onready var restart_confirm: ConfirmationDialog = $RestartConfirm

func _ready() -> void:
	visible = false
	review_button.pressed.connect(func() -> void: review_requested.emit())
	restart_button.pressed.connect(func() -> void: restart_confirm.popup_centered())
	menu_button.pressed.connect(func() -> void: return_to_menu_requested.emit())
	restart_confirm.confirmed.connect(func() -> void: restart_requested.emit())

func open(ending_data: Dictionary) -> void:
	var ending_type := String(ending_data.get("ending_type", "Neutral"))
	var tint: Color = STYLE_COLORS.get(ending_type, STYLE_COLORS["Neutral"])
	title_label.text = "%s结局" % String(ending_data.get("title", "旧庙余香"))
	title_label.add_theme_color_override("font_color", tint.lightened(0.2))
	illustration.color = tint.darkened(0.35)
	illustration_label.text = "［ %s ］" % String(ending_data.get("route_label", "结局插图"))
	ending_text.text = String(ending_data.get("description", ""))
	evaluation_label.text = "最终评价：%s" % String(ending_data.get("evaluation", "旁观者"))
	visible = true
	menu_button.grab_focus()

func close() -> void:
	visible = false

func _unhandled_input(event: InputEvent) -> void:
	# Esc 不跳过结局，仅消费事件避免误触发暂停菜单。
	if visible and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
