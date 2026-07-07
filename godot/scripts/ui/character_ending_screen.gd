extends Control

## 角色结局覆盖层。展示单个 NPC 的业线结局：类型 / 插图占位 / 结局文本 / 原因 / 资源影响。
## MVP 由 DestinyView 进度 100% 的「查看结局」入口打开；数据来自 MockGameState.get_character_ending。

signal continue_requested()

const TYPE_COLORS := {
	"好结局": Color(0.86, 0.70, 0.30),
	"坏结局": Color(0.55, 0.20, 0.28),
	"中性结局": Color(0.55, 0.52, 0.48),
	"特殊结局": Color(0.55, 0.40, 0.72),
}

@onready var title_label: Label = $Dim/Panel/VBox/TitleLabel
@onready var illustration: ColorRect = $Dim/Panel/VBox/Illustration
@onready var body_text: RichTextLabel = $Dim/Panel/VBox/BodyScroll/BodyText
@onready var continue_button: Button = $Dim/Panel/VBox/ContinueButton

func _ready() -> void:
	visible = false
	continue_button.pressed.connect(_on_continue)

func open(ending: Dictionary) -> void:
	var ending_type: String = String(ending.get("ending_type", "中性结局"))
	title_label.text = "%s：%s" % [String(ending.get("name", "居民")), ending_type]
	title_label.add_theme_color_override("font_color", TYPE_COLORS.get(ending_type, Color.WHITE))
	illustration.color = TYPE_COLORS.get(ending_type, Color(0.3, 0.3, 0.3)).darkened(0.4)
	body_text.text = _build_body(ending)
	visible = true
	continue_button.grab_focus()

func close() -> void:
	visible = false

func _on_continue() -> void:
	close()
	continue_requested.emit()

func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		_on_continue()
		get_viewport().set_input_as_handled()

func _build_body(ending: Dictionary) -> String:
	var lines: Array[String] = []
	lines.append(String(ending.get("ending_text", "命运在此落下帷幕。")))
	lines.append("")
	lines.append("[b]结局原因[/b]")
	var reasons: Array = ending.get("reasons", [])
	if reasons.is_empty():
		lines.append("· 业线走向最终的归宿。")
	else:
		for reason in reasons:
			lines.append("· %s" % String(reason))
	lines.append("")
	lines.append("[b]影响[/b]")
	var impact: Dictionary = ending.get("resource_impact", {})
	var parts: Array[String] = []
	for key in impact:
		var label := _resource_label(String(key))
		var value := int(impact[key])
		var sign := "+" if value >= 0 else ""
		parts.append("%s %s%d" % [label, sign, value])
	lines.append("、".join(parts) if not parts.is_empty() else "无明显资源变化")
	return "\n".join(lines)

func _resource_label(key: String) -> String:
	match key:
		"incense":
			return "香火"
		"yang_de":
			return "阳德"
		"yin_de":
			return "阴德"
		"divine_power":
			return "神力"
		_:
			return key
