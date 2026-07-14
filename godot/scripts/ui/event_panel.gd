extends VBoxContainer
class_name EventPanel

## 事件详情面板（重构版）。
## 职责：呈现事件基础信息 + 参与角色头像 + 进入 / 回看按钮。
## 干预不再挂在此面板 —— 托梦入口移到 CharacterPanel，赐福在演出内部关键点触发。
## 演出结束后事件被锁定：按钮切换为「回看事件」，并在下方展示演出快照摘要。

signal enter_requested(event_id: String)

@onready var title_label: Label = $Header/TitleLabel
@onready var risk_label: Label = $Header/RiskLabel
@onready var location_label: Label = $MetaRow/LocationLabel
@onready var type_label: Label = $MetaRow/TypeLabel
@onready var participants_row: HBoxContainer = $ParticipantsRow
@onready var participants_container: HBoxContainer = $ParticipantsRow/ParticipantsContainer
@onready var summary_text: RichTextLabel = $SummaryText
@onready var enter_button: Button = $EnterButton
## 复用原干预容器承载「演出快照」摘要（已完成事件）或「入场提示」（未完成事件）。
@onready var interventions_container: VBoxContainer = $InterventionsSection/InterventionsContainer

const PARTICIPANT_AVATAR_SIZE: int = 30

var _event_id := ""

func _ready() -> void:
	enter_button.pressed.connect(func() -> void: enter_requested.emit(_event_id))

## 呈现事件。
## - is_completed=false：显示「进入事件」，下方给一句提示。
## - is_completed=true ：显示「回看事件」，下方渲染 snapshot（赐福链、结局标签）。
func show_event(event: Dictionary, is_completed: bool, snapshot: Dictionary = {}) -> void:
	_event_id = String(event.get("event_id", ""))
	title_label.text = String(event.get("event_name", "未知事件"))
	risk_label.text = String(event.get("risk_level", "Low"))
	location_label.text = String(event.get("location_label", "地点未知"))
	type_label.text = String(event.get("event_type", "Daily"))
	summary_text.text = String(event.get("description", "暂无事件描述。"))
	enter_button.visible = true
	enter_button.disabled = false

	_apply_participants(event)
	_clear_intervention_area()

	if is_completed:
		enter_button.text = "回看事件（结局已定）"
		var badge: Label = _make_hint("✅ 此事件已演出完毕，命运线不再改变。")
		badge.add_theme_color_override("font_color", Color(0.65, 0.85, 0.75, 1))
		interventions_container.add_child(badge)
		_render_snapshot(snapshot)
	else:
		enter_button.text = "进入事件"
		interventions_container.add_child(_make_hint("演出中会出现关键抉择时刻，届时可选择是否赐福。"))

func show_empty() -> void:
	_event_id = ""
	title_label.text = "事件"
	risk_label.text = ""
	location_label.text = ""
	type_label.text = ""
	summary_text.text = "此刻风平浪静。"
	enter_button.visible = false
	_clear_intervention_area()
	_clear_participants()
	if participants_row != null:
		participants_row.visible = false

## 渲染演出快照：赐福链每一次决策的结果 + 完成时间。
func _render_snapshot(snapshot: Dictionary) -> void:
	if snapshot.is_empty():
		return
	var blessings: Array = snapshot.get("blessings", [])
	if not blessings.is_empty():
		var header: Label = _make_hint("演出中的赐福：")
		header.add_theme_color_override("font_color", Color(1, 0.92, 0.7, 1))
		interventions_container.add_child(header)
		for entry in blessings:
			var seg: int = int(entry.get("seg_index", 0))
			var blessed: bool = bool(entry.get("bless", false))
			var coin: Dictionary = entry.get("coin_result", {})
			var line: String
			if not blessed:
				line = "· 第 %d 幕：未干预" % (seg + 1)
			else:
				var ok: bool = bool(coin.get("success", false))
				line = "· 第 %d 幕：赐福 %s" % [seg + 1, "成功" if ok else "未奏效"]
				if coin.has("outcome_label"):
					line += " —— " + String(coin.get("outcome_label", ""))
			interventions_container.add_child(_make_hint(line))
	var finished_at: Dictionary = snapshot.get("finished_at", {})
	if not finished_at.is_empty():
		var slot: String = String(finished_at.get("time_slot", ""))
		var slot_label: String = {"Morning": "早晨", "Afternoon": "下午", "Night": "夜晚"}.get(slot, slot)
		interventions_container.add_child(_make_hint("完成于第 %d 天 · %s" % [int(finished_at.get("day", 0)), slot_label]))

func _make_hint(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.add_theme_font_size_override("font_size", 13)
	label.add_theme_color_override("font_color", Color(0.82, 0.86, 0.9, 1))
	return label

func _clear_intervention_area() -> void:
	for child in interventions_container.get_children():
		child.queue_free()

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
