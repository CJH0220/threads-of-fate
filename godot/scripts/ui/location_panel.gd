extends VBoxContainer
class_name LocationPanel

const PRESENT_PORTRAIT_SIZE: int = 36
const PRESENT_MAX_PORTRAITS: int = 6

@onready var background_frame: PanelContainer = $BackgroundFrame
@onready var background_image: TextureRect = $BackgroundFrame/BackgroundImage
@onready var name_label: Label = $Header/NameLabel
@onready var category_label: Label = $Header/CategoryLabel
@onready var present_row: HBoxContainer = $PresentSection/PresentRow
@onready var description_text: RichTextLabel = $DescriptionText
@onready var function_label: Label = $FunctionSection/FunctionLabel
@onready var time_slots_label: Label = $TimeSlotsSection/TimeSlotsLabel
@onready var morning_presence_label: Label = $DailyPresenceSection/MorningRow/MorningPresenceLabel
@onready var afternoon_presence_label: Label = $DailyPresenceSection/AfternoonRow/AfternoonPresenceLabel
@onready var night_presence_label: Label = $DailyPresenceSection/NightRow/NightPresenceLabel
@onready var events_container: VBoxContainer = $EventsSection/EventsContainer

func show_location(location: Dictionary, _time_slot_label_provider: Callable, presence_provider: Callable, events_provider: Callable) -> void:
	var location_id: String = String(location.get("location_id", ""))
	name_label.text = "%s" % location.get("display_name", "未知地点")
	category_label.text = location.get("category", "Daily")
	description_text.text = location.get("description", "暂无地点描述。")
	function_label.text = location.get("function", "暂无用途。")

	_apply_background(location_id)
	_apply_present_row(location)

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
	_clear_present_row()
	_apply_background("")

## 加载并显示地点空镜背景。无图则隐藏背景框以节省纵向空间。
func _apply_background(location_id: String) -> void:
	if background_image == null or background_frame == null:
		return
	var tex: Texture2D = PortraitService.get_background(location_id) if location_id != "" else null
	if tex != null:
		background_image.texture = tex
		background_frame.visible = true
	else:
		background_image.texture = null
		background_frame.visible = false

## 用当前地点的 present_npc_ids 渲染 "此刻在此" 头像行。
func _apply_present_row(location: Dictionary) -> void:
	_clear_present_row()
	if present_row == null:
		return
	var ids: Array = location.get("present_npc_ids", [])
	var names: Array = location.get("present_npc_names", [])
	if ids.is_empty():
		var empty_label := Label.new()
		empty_label.text = "此刻无人。"
		empty_label.add_theme_color_override("font_color", Color(0.75, 0.75, 0.78, 1))
		empty_label.add_theme_font_size_override("font_size", 13)
		present_row.add_child(empty_label)
		return
	var shown: int = min(ids.size(), PRESENT_MAX_PORTRAITS)
	for i in range(shown):
		var npc_id: String = String(ids[i])
		var display_name: String = String(names[i]) if i < names.size() else npc_id
		present_row.add_child(_make_present_avatar(npc_id, display_name))
	if ids.size() > PRESENT_MAX_PORTRAITS:
		var more_label := Label.new()
		more_label.text = "+%d" % (ids.size() - PRESENT_MAX_PORTRAITS)
		more_label.add_theme_font_size_override("font_size", 13)
		more_label.add_theme_color_override("font_color", Color(0.9, 0.9, 0.9, 1))
		present_row.add_child(more_label)

func _clear_present_row() -> void:
	if present_row == null:
		return
	for child in present_row.get_children():
		child.queue_free()

func _make_present_avatar(npc_id: String, display_name: String) -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(PRESENT_PORTRAIT_SIZE, PRESENT_PORTRAIT_SIZE)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.set_corner_radius_all(PRESENT_PORTRAIT_SIZE / 2)
	style.set_border_width_all(1)
	style.border_color = Color(0.82, 0.72, 0.48, 0.85)
	style.bg_color = Color(0.09, 0.11, 0.14, 1)
	panel.add_theme_stylebox_override("panel", style)
	panel.tooltip_text = display_name

	var tex: Texture2D = PortraitService.get_portrait(npc_id)
	if tex != null:
		var tr := TextureRect.new()
		tr.texture = tex
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
		tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
		panel.add_child(tr)
	else:
		var initial := Label.new()
		initial.text = PortraitService.get_initial(display_name)
		initial.add_theme_font_size_override("font_size", 16)
		initial.add_theme_color_override("font_color", PortraitService.get_color(npc_id))
		initial.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		initial.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		initial.mouse_filter = Control.MOUSE_FILTER_IGNORE
		initial.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		initial.size_flags_vertical = Control.SIZE_EXPAND_FILL
		panel.add_child(initial)
	return panel
