extends Control

## 视觉小说式事件演出界面（VN）。
## 结构：上半区（背景 + 左右立绘槽 + 地点标签）+ 下半区（对话框：头像/发言者/类型标签 + 逐字文本 + 进度 + 控制按钮）
## 特性：逐字打字效果、自动播放、跳过已读、展开对话日志回顾、立绘入场动画
## 无障碍：角色区分依靠 位置 / 名字 / 头像首字 / 发言中标记 四重提示，不唯一依赖颜色
## Settings 接入：text/typing_speed / text/auto_speed / text/skip_read / accessibility/reduce_motion

signal finished()

## 对话分段类型：角色正常说话
const TYPE_SPEECH := "speech"
## 对话分段类型：旁白/叙述
const TYPE_NARRATION := "narration"
## 对话分段类型：角色内心想法
const TYPE_THOUGHT := "thought"

## 逐字打字速度（字符/秒），下标 0=慢 / 1=中 / 2=快，对应设置
const TYPING_CPS := {0: 18.0, 1: 36.0, 2: 72.0}
## 自动播放时每句末尾停留时间（秒），下标 0=慢 / 1=中 / 2=快
const AUTO_WAIT := {0: 2.4, 1: 1.5, 2: 0.8}
## 事件文本字号（像素），下标 0=小 / 1=标准 / 2=大
const FONT_SIZE := {0: 18, 1: 22, 2: 28}

## 地点背景色映射（LOCATION_BG["地点ID"] = 对应背景 Color），增强场景代入感
const LOCATION_BG := {
    "temple": Color(0.08, 0.06, 0.04),
    "school": Color(0.06, 0.07, 0.10),
    "port": Color(0.04, 0.05, 0.08),
    "coffee_shop": Color(0.10, 0.08, 0.06),
    "wine_bar": Color(0.06, 0.04, 0.05),
    "seafood_shop": Color(0.07, 0.06, 0.05),
    "clinic": Color(0.06, 0.08, 0.07),
    "beach": Color(0.05, 0.06, 0.08),
    "plaza": Color(0.07, 0.07, 0.06),
    "police_station": Color(0.05, 0.05, 0.07),
    "mountain_forest": Color(0.04, 0.06, 0.04),
}

@onready var location_label: Label = $Stage/LocationLabel
@onready var slot_left: Control = $Stage/CharSlotLeft
@onready var slot_left_portrait: ColorRect = $Stage/CharSlotLeft/Portrait
@onready var slot_left_initial: Label = $Stage/CharSlotLeft/Portrait/Initial
@onready var slot_left_active: Label = $Stage/CharSlotLeft/ActiveTag
@onready var slot_left_name: Label = $Stage/CharSlotLeft/NameTag
@onready var slot_right: Control = $Stage/CharSlotRight
@onready var slot_right_portrait: ColorRect = $Stage/CharSlotRight/Portrait
@onready var slot_right_initial: Label = $Stage/CharSlotRight/Portrait/Initial
@onready var slot_right_active: Label = $Stage/CharSlotRight/ActiveTag
@onready var slot_right_name: Label = $Stage/CharSlotRight/NameTag

@onready var avatar: ColorRect = $DialogueBox/VBox/TopRow/Avatar
@onready var avatar_initial: Label = $DialogueBox/VBox/TopRow/Avatar/Initial
@onready var speaker_label: Label = $DialogueBox/VBox/TopRow/SpeakerInfo/SpeakerLabel
@onready var type_tag: Label = $DialogueBox/VBox/TopRow/SpeakerInfo/TypeTag
@onready var expand_button: Button = $DialogueBox/VBox/TopRow/Controls/ExpandButton
@onready var auto_button: Button = $DialogueBox/VBox/TopRow/Controls/AutoButton
@onready var skip_button: Button = $DialogueBox/VBox/TopRow/Controls/SkipButton
@onready var background: ColorRect = $Background
@onready var body_text: RichTextLabel = $DialogueBox/VBox/BodyText
@onready var continue_hint: Label = $DialogueBox/VBox/HintRow/ContinueHint
@onready var progress_label: Label = $DialogueBox/VBox/HintRow/ProgressLabel
@onready var close_button: Button = $DialogueBox/VBox/HintRow/CloseButton

@onready var log_panel: Control = $LogPanel
@onready var log_container: VBoxContainer = $LogPanel/Dim/Panel/VBox/LogScroll/LogContainer
@onready var log_close_button: Button = $LogPanel/Dim/Panel/VBox/Header/CloseButton

@onready var auto_timer: Timer = $AutoTimer

var _segments: Array = []
var _index := 0
var _typing := false
var _char_progress := 0.0
var _cps := 36.0
var _full_len := 0
var _auto := false
var _history: Array = []
var _slot_pos := {}   # position -> {"id":..., "name":...}

func _ready() -> void:
	visible = false
	expand_button.pressed.connect(_toggle_log)
	auto_button.pressed.connect(_toggle_auto)
	skip_button.pressed.connect(_skip_all)
	close_button.pressed.connect(_finish)
	log_close_button.pressed.connect(_toggle_log)
	auto_timer.timeout.connect(_on_auto_timeout)

func open(event: Dictionary) -> void:
	_segments = _build_segments(event)
	if _segments.is_empty():
		_segments = [{
			"speaker_id": "", "speaker_name": "", "line_type": TYPE_NARRATION,
			"position": "center", "text": "（这里暂时没有可演出的内容。）",
		}]
	_index = 0
	_auto = false
	auto_button.text = "自动：关"
	_history.clear()
	_clear_log()
	log_panel.visible = false
	location_label.text = String(event.get("location_label", ""))
	body_text.add_theme_font_size_override("normal_font_size", _event_font_size())
	var loc_id: String = String(event.get("location_id", ""))
	background.color = LOCATION_BG.get(loc_id, Color(0.06, 0.07, 0.1, 1))
	var show_skip: bool = bool(Settings.get_value("text", "skip_read"))
	skip_button.visible = show_skip
	_setup_slots()
	visible = true
	_show_line()

func _build_segments(event: Dictionary) -> Array:
	var segs: Array = event.get("dialogue_segments", [])
	if not segs.is_empty():
		return segs.duplicate(true)
	# 回退：把 narrative_segments 当作旁白逐句呈现。
	var fallback: Array = []
	for line in event.get("narrative_segments", []):
		fallback.append({
			"speaker_id": "", "speaker_name": "", "line_type": TYPE_NARRATION,
			"position": "center", "text": String(line),
		})
	return fallback

# 扫描全部对话，给左右两个立绘槽分配固定占位的角色。
func _setup_slots() -> void:
	_slot_pos.clear()
	for seg in _segments:
		var pos: String = String(seg.get("position", "center"))
		if pos != "left" and pos != "right":
			continue
		var id: String = String(seg.get("speaker_id", ""))
		if id == "":
			continue
		if not _slot_pos.has(pos):
			_slot_pos[pos] = {"id": id, "name": String(seg.get("speaker_name", id))}
	_apply_slot(slot_left, slot_left_portrait, slot_left_initial, slot_left_name, _slot_pos.get("left", {}))
	_apply_slot(slot_right, slot_right_portrait, slot_right_initial, slot_right_name, _slot_pos.get("right", {}))

func _apply_slot(slot: Control, portrait: ColorRect, initial: Label, name_tag: Label, data: Dictionary) -> void:
	if data.is_empty():
		slot.visible = false
		return
	var was_visible := slot.visible
	slot.visible = true
	var nm: String = String(data.get("name", ""))
	portrait.color = _color_for(String(data.get("id", "")))
	initial.text = _initial_of(nm)
	name_tag.text = nm
	if not was_visible and not _reduce_motion():
		_slot_enter_tween(slot)

func _show_line() -> void:
	var seg: Dictionary = _segments[_index]
	var line_type: String = String(seg.get("line_type", TYPE_NARRATION))
	var pos: String = String(seg.get("position", "center"))
	var nm: String = String(seg.get("speaker_name", ""))
	var id: String = String(seg.get("speaker_id", ""))
	var text: String = String(seg.get("text", ""))

	_highlight_active(pos, line_type)

	# 对话框头像 / 名字 / 类型标签
	match line_type:
		TYPE_NARRATION:
			avatar.visible = false
			speaker_label.text = "旁白"
			type_tag.text = ""
		TYPE_THOUGHT:
			avatar.visible = true
			avatar.color = _color_for(id)
			avatar_initial.text = _initial_of(nm)
			speaker_label.text = nm
			type_tag.text = "· 心声"
		_:
			avatar.visible = true
			avatar.color = _color_for(id)
			avatar_initial.text = _initial_of(nm)
			speaker_label.text = nm
			type_tag.text = ""

	var display := text
	if line_type == TYPE_NARRATION:
		display = "[i]%s[/i]" % text
	body_text.text = display
	_full_len = body_text.get_total_character_count()
	_history.append({"name": speaker_label.text, "type": line_type, "text": text})

	continue_hint.visible = false
	progress_label.text = "%d / %d" % [_index + 1, _segments.size()]

	if _is_instant():
		body_text.visible_characters = -1
		_typing = false
		_on_line_complete()
	else:
		body_text.visible_characters = 0
		_char_progress = 0.0
		_cps = TYPING_CPS.get(_typing_speed(), 36.0)
		_typing = true

func _process(delta: float) -> void:
	if not _typing:
		return
	_char_progress += delta * _cps
	var vc := int(_char_progress)
	if vc >= _full_len:
		body_text.visible_characters = -1
		_typing = false
		_on_line_complete()
	else:
		body_text.visible_characters = vc

func _on_line_complete() -> void:
	var last := _index >= _segments.size() - 1
	continue_hint.text = "▼ 点击结束" if last else "▼ 点击 / 空格 继续"
	continue_hint.visible = true
	if _auto:
		auto_timer.start(AUTO_WAIT.get(_auto_speed(), 1.5))

func _advance() -> void:
	if log_panel.visible:
		return
	auto_timer.stop()
	if _typing:
		body_text.visible_characters = -1
		_typing = false
		_on_line_complete()
		return
	_index += 1
	if _index >= _segments.size():
		_finish()
	else:
		_show_line()

func _highlight_active(pos: String, line_type: String) -> void:
	var left_active := pos == "left" and line_type != TYPE_NARRATION
	var right_active := pos == "right" and line_type != TYPE_NARRATION
	_set_slot_active(slot_left, slot_left_active, left_active)
	_set_slot_active(slot_right, slot_right_active, right_active)

func _set_slot_active(slot: Control, active_tag: Label, active: bool) -> void:
	if not slot.visible:
		return
	# 亮度 + 缩放 + 文字「发言中」三重提示，避免仅靠颜色。
	slot.modulate = Color(1, 1, 1, 1) if active else Color(0.5, 0.5, 0.55, 1)
	slot.scale = Vector2(1.0, 1.0) if active else Vector2(0.94, 0.94)
	active_tag.visible = active

func _toggle_log() -> void:
	if not log_panel.visible:
		_rebuild_log()
	log_panel.visible = not log_panel.visible

func _rebuild_log() -> void:
	_clear_log()
	for entry in _history:
		var row := Label.new()
		row.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var nm: String = String(entry.get("name", ""))
		var tp: String = String(entry.get("type", TYPE_SPEECH))
		var txt: String = String(entry.get("text", ""))
		if tp == TYPE_NARRATION:
			row.text = txt
		elif tp == TYPE_THOUGHT:
			row.text = "%s（心声）：%s" % [nm, txt]
		else:
			row.text = "%s：%s" % [nm, txt]
		log_container.add_child(row)

func _clear_log() -> void:
	for child in log_container.get_children():
		child.queue_free()

func _toggle_auto() -> void:
	_auto = not _auto
	auto_button.text = "自动：开" if _auto else "自动：关"
	if _auto and not _typing:
		auto_timer.start(AUTO_WAIT.get(_auto_speed(), 1.5))
	elif not _auto:
		auto_timer.stop()

func _on_auto_timeout() -> void:
	if _auto and not log_panel.visible:
		_advance()

func _finish() -> void:
	auto_timer.stop()
	_typing = false
	if not _reduce_motion():
		_slot_exit_tween(slot_left)
		_slot_exit_tween(slot_right)
		await get_tree().create_timer(0.25).timeout
	visible = false
	finished.emit()

func _skip_all() -> void:
	auto_timer.stop()
	_typing = false
	_index = _segments.size()
	_finish()

func _slot_enter_tween(slot: Control) -> void:
	slot.modulate = Color(1, 1, 1, 0)
	slot.scale = Vector2(0.9, 0.9)
	var t := create_tween().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	t.tween_property(slot, "modulate:a", 1.0, 0.3)
	t.parallel().tween_property(slot, "scale", Vector2(1, 1), 0.3)

func _slot_exit_tween(slot: Control) -> void:
	if not slot.visible:
		return
	var t := create_tween().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	t.tween_property(slot, "modulate:a", 0.0, 0.2)

func _reduce_motion() -> bool:
	return bool(Settings.get_value("accessibility", "reduce_motion"))

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("ui_cancel"):
		if log_panel.visible:
			_toggle_log()
		else:
			_finish()
		get_viewport().set_input_as_handled()
		return
	if event.is_action_pressed("ui_accept"):
		_advance()
		get_viewport().set_input_as_handled()

func _gui_input(event: InputEvent) -> void:
	# 根节点 mouse_filter=STOP，拦截点击避免穿透到背后的 HUD；空白处点击=推进。
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_advance()
		accept_event()

func _color_for(id: String) -> Color:
	if id == "":
		return Color(0.4, 0.4, 0.45)
	var h: int = abs(hash(id))
	var hue := float(h % 360) / 360.0
	return Color.from_hsv(hue, 0.45, 0.72)

func _initial_of(nm: String) -> String:
	if nm.is_empty():
		return "?"
	return nm.substr(0, 1)

func _is_instant() -> bool:
	if bool(Settings.get_value("accessibility", "reduce_motion")):
		return true
	if bool(Settings.get_value("text", "skip_read")):
		return true
	return false

func _typing_speed() -> int:
	return int(Settings.get_value("text", "typing_speed"))

func _auto_speed() -> int:
	return int(Settings.get_value("text", "auto_speed"))

func _event_font_size() -> int:
	return FONT_SIZE.get(int(Settings.get_value("text", "event_font_size")), 22)
