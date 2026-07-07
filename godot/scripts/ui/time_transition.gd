extends Control

## 时间推进「命运流转」过渡覆盖层。
## 纯演出节拍：显示「命运流转中……」与旧→新时段，随后自动淡出。
## 真正的变化摘要由其后的 SettlementPanel 呈现，这里不重复列变化。

signal finished()

@onready var title_label: Label = $Center/VBox/TitleLabel
@onready var thread: ColorRect = $Center/VBox/ThreadTrack/Thread
@onready var time_label: Label = $Center/VBox/TimeLabel

func _ready() -> void:
	visible = false

func play(before_label: String, after_label: String) -> void:
	visible = true
	modulate = Color(1, 1, 1, 1)
	title_label.text = "命运流转中……"
	time_label.text = before_label

	if _reduce_motion():
		thread.scale = Vector2(1, 1)
		thread.modulate = Color(1, 1, 1, 1)
		time_label.text = _time_text(before_label, after_label)
		await get_tree().create_timer(0.5).timeout
		_hide_now()
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
	var pulse := create_tween()
	pulse.tween_property(thread, "modulate:a", 0.45, 0.5)
	await get_tree().create_timer(0.7).timeout

	# 淡出。
	var fade := create_tween()
	fade.tween_property(self, "modulate:a", 0.0, 0.35)
	await fade.finished
	_hide_now()

func _hide_now() -> void:
	visible = false
	modulate = Color(1, 1, 1, 1)
	finished.emit()

func _time_text(before_label: String, after_label: String) -> String:
	if before_label == after_label:
		return before_label
	return "%s    →    %s" % [before_label, after_label]

func _reduce_motion() -> bool:
	return bool(Settings.get_value("accessibility", "reduce_motion"))
