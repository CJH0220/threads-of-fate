extends VBoxContainer
class_name EventPanel

signal intervention_applied(event_id: String, intervention_id: String)
signal enter_requested(event_id: String)

@onready var title_label: Label = $Header/TitleLabel
@onready var risk_label: Label = $Header/RiskLabel
@onready var location_label: Label = $MetaRow/LocationLabel
@onready var type_label: Label = $MetaRow/TypeLabel
@onready var participants_row: HBoxContainer = $ParticipantsRow
@onready var participants_container: HBoxContainer = $ParticipantsRow/ParticipantsContainer
@onready var summary_text: RichTextLabel = $SummaryText
@onready var enter_button: Button = $EnterButton
@onready var interventions_container: VBoxContainer = $InterventionsSection/InterventionsContainer

const PARTICIPANT_AVATAR_SIZE: int = 30

var _event_id := ""

func _ready() -> void:
	enter_button.pressed.connect(func() -> void: enter_requested.emit(_event_id))

func show_event(event: Dictionary, interventions: Array, divine_power: int, applied: Dictionary = {}) -> void:
	_event_id = String(event.get("event_id", ""))
	title_label.text = String(event.get("event_name", "未知事件"))
	risk_label.text = String(event.get("risk_level", "Low"))
	location_label.text = String(event.get("location_label", "地点未知"))
	type_label.text = String(event.get("event_type", "Daily"))
	summary_text.text = String(event.get("description", "暂无事件描述。"))
	enter_button.visible = true

	_apply_participants(event)

	for child in interventions_container.get_children():
		child.queue_free()

	var is_locked: bool = not applied.is_empty()
	var applied_display: String = String(applied.get("display_name", "")) if is_locked else ""

	if interventions.is_empty():
		var empty_label: Label = Label.new()
		empty_label.text = "当前事件暂无可用干预。"
		interventions_container.add_child(empty_label)
	else:
		var event_id: String = String(event.get("event_id", ""))
		for intervention in interventions:
			var button: Button = Button.new()
			var cost: int = int(intervention.get("cost_divine_power", 0))
			var intervention_id: String = String(intervention.get("intervention_id", ""))
			var display_name: String = String(intervention.get("display_name", "未知干预"))
			var desc: String = String(intervention.get("description", ""))
			button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			if is_locked:
				button.disabled = true
				if intervention_id == String(applied.get("intervention_id", "")):
					button.text = "%s · 神力 %d\n已干预：%s" % [display_name, cost, applied_display]
				else:
					button.text = "%s · 神力 %d\n（已干预，无法再次影响此事件）" % [display_name, cost]
			else:
				button.text = "%s · 神力 %d\n%s" % [display_name, cost, desc]
				if divine_power < cost:
					button.disabled = true
					button.text += "\n（神力不足）"
				button.pressed.connect(func() -> void: _on_intervention_clicked(event_id, intervention_id))
			interventions_container.add_child(button)

func show_empty() -> void:
	_event_id = ""
	title_label.text = "事件"
	risk_label.text = ""
	location_label.text = ""
	type_label.text = ""
	summary_text.text = "此刻风平浪静。"
	enter_button.visible = false
	for child in interventions_container.get_children():
		child.queue_free()
	_clear_participants()
	if participants_row != null:
		participants_row.visible = false

func _on_intervention_clicked(event_id: String, intervention_id: String) -> void:
	intervention_applied.emit(event_id, intervention_id)

## 用事件的 participant_npc_ids / participant_display_names 渲染涉及角色头像。
func _apply_participants(event: Dictionary) -> void:
	_clear_participants()
	if participants_row == null:
		return
	var ids: Array = event.get("participant_npc_ids", [])
	var names: Array = event.get("participant_display_names", [])
	if ids.is_empty():
		participants_row.visible = false
		return
	participants_row.visible = true
	for i in range(ids.size()):
		var npc_id: String = String(ids[i])
		var display_name: String = String(names[i]) if i < names.size() else npc_id
		participants_container.add_child(_make_participant_avatar(npc_id, display_name))

func _clear_participants() -> void:
	if participants_container == null:
		return
	for child in participants_container.get_children():
		child.queue_free()

func _make_participant_avatar(npc_id: String, display_name: String) -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(PARTICIPANT_AVATAR_SIZE, PARTICIPANT_AVATAR_SIZE)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.set_corner_radius_all(PARTICIPANT_AVATAR_SIZE / 2)
	style.set_border_width_all(1)
	style.border_color = Color(0.82, 0.72, 0.48, 0.75)
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
		initial.add_theme_font_size_override("font_size", 14)
		initial.add_theme_color_override("font_color", PortraitService.get_color(npc_id))
		initial.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		initial.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		initial.mouse_filter = Control.MOUSE_FILTER_IGNORE
		initial.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		initial.size_flags_vertical = Control.SIZE_EXPAND_FILL
		panel.add_child(initial)
	return panel
