extends Control

## 周结算覆盖层。每 7 天（第 7/14/.../56 天）夜后触发，展示本周资源 / 重大事件 / 业线进度。
## 显示期间应阻断暂停与存档（由 main.gd 守卫）。第 60 天走最终总评，不走周结算。

signal continue_requested()

@onready var title_label: Label = $Dim/Panel/VBox/TitleLabel
@onready var range_label: Label = $Dim/Panel/VBox/RangeLabel
@onready var body_text: RichTextLabel = $Dim/Panel/VBox/BodyScroll/BodyText
@onready var continue_button: Button = $Dim/Panel/VBox/ContinueButton

func _ready() -> void:
	visible = false
	continue_button.pressed.connect(_on_continue)

func open(week_data: Dictionary) -> void:
	title_label.text = "第 %d 周回顾" % int(week_data.get("week_number", 1))
	range_label.text = String(week_data.get("day_range", ""))
	body_text.text = _build_body(week_data)
	visible = true
	continue_button.grab_focus()

func close() -> void:
	visible = false

func _on_continue() -> void:
	close()
	continue_requested.emit()

func _unhandled_input(event: InputEvent) -> void:
	# 周结算期间消费 Esc，避免误触发暂停菜单；不可跳过，需点「继续」。
	if visible and event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()

func _build_body(week_data: Dictionary) -> String:
	var lines: Array[String] = []
	var resources: Dictionary = week_data.get("resources", {})
	lines.append("[b]当前资源[/b]")
	lines.append("香火 %d   神力 %d   阳德 %d   阴德 %d" % [
		int(resources.get("incense", 0)),
		int(resources.get("divine_power", 0)),
		int(resources.get("yang_de", 0)),
		int(resources.get("yin_de", 0)),
	])
	lines.append("")

	var major_events: Array = week_data.get("major_events", [])
	lines.append("[b]本周大事[/b]")
	if major_events.is_empty():
		lines.append("· 本周风平浪静。")
	else:
		for event_name in major_events:
			lines.append("· %s" % String(event_name))
	lines.append("")

	var destiny_progress: Array = week_data.get("destiny_progress", [])
	lines.append("[b]业线进度[/b]")
	if destiny_progress.is_empty():
		lines.append("· 暂无可见业线。")
	else:
		for entry in destiny_progress:
			lines.append("· %s — %s（%d%%）" % [
				String(entry.get("name", "居民")),
				String(entry.get("karma_summary", "")),
				int(entry.get("progress", 0)),
			])
	lines.append("")
	lines.append("[i]%s[/i]" % String(week_data.get("next_hint", "")))
	return "\n".join(lines)
