extends Control

## 缘线视图覆盖层。按人物分组列出其 bond_summaries（对象 / 性质 / 等级 / 强度）。
## 性质用「符号 + 文字」表达，不依赖颜色。点人物名 emit character_selected 由 HUD 开人物弹窗。

signal closed()
signal character_selected(npc_id: String)

const BOND_SYMBOLS := {
	"友情": "🤝",
	"爱情": "❤",
	"恋情": "❤",
	"亲情": "🏠",
	"敌对": "⚔",
	"竞争": "⚔",
	"师徒": "📖",
	"信仰": "🕯",
}

@onready var back_button: Button = $Dim/Panel/VBox/Header/BackButton
@onready var filter_option: OptionButton = $Dim/Panel/VBox/FilterBar/FilterOption
@onready var list_container: VBoxContainer = $Dim/Panel/VBox/ListScroll/ListContainer
@onready var empty_label: Label = $Dim/Panel/VBox/EmptyLabel

var _characters: Array = []
var _filter_npc_id := ""

func _ready() -> void:
	visible = false
	back_button.pressed.connect(_close)
	filter_option.item_selected.connect(_on_filter_selected)

func open(characters: Array) -> void:
	_characters = characters
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
	filter_option.add_item("全部居民", 0)
	var idx := 1
	for character in _characters:
		if not bool(character.get("is_unlocked", true)):
			continue
		var bonds: Array = character.get("bond_summaries", [])
		if bonds.is_empty():
			continue
		filter_option.add_item(String(character.get("display_name", "未知")), idx)
		filter_option.set_item_metadata(idx, String(character.get("npc_id", "")))
		idx += 1
	filter_option.select(0)

func _on_filter_selected(index: int) -> void:
	if index == 0:
		_filter_npc_id = ""
	else:
		_filter_npc_id = String(filter_option.get_item_metadata(index))
	_rebuild_list()

func _rebuild_list() -> void:
	for child in list_container.get_children():
		child.queue_free()

	var any_shown := false
	for character in _characters:
		if not bool(character.get("is_unlocked", true)):
			continue
		var npc_id: String = String(character.get("npc_id", ""))
		if _filter_npc_id != "" and npc_id != _filter_npc_id:
			continue
		var bonds: Array = character.get("bond_summaries", [])
		if bonds.is_empty():
			continue
		_add_group(character, bonds)
		any_shown = true

	empty_label.visible = not any_shown

func _add_group(character: Dictionary, bonds: Array) -> void:
	var npc_id: String = String(character.get("npc_id", ""))
	var display_name: String = String(character.get("display_name", "未知居民"))

	var name_button := Button.new()
	name_button.text = "%s 的缘线" % display_name
	name_button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	name_button.theme_type_variation = "FlatButton"
	name_button.pressed.connect(func() -> void: _on_name_pressed(npc_id))
	list_container.add_child(name_button)

	for bond in bonds:
		var entry := Button.new()
		entry.text = "    %s" % _format_bond(bond)
		entry.alignment = HORIZONTAL_ALIGNMENT_LEFT
		var target_id: String = String(bond.get("target_npc_id", ""))
		entry.pressed.connect(func() -> void: _on_name_pressed(target_id))
		list_container.add_child(entry)

	list_container.add_child(HSeparator.new())

func _format_bond(bond: Dictionary) -> String:
	var bond_type: String = String(bond.get("bond_type", "羁绊"))
	var symbol: String = BOND_SYMBOLS.get(bond_type, "•")
	var target: String = String(bond.get("target_display_name", "未知"))
	var level: int = int(bond.get("level", 0))
	var strength: int = int(bond.get("strength", 0))
	return "%s %s · %s · Lv.%d · 强度 %d" % [symbol, target, bond_type, level, strength]

func _on_name_pressed(npc_id: String) -> void:
	if npc_id == "":
		return
	character_selected.emit(npc_id)
