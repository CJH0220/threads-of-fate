extends Control

## 60 天总评覆盖层。第 60 天结束且未触发 Game Over 后进入。
## 展示最终路线、资源结果、NPC 结局、关键事件回顾。
## 出口：查看最终结局 / 返回主菜单。

signal view_ending_requested(ending_data: Dictionary)
signal return_to_menu_requested()
signal review_requested()

@onready var route_label: Label = $Dim/Panel/VBox/RouteLabel
@onready var summary_text: RichTextLabel = $Dim/Panel/VBox/SummaryScroll/SummaryText
@onready var view_ending_button: Button = $Dim/Panel/VBox/ButtonRow/ViewEndingButton
@onready var review_button: Button = $Dim/Panel/VBox/ButtonRow/ReviewButton
@onready var menu_button: Button = $Dim/Panel/VBox/ButtonRow/MenuButton

var _ending_data: Dictionary = {}

func _ready() -> void:
	visible = false
	view_ending_button.pressed.connect(_on_view_ending)
	review_button.pressed.connect(func() -> void: review_requested.emit())
	menu_button.pressed.connect(func() -> void: return_to_menu_requested.emit())

func open(ending_data: Dictionary) -> void:
	_ending_data = ending_data
	route_label.text = "最终路线：%s" % String(ending_data.get("title", "旧庙余香"))
	summary_text.text = _build_summary(ending_data)
	visible = true
	view_ending_button.grab_focus()

func close() -> void:
	visible = false

func _on_view_ending() -> void:
	view_ending_requested.emit(_ending_data)

func _build_summary(data: Dictionary) -> String:
	var resources: Dictionary = data.get("resources", {})
	var lines: Array[String] = []
	lines.append("[b]资源结果[/b]")
	lines.append("香火 %d    阳德 %d    阴德 %d    神力 %d" % [
		int(resources.get("incense", 0)),
		int(resources.get("yang_de", 0)),
		int(resources.get("yin_de", 0)),
		int(resources.get("divine_power", 0)),
	])
	lines.append("")
	lines.append("[b]居民命运[/b]")
	var character_endings: Array = data.get("character_endings", [])
	if character_endings.is_empty():
		lines.append("（暂无居民记录）")
	else:
		for entry: Dictionary in character_endings:
			lines.append("%s：%s" % [String(entry.get("name", "居民")), String(entry.get("ending", "中性结局"))])
	lines.append("")
	lines.append("[b]关键事件回顾[/b]")
	var key_events: Array = data.get("key_events", [])
	if key_events.is_empty():
		lines.append("（本局没有显著事件）")
	else:
		for event_name: String in key_events:
			lines.append("- %s" % event_name)
	return "\n".join(lines)
