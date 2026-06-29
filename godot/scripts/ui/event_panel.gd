extends VBoxContainer
class_name EventPanel

signal intervention_applied(event_id: String, intervention_id: String)
signal enter_requested(event_id: String)

@onready var title_label: Label = $Header/TitleLabel
@onready var risk_label: Label = $Header/RiskLabel
@onready var location_label: Label = $MetaRow/LocationLabel
@onready var type_label: Label = $MetaRow/TypeLabel
@onready var summary_text: RichTextLabel = $SummaryText
@onready var enter_button: Button = $EnterButton
@onready var interventions_container: VBoxContainer = $InterventionsSection/InterventionsContainer

var _event_id := ""

func _ready() -> void:
	enter_button.pressed.connect(func() -> void: enter_requested.emit(_event_id))

func show_event(event: Dictionary, interventions: Array, divine_power: int) -> void:
	_event_id = String(event.get("event_id", ""))
	title_label.text = String(event.get("event_name", "未知事件"))
	risk_label.text = String(event.get("risk_level", "Low"))
	location_label.text = String(event.get("location_label", "地点未知"))
	type_label.text = String(event.get("event_type", "Daily"))
	summary_text.text = String(event.get("description", "暂无事件描述。"))
	enter_button.visible = true

	for child in interventions_container.get_children():
		child.queue_free()

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
			button.text = "%s · 神力 %d\n%s" % [display_name, cost, desc]
			button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
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

func _on_intervention_clicked(event_id: String, intervention_id: String) -> void:
	intervention_applied.emit(event_id, intervention_id)
