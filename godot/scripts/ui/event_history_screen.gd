extends Control

## 事件历史回顾覆盖层。显示本局已发生的事件列表。

signal closed()

@onready var event_list: VBoxContainer = $Dim/Panel/VBox/Scroll/EventList
@onready var empty_label: Label = $Dim/Panel/VBox/EmptyLabel
@onready var close_button: Button = $Dim/Panel/VBox/Header/CloseButton

func _ready() -> void:
	visible = false
	close_button.pressed.connect(close)
	empty_label.add_theme_color_override("font_color", Color(0.5, 0.55, 0.6))

func open(history: Array) -> void:
	_rebuild_list(history)
	visible = true
	close_button.grab_focus()

func close() -> void:
	visible = false
	closed.emit()

func _rebuild_list(history: Array) -> void:
	_clear_list()
	if history.is_empty():
		empty_label.visible = true
		return
	empty_label.visible = false
	for entry in history:
		var item := _create_item(entry)
		event_list.add_child(item)

func _clear_list() -> void:
	for child in event_list.get_children():
		child.queue_free()

func _create_item(entry: Dictionary) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 0)
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	# 危险度左侧色条
	var risk: String = String(entry.get("risk_level", "Low"))
	var bar := ColorRect.new()
	bar.custom_minimum_size = Vector2(4, 0)
	bar.size_flags_vertical = Control.SIZE_EXPAND_FILL
	bar.color = _risk_color(risk)
	row.add_child(bar)

	var margin := MarginContainer.new()
	margin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	margin.add_theme_constant_override("margin_left", 10)
	margin.add_theme_constant_override("margin_top", 6)
	margin.add_theme_constant_override("margin_right", 10)
	margin.add_theme_constant_override("margin_bottom", 6)
	row.add_child(margin)

	var vbox := VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	margin.add_child(vbox)

	var meta := Label.new()
	meta.add_theme_font_size_override("font_size", 14)
	meta.add_theme_color_override("font_color", Color(0.6, 0.65, 0.72))
	meta.text = "第 %d 天 · %s · %s" % [
		int(entry.get("day", 0)),
		String(entry.get("time_slot_label", "")),
		String(entry.get("location_label", "")),
	]
	vbox.add_child(meta)

	var title := Label.new()
	title.add_theme_font_size_override("font_size", 17)
	title.text = String(entry.get("event_name", "未知事件"))
	vbox.add_child(title)

	var summary := Label.new()
	summary.add_theme_font_size_override("font_size", 14)
	summary.add_theme_color_override("font_color", Color(0.55, 0.6, 0.65))
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	summary.text = String(entry.get("summary", ""))
	vbox.add_child(summary)

	return row

func _risk_color(risk: String) -> Color:
	match risk:
		"High":
			return Color(0.85, 0.25, 0.2)
		"Fatal":
			return Color(0.9, 0.1, 0.1)
		_:
			return Color(0.3, 0.35, 0.4)

func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		close()
		get_viewport().set_input_as_handled()
