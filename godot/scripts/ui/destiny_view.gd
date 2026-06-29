extends Control

## 业线视图覆盖层。每条业线显示 NPC / karma_summary / 进度条 / 风险 / 当前状态。
## 筛选：全部 / 有风险 / 指定 NPC。点人物名 emit character_selected 由 HUD 开人物弹窗。
## 进度 >= 100 时给「查看结局」入口 emit ending_requested。

signal closed()
signal character_selected(npc_id: String)
signal ending_requested(npc_id: String)

const RISK_LABELS := {
	"Low": "● 平稳",
	"Medium": "●● 留意",
	"High": "●●● 危险",
	"Fatal": "●●●● 致命",
}

const FILTER_ALL := 0
const FILTER_RISK := 1

@onready var back_button: Button = $Dim/Panel/VBox/Header/BackButton
@onready var filter_option: OptionButton = $Dim/Panel/VBox/FilterBar/FilterOption
@onready var list_container: VBoxContainer = $Dim/Panel/VBox/ListScroll/ListContainer
@onready var empty_label: Label = $Dim/Panel/VBox/EmptyLabel

var _characters: Array = []
var _filter_mode := FILTER_ALL
var _filter_npc_id := ""

func _ready() -> void:
	visible = false
	back_button.pressed.connect(_close)
	filter_option.item_selected.connect(_on_filter_selected)

func open(characters: Array) -> void:
	_characters = characters
	_filter_mode = FILTER_ALL
	_filter_npc_id = ""
	_build_filter()
	_rebuild_list()
	visible = true
	back_button.grab_focus()

func close() -> void:
	visible = false

func _close() -> void:
	close()
	closed.emit()

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("ui_cancel"):
		_close()
		get_viewport().set_input_as_handled()

func _build_filter() -> void:
	filter_option.clear()
	filter_option.add_item("全部业线", 0)
	filter_option.set_item_metadata(0, {"mode": FILTER_ALL})
	filter_option.add_item("仅有风险", 1)
	filter_option.set_item_metadata(1, {"mode": FILTER_RISK})
	var idx := 2
	for character in _characters:
		if not bool(character.get("is_unlocked", true)):
			continue
		if String(character.get("karma_summary", "")) == "":
			continue
		filter_option.add_item(String(character.get("display_name", "未知")), idx)
		filter_option.set_item_metadata(idx, {"mode": FILTER_ALL, "npc_id": String(character.get("npc_id", ""))})
		idx += 1
	filter_option.select(0)

func _on_filter_selected(index: int) -> void:
	var meta: Dictionary = filter_option.get_item_metadata(index)
	_filter_mode = int(meta.get("mode", FILTER_ALL))
	_filter_npc_id = String(meta.get("npc_id", ""))
	_rebuild_list()

func _is_risky(character: Dictionary) -> bool:
	var risk: String = String(character.get("risk_level", "Low"))
	return risk == "High" or risk == "Fatal"

func _rebuild_list() -> void:
	for child in list_container.get_children():
		child.queue_free()

	var any_shown := false
	for character in _characters:
		if not bool(character.get("is_unlocked", true)):
			continue
		if String(character.get("karma_summary", "")) == "":
			continue
		var npc_id: String = String(character.get("npc_id", ""))
		if _filter_npc_id != "" and npc_id != _filter_npc_id:
			continue
		if _filter_mode == FILTER_RISK and not _is_risky(character):
			continue
		_add_card(character)
		any_shown = true

	empty_label.visible = not any_shown

func _add_card(character: Dictionary) -> void:
	var npc_id: String = String(character.get("npc_id", ""))
	var display_name: String = String(character.get("display_name", "未知居民"))
	var karma_summary: String = String(character.get("karma_summary", "未知业线"))
	var progress: int = int(character.get("karma_progress", 0))
	var risk: String = String(character.get("risk_level", "Low"))
	var current_state: String = String(character.get("current_state", ""))

	var name_button := Button.new()
	name_button.text = "%s — %s" % [display_name, karma_summary]
	name_button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	name_button.pressed.connect(func() -> void: character_selected.emit(npc_id))
	list_container.add_child(name_button)

	var bar := ProgressBar.new()
	bar.min_value = 0
	bar.max_value = 100
	bar.value = progress
	bar.custom_minimum_size = Vector2(0, 20)
	list_container.add_child(bar)

	var info := Label.new()
	info.text = "进度 %d%%   风险 %s" % [progress, RISK_LABELS.get(risk, risk)]
	list_container.add_child(info)

	if current_state != "":
		var state_label := Label.new()
		state_label.text = "状态：%s" % current_state
		state_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		list_container.add_child(state_label)

	if progress >= 100:
		var ending_button := Button.new()
		ending_button.text = "查看角色结局"
		ending_button.pressed.connect(func() -> void: ending_requested.emit(npc_id))
		list_container.add_child(ending_button)

	list_container.add_child(HSeparator.new())
