extends Control
class_name SettlementPanel

signal closed()

@onready var title_label: Label = $Panel/Content/TitleLabel
@onready var summary_label: Label = $Panel/Content/SummaryLabel
@onready var resource_changes_container: VBoxContainer = $Panel/Content/ResourceChanges/ChangesList
@onready var character_changes_container: VBoxContainer = $Panel/Content/CharacterChanges/ChangesList
@onready var event_changes_container: VBoxContainer = $Panel/Content/EventChanges/ChangesList
@onready var close_button: Button = $Panel/Content/CloseButton

func _ready() -> void:
	close_button.pressed.connect(_on_close_pressed)

func show_settlement(settlement_data: Dictionary) -> void:
	if not is_node_ready():
		await ready

	title_label.text = settlement_data.get("title", "结算摘要")
	summary_label.text = settlement_data.get("summary", "时间已推进。")

	_show_resource_changes(settlement_data.get("resource_delta", {}))
	_show_character_changes(settlement_data.get("character_changes", []))
	_show_event_changes(settlement_data.get("event_changes", []))

	visible = true

func _show_resource_changes(changes: Dictionary) -> void:
	for child in resource_changes_container.get_children():
		child.queue_free()

	if changes.is_empty():
		var label := Label.new()
		label.text = "  无资源变化"
		resource_changes_container.add_child(label)
		return

	for key in changes:
		var value := int(changes.get(key, 0))
		if value == 0:
			continue
		var label := Label.new()
		var resource_name := _get_resource_name(key)
		var sign_prefix := "+" if value > 0 else ""
		label.text = "  %s: %s%d" % [resource_name, sign_prefix, value]
		resource_changes_container.add_child(label)

func _show_character_changes(changes: Array) -> void:
	for child in character_changes_container.get_children():
		child.queue_free()

	if changes.is_empty():
		var label := Label.new()
		label.text = "  无人物状态变化"
		character_changes_container.add_child(label)
		return

	for change in changes:
		var label := Label.new()
		var character_name: String = String(change.get("character_name", "未知居民"))
		var change_desc: String = String(change.get("change", "状态变化"))
		label.text = "  %s: %s" % [character_name, change_desc]
		character_changes_container.add_child(label)

func _show_event_changes(changes: Array) -> void:
	for child in event_changes_container.get_children():
		child.queue_free()

	if changes.is_empty():
		var label := Label.new()
		label.text = "  无事件结果"
		event_changes_container.add_child(label)
		return

	for change in changes:
		var label := Label.new()
		var event_name: String = String(change.get("event_name", "未知事件"))
		var outcome: String = String(change.get("outcome", "已解决"))
		label.text = "  %s: %s" % [event_name, outcome]
		event_changes_container.add_child(label)

func _get_resource_name(key: String) -> String:
	match key:
		"incense":
			return "香火"
		"divine_power":
			return "神力"
		"yang_de":
			return "阳德"
		"yin_de":
			return "阴德"
		_:
			return key

func _on_close_pressed() -> void:
	visible = false
	closed.emit()
