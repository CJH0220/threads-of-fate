extends Control

## 时间推进「命运流转」过渡覆盖层 + 内嵌结算摘要。
## 职责：播放旧→新时段的过渡动画，并在同一面板内逐条展示资源变化、人物变化与事件结果。
## 面板在动画结束后保持可见，直到玩家点击「继续」按钮关闭。

signal finished()

@onready var title_label: Label = $Center/VBox/TitleLabel
@onready var thread: ColorRect = $Center/VBox/ThreadTrack/Thread
@onready var time_label: Label = $Center/VBox/TimeLabel
@onready var settlement_box: PanelContainer = $Center/VBox/SettlementBox
@onready var resource_container: VBoxContainer = $Center/VBox/SettlementBox/ScrollContainer/ScrollInner/ResourceSection/ResourceList
@onready var character_container: VBoxContainer = $Center/VBox/SettlementBox/ScrollContainer/ScrollInner/CharacterSection/CharacterList
@onready var event_container: VBoxContainer = $Center/VBox/SettlementBox/ScrollContainer/ScrollInner/EventSection/EventList
@onready var close_button: Button = $Center/VBox/CloseButton

## 资源字段 → 中文展示名。
const RESOURCE_NAMES: Dictionary = {
	"incense": "香火",
	"divine_power": "神力",
	"yang_de": "阳德",
	"yin_de": "阴德",
}

func _ready() -> void:
	if close_button != null:
		close_button.pressed.connect(_on_close_pressed)
	visible = false

func _on_close_pressed() -> void:
	_hide_now()

## 加载态：立刻弹出"命运流转中……"提示，等待后端返回。
## 不显示继续按钮、不绑定 finished，仅作为 loading 遮罩。
## 调用方在后端返回后须调用 play(before, after, settlement_data) 补上结算与继续按钮。
func show_loading(before_label: String) -> void:
	visible = true
	modulate = Color(1, 1, 1, 1)
	title_label.text = "命运流转中……"
	time_label.text = before_label
	if close_button != null:
		close_button.visible = false
	## 织线动画预置为半态,营造"进行中"的错觉
	thread.scale = Vector2(0.35, 1)
	thread.modulate = Color(1, 1, 1, 0.8)
	## loading 阶段不渲染结算内容
	if settlement_box != null:
		settlement_box.visible = false

## 兼容老调用：只传两个 label 也能跑，settlement_data 用默认空字典。
func play(before_label: String, after_label: String, settlement_data: Dictionary = {}) -> void:
	visible = true
	modulate = Color(1, 1, 1, 1)
	title_label.text = "命运流转中……"
	time_label.text = before_label
	if close_button != null:
		close_button.visible = false
	_render_settlement(settlement_data)

	if _reduce_motion():
		thread.scale = Vector2(1, 1)
		thread.modulate = Color(1, 1, 1, 1)
		time_label.text = _time_text(before_label, after_label)
		title_label.text = "命运流转"
		if close_button != null:
			close_button.visible = true
		## 等待玩家点击「继续」
		await finished
		return

	# 阶段一：命运织线生长。
	thread.scale = Vector2(0, 1)
	thread.modulate = Color(1, 1, 1, 0.9)
	var grow := create_tween()
	grow.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	grow.tween_property(thread, "scale", Vector2(1, 1), 0.7)
	await grow.finished

	# 阶段二：揭示旧→新时段。
	time_label.text = _time_text(before_label, after_label)
	title_label.text = "命运流转"
	var pulse := create_tween()
	pulse.tween_property(thread, "modulate:a", 0.45, 0.5)
	await get_tree().create_timer(0.5).timeout

	# 显示关闭按钮，等待玩家查看
	if close_button != null:
		close_button.visible = true

	## 等待玩家点击「继续」按钮关闭面板
	await finished

func _hide_now() -> void:
	visible = false
	modulate = Color(1, 1, 1, 1)
	if close_button != null:
		close_button.visible = false
	finished.emit()

func _time_text(before_label: String, after_label: String) -> String:
	if before_label == after_label:
		return before_label
	return "%s    →    %s" % [before_label, after_label]

func _reduce_motion() -> bool:
	return bool(Settings.get_value("accessibility", "reduce_motion"))

# ─────────────────────────────────────────────────────────────
# 结算摘要渲染
# ─────────────────────────────────────────────────────────────

## settlement_data 期望字段：
##   resource_change_log: Array           —— [{resource, change, reason}, ...] 逐条变化
##   resource_delta: Dictionary           —— {incense: int, divine_power: int, ...} 汇总差量（兜底）
##   before_resources: Dictionary         —— 推进前的快照，用于显示「16→13」形式
##   character_changes: Array             —— 编剧 Agent 填写；空数组走占位
##   event_changes: Array                 —— 编剧 Agent 填写；空数组走占位
func _render_settlement(data: Dictionary) -> void:
	if data.is_empty():
		settlement_box.visible = false
		return
	settlement_box.visible = true
	var change_log: Array = Array(data.get("resource_change_log", []))
	if not change_log.is_empty():
		_render_resource_changes(change_log, Dictionary(data.get("before_resources", {})))
	else:
		## 兜底：用汇总差量展示
		_render_resources(
			Dictionary(data.get("resource_delta", {})),
			Dictionary(data.get("before_resources", {})),
		)
	_render_character_changes(Array(data.get("character_changes", [])))
	_render_event_changes(Array(data.get("event_changes", [])))

## 逐条展示资源变化：每一次干预/赐福/托梦单独一行。
func _render_resource_changes(log: Array, before: Dictionary) -> void:
	_clear_children(resource_container)
	## 逐条展示，同时追踪累计值用于显示「当前值」
	var running: Dictionary = before.duplicate()
	for entry in log:
		var res_key: String = String(entry.get("resource", ""))
		var change: int = int(entry.get("change", 0))
		var reason: String = String(entry.get("reason", ""))
		if change == 0:
			continue
		var before_val: int = int(running.get(res_key, 0))
		running[res_key] = before_val + change
		var row := _make_change_row(res_key, change, reason, before_val, int(running.get(res_key, 0)))
		resource_container.add_child(row)
	## 底部汇总行
	var total_delta: Dictionary = {}
	for entry in log:
		var rk: String = String(entry.get("resource", ""))
		total_delta[rk] = int(total_delta.get(rk, 0)) + int(entry.get("change", 0))
	var has_any: bool = false
	for key in ["incense", "divine_power", "yang_de", "yin_de"]:
		var total: int = int(total_delta.get(key, 0))
		if total != 0:
			has_any = true
	if has_any:
		var sep := HSeparator.new()
		resource_container.add_child(sep)
		for key in ["incense", "divine_power", "yang_de", "yin_de"]:
			var total: int = int(total_delta.get(key, 0))
			if total == 0:
				continue
			var summary_row := HBoxContainer.new()
			summary_row.add_theme_constant_override("separation", 8)
			var name_label := Label.new()
			name_label.custom_minimum_size = Vector2(64, 0)
			name_label.text = RESOURCE_NAMES.get(key, key)
			name_label.add_theme_font_size_override("font_size", 14)
			name_label.add_theme_color_override("font_color", Color(1, 0.9, 0.65, 1))
			summary_row.add_child(name_label)
			var b_val: int = int(before.get(key, 0))
			var a_val: int = b_val + total
			var arrow_label := Label.new()
			arrow_label.text = "%d → %d" % [b_val, a_val]
			arrow_label.add_theme_font_size_override("font_size", 14)
			arrow_label.add_theme_color_override("font_color", Color(0.93, 0.93, 0.9, 1))
			summary_row.add_child(arrow_label)
			var delta_label := Label.new()
			delta_label.text = "(%s%d)" % ["+" if total > 0 else "", total]
			delta_label.add_theme_font_size_override("font_size", 13)
			var delta_color: Color = Color(0.7, 0.95, 0.7, 1) if total > 0 else Color(0.95, 0.72, 0.72, 1)
			delta_label.add_theme_color_override("font_color", delta_color)
			summary_row.add_child(delta_label)
			resource_container.add_child(summary_row)
	if not has_any and log.is_empty():
		var hint := Label.new()
		hint.text = "  本时段资源无变化"
		hint.add_theme_color_override("font_color", Color(0.72, 0.75, 0.82, 1))
		hint.add_theme_font_size_override("font_size", 13)
		resource_container.add_child(hint)

## 单条变化行：「原因 · 资源名 ±N (前→后)」。
func _make_change_row(res_key: String, change: int, reason: String, before_val: int, after_val: int) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	var reason_label := Label.new()
	reason_label.text = reason if reason != "" else RESOURCE_NAMES.get(res_key, res_key)
	reason_label.add_theme_font_size_override("font_size", 13)
	reason_label.add_theme_color_override("font_color", Color(0.85, 0.85, 0.82, 1))
	reason_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	reason_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	row.add_child(reason_label)
	var delta_label := Label.new()
	delta_label.text = "%s %s%d" % [RESOURCE_NAMES.get(res_key, res_key), "+" if change > 0 else "", change]
	delta_label.add_theme_font_size_override("font_size", 13)
	var delta_color: Color = Color(0.7, 0.95, 0.7, 1) if change > 0 else Color(0.95, 0.72, 0.72, 1)
	delta_label.add_theme_color_override("font_color", delta_color)
	row.add_child(delta_label)
	var value_label := Label.new()
	value_label.text = "%d→%d" % [before_val, after_val]
	value_label.add_theme_font_size_override("font_size", 12)
	value_label.add_theme_color_override("font_color", Color(0.72, 0.75, 0.82, 1))
	row.add_child(value_label)
	return row

## 兜底：汇总差量展示（当没有逐条日志时使用）。
func _render_resources(delta: Dictionary, before: Dictionary) -> void:
	_clear_children(resource_container)
	var any_row := false
	for key in ["incense", "divine_power", "yang_de", "yin_de"]:
		var change: int = int(delta.get(key, 0))
		if change == 0:
			continue
		any_row = true
		var row := _make_resource_row(key, change, int(before.get(key, 0)))
		resource_container.add_child(row)
	if not any_row:
		var hint := Label.new()
		hint.text = "  本时段资源无变化"
		hint.add_theme_color_override("font_color", Color(0.72, 0.75, 0.82, 1))
		hint.add_theme_font_size_override("font_size", 13)
		resource_container.add_child(hint)

func _make_resource_row(key: String, change: int, before_value: int) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var name_label := Label.new()
	name_label.custom_minimum_size = Vector2(64, 0)
	name_label.text = RESOURCE_NAMES.get(key, key)
	name_label.add_theme_font_size_override("font_size", 14)
	name_label.add_theme_color_override("font_color", Color(1, 0.9, 0.65, 1))
	row.add_child(name_label)
	var arrow_label := Label.new()
	var after_value: int = before_value + change
	arrow_label.text = "%d → %d" % [before_value, after_value]
	arrow_label.add_theme_font_size_override("font_size", 14)
	arrow_label.add_theme_color_override("font_color", Color(0.93, 0.93, 0.9, 1))
	row.add_child(arrow_label)
	var delta_label := Label.new()
	delta_label.text = "(%s%d)" % ["+" if change > 0 else "", change]
	delta_label.add_theme_font_size_override("font_size", 13)
	var delta_color: Color = Color(0.7, 0.95, 0.7, 1) if change > 0 else Color(0.95, 0.72, 0.72, 1)
	delta_label.add_theme_color_override("font_color", delta_color)
	row.add_child(delta_label)
	return row

func _render_character_changes(changes: Array) -> void:
	_clear_children(character_container)
	if changes.is_empty():
		var hint := Label.new()
		hint.text = "  （编剧 Agent 待总结人物状态变化）"
		hint.add_theme_color_override("font_color", Color(0.55, 0.58, 0.65, 1))
		hint.add_theme_font_size_override("font_size", 13)
		character_container.add_child(hint)
		return
	for change in changes:
		var row := Label.new()
		row.text = "  %s：%s" % [
			String(change.get("character_name", "未知居民")),
			String(change.get("change", "状态变化")),
		]
		row.add_theme_font_size_override("font_size", 14)
		character_container.add_child(row)

func _render_event_changes(changes: Array) -> void:
	_clear_children(event_container)
	if changes.is_empty():
		var hint := Label.new()
		hint.text = "  （编剧 Agent 待总结本时段事件结果）"
		hint.add_theme_color_override("font_color", Color(0.55, 0.58, 0.65, 1))
		hint.add_theme_font_size_override("font_size", 13)
		event_container.add_child(hint)
		return
	for change in changes:
		var row := Label.new()
		row.text = "  %s：%s" % [
			String(change.get("event_name", "未知事件")),
			String(change.get("outcome", "已解决")),
		]
		row.add_theme_font_size_override("font_size", 14)
		event_container.add_child(row)

func _clear_children(node: Node) -> void:
	for child in node.get_children():
		child.queue_free()
