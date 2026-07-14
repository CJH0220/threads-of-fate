extends Control
class_name BlessingDecisionDialog

## 演出内关键抉择弹窗。
## 由 DialogueEventScreen 在含 blessing_prompt 的对话段暂停时打开。
## 显示：目的 / 难度 / 消耗 / 成功效果 / 失败效果；玩家选择「赐福」或「不干预」。
## 神力不足时「赐福」按钮置灰；关闭动作等价于「不干预」。

signal blessing_decided(bless: bool)

@onready var purpose_label: Label = $Panel/VBox/PurposeLabel
@onready var difficulty_label: Label = $Panel/VBox/DifficultyLabel
@onready var cost_label: Label = $Panel/VBox/CostLabel
@onready var success_label: Label = $Panel/VBox/SuccessLabel
@onready var failure_label: Label = $Panel/VBox/FailureLabel
@onready var hint_label: Label = $Panel/VBox/HintLabel
@onready var skip_button: Button = $Panel/VBox/ButtonRow/SkipButton
@onready var bless_button: Button = $Panel/VBox/ButtonRow/BlessButton

var _decided: bool = false

func _ready() -> void:
	visible = false
	skip_button.pressed.connect(_on_skip)
	bless_button.pressed.connect(_on_bless)

## 打开弹窗。prompt 期望字段：
##   purpose, difficulty_text, difficulty_value, cost,
##   success_effect, failure_effect
func open(prompt: Dictionary, divine_power: int) -> void:
	_decided = false
	purpose_label.text = "目的：%s" % String(prompt.get("purpose", "—"))
	var diff_text: String = String(prompt.get("difficulty_text", ""))
	if diff_text == "":
		diff_text = "需求 %d 面 · 抛硬币判定" % int(prompt.get("difficulty_value", 1))
	difficulty_label.text = "难度：%s" % diff_text
	var cost: int = int(prompt.get("cost", 3))
	cost_label.text = "消耗：%d 神力（当前 %d）" % [cost, divine_power]
	success_label.text = "成功：%s" % String(prompt.get("success_effect", "—"))
	failure_label.text = "失败：%s" % String(prompt.get("failure_effect", "—"))

	if divine_power < cost:
		bless_button.disabled = true
		bless_button.tooltip_text = "神力不足，无法赐福。"
		hint_label.text = "神力不足，无法赐福 —— 命运将顺其自然。"
	else:
		bless_button.disabled = false
		bless_button.tooltip_text = ""
		hint_label.text = "命运只会被轻推，结果未必如愿。"

	visible = true

func _on_skip() -> void:
	_finish(false)

func _on_bless() -> void:
	if bless_button.disabled:
		return
	_finish(true)

func _finish(bless: bool) -> void:
	if _decided:
		return
	_decided = true
	visible = false
	blessing_decided.emit(bless)

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("ui_cancel"):
		_finish(false)
		get_viewport().set_input_as_handled()
