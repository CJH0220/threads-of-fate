extends VBoxContainer
class_name LocationPanel

@onready var name_label: Label = $Header/NameLabel
@onready var category_label: Label = $Header/CategoryLabel
@onready var description_text: RichTextLabel = $DescriptionText
@onready var function_label: Label = $FunctionSection/FunctionLabel
@onready var time_slots_label: Label = $TimeSlotsSection/TimeSlotsLabel
@onready var morning_presence_label: Label = $DailyPresenceSection/MorningRow/MorningPresenceLabel
@onready var afternoon_presence_label: Label = $DailyPresenceSection/AfternoonRow/AfternoonPresenceLabel
@onready var night_presence_label: Label = $DailyPresenceSection/NightRow/NightPresenceLabel
@onready var events_container: VBoxContainer = $EventsSection/EventsContainer

func show_location(location: Dictionary, _time_slot_label_provider: Callable, presence_provider: Callable, events_provider: Callable) -> void:
	name_label.text = "%s" % location.get("display_name", "未知地点")
	category_label.text = location.get("category", "Daily")
	description_text.text = location.get("description", "暂无地点描述。")
	function_label.text = location.get("function", "暂无用途。")

	var slots: Array = location.get("primary_time_slots", [])
	if slots.is_empty():
		time_slots_label.text = "—"
	else:
		time_slots_label.text = ", ".join(slots)

	morning_presence_label.text = presence_provider.call(location.get("location_id", ""), "Morning")
	afternoon_presence_label.text = presence_provider.call(location.get("location_id", ""), "Afternoon")
	night_presence_label.text = presence_provider.call(location.get("location_id", ""), "Night")

	for child in events_container.get_children():
		child.queue_free()
	var location_events: Array = events_provider.call(location.get("location_id", ""))
	if location_events.is_empty():
		var empty_label := Label.new()
		empty_label.text = "无事件。"
		events_container.add_child(empty_label)
	else:
		for event in location_events:
			var event_label := Label.new()
			event_label.text = "%s（%s）" % [event.get("event_name", "未知事件"), event.get("risk_level", "Low")]
			events_container.add_child(event_label)

func show_empty() -> void:
	name_label.text = "地点"
	category_label.text = ""
	description_text.text = "未知地点。"
	function_label.text = ""
	time_slots_label.text = "—"
	morning_presence_label.text = "—"
	afternoon_presence_label.text = "—"
	night_presence_label.text = "—"
	for child in events_container.get_children():
		child.queue_free()
