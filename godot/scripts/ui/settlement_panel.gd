extends Control
class_name SettlementPanel

signal closed()

@onready var title_label: Label = $Panel/Content/TitleLabel
@onready var summary_label: Label = $Panel/Content/SummaryLabel
@onready var coin_result_box: VBoxContainer = $Panel/Content/CoinResult
@onready var coin_row: HBoxContainer = $Panel/Content/CoinResult/CoinRow
@onready var coin_summary_label: Label = $Panel/Content/CoinResult/CoinSummary
@onready var coin_outcome_label: Label = $Panel/Content/CoinResult/CoinOutcome
@onready var dream_text_label: Label = $Panel/Content/CoinResult/DreamText
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

	_show_coin_result(settlement_data.get("coin_result", {}), String(settlement_data.get("dream_text", "")))
	_show_resource_changes(settlement_data.get("resource_delta", {}))
	_show_character_changes(settlement_data.get("character_changes", []))
	_show_event_changes(settlement_data.get("event_changes", []))

	visible = true

func _show_coin_result(coin_result: Dictionary, dream_text: String) -> void:
	for child in coin_row.get_children():
		child.queue_free()

	if coin_result.is_empty():
		coin_result_box.visible = false
		dream_text_label.visible = false
		return

	coin_result_box.visible = true

	var flips: Array = coin_result.get("flips", [])
	for flip in flips:
		var head: bool = bool(flip)
		var coin_label: Label = Label.new()
		coin_label.text = "◉" if head else "○"
		coin_label.add_theme_font_size_override("font_size", 22)
		var color: Color = Color(1, 0.9, 0.55, 1) if head else Color(0.55, 0.6, 0.68, 1)
		coin_label.add_theme_color_override("font_color", color)
		coin_row.add_child(coin_label)

	var heads: int = int(coin_result.get("heads", 0))
	var total: int = int(coin_result.get("coins_thrown", 0))
	var tails: int = max(0, total - heads)
	var difficulty: int = int(coin_result.get("difficulty", 0))
	var bonus: int = int(coin_result.get("bonus_coins", 0))
	var success: bool = bool(coin_result.get("success", false))
	var bonus_hint: String = "（赐福 +%d）" % bonus if bonus > 0 else ""
	coin_summary_label.text = "掷出 %d 枚硬币%s，正 %d · 反 %d（需要 %d 枚正才能成功）" % [total, bonus_hint, heads, tails, difficulty]

	var outcome_word: String = "成功" if success else "失败"
	var outcome_label: String = String(coin_result.get("outcome_label", ""))
	var outcome_color: Color = Color(0.72, 0.92, 0.72, 1) if success else Color(0.95, 0.72, 0.72, 1)
	coin_outcome_label.add_theme_color_override("font_color", outcome_color)
	if outcome_label != "":
		coin_outcome_label.text = "%s · %s" % [outcome_word, outcome_label]
	else:
		coin_outcome_label.text = outcome_word

	if dream_text != "":
		dream_text_label.visible = true
		dream_text_label.text = "托梦：%s" % dream_text
	else:
		dream_text_label.visible = false

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
