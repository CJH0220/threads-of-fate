extends Control

## 关于我们覆盖层。展示游戏名、制作人员、鸣谢、版本号。
## 仅从主菜单进入，返回主菜单。文案为占位，后续补全。

signal closed()

@onready var credits_text: RichTextLabel = $Dim/Panel/VBox/CreditsScroll/CreditsText
@onready var back_button: Button = $Dim/Panel/VBox/Header/BackButton

func _ready() -> void:
	visible = false
	back_button.pressed.connect(_close)
	_build_content()

func open() -> void:
	visible = true
	back_button.grab_focus()

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("ui_cancel"):
		_close()
		get_viewport().set_input_as_handled()

func _close() -> void:
	visible = false
	closed.emit()

func _build_content() -> void:
	var version := str(ProjectSettings.get_setting("application/config/version", "0.1.0"))
	var lines: Array[String] = [
		"[center][font_size=28]命运的织线[/font_size][/center]",
		"[center]归潮镇 · 命运织线器[/center]",
		"",
		"[b]制作[/b]",
		"策划 — 待定",
		"程序 — 待定",
		"美术 — 待定",
		"音频 — 待定",
		"",
		"[b]特别鸣谢[/b]",
		"测试与建议 — 待定",
		"",
		"[b]工具鸣谢[/b]",
		"Godot Engine 4.4",
		"字体 / 音频工具 — 待补充",
		"",
		"[b]素材鸣谢[/b]",
		"美术 / 音效 / 字体素材来源 — 待补充",
		"",
		"版本：v%s" % version,
		"© 2026 命运的织线项目组",
	]
	credits_text.text = "\n".join(lines)
