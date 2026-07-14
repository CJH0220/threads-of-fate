extends VBoxContainer
class_name CharacterPanel

signal chat_requested(npc_id: String, display_name: String)
## 玩家在角色框点击「托梦」按钮，请求外层弹起托梦文字输入对话框。
## MainGameUI 会做真正的执行 —— 面板本身不消费神力也不写记忆。
signal dream_requested(npc_id: String, display_name: String)

@onready var name_label: Label = $Header/HeaderText/NameLabel
@onready var role_label: Label = $Header/HeaderText/RoleLabel
@onready var chat_button: Button = $Header/ChatButton
@onready var portrait_panel: PanelContainer = $Header/Portrait
@onready var portrait_image: TextureRect = $Header/Portrait/PortraitImage
@onready var portrait_initial: Label = $Header/Portrait/PortraitInitial
@onready var bio_text: RichTextLabel = $BioText
@onready var identity_label: Label = $IdentitySection/IdentityLabel
@onready var traits_row: HBoxContainer = $IdentitySection/TraitsScroll/TraitsRow
@onready var backstory_label: Label = $IdentitySection/BackstoryLabel
@onready var state_label: Label = $StatsSection/StateLabel
@onready var stats_row: HBoxContainer = $StatsSection/StatsRow
@onready var bond_container: VBoxContainer = $BondSection/BondContainer
@onready var karma_label: Label = $KarmaSection/KarmaLabel

var _npc_id: String = ""
var _display_name: String = ""
## 动态添加的托梦按钮（因原 .tscn 里没有节点，运行时注入到 Header 中 chat_button 之前）。
var _dream_button: Button = null
## 当前各能力值（用于 +/- 按钮的基准）。
var _stats: Dictionary = {}

func _ready() -> void:
	if chat_button != null:
		chat_button.pressed.connect(_on_chat_pressed)
	_ensure_dream_button()

func _on_chat_pressed() -> void:
	if _npc_id == "":
		return
	chat_requested.emit(_npc_id, _display_name)

func show_character(character: Dictionary, dream_ctx: Dictionary = {}) -> void:
	_npc_id = String(character.get("npc_id", ""))
	_display_name = String(character.get("display_name", "未知居民"))
	name_label.text = _display_name
	role_label.text = "%s｜%s" % [
		character.get("role", "身份未知"),
		character.get("age_range", ""),
	]
	if chat_button != null:
		chat_button.disabled = _npc_id == ""
	_apply_portrait(_npc_id, _display_name)
	_render_identity(character)
	bio_text.text = character.get("description", "暂无简介。")
	_update_dream_button(dream_ctx)

	state_label.text = character.get("current_state", "暂无状态。")

	_stats = character.get("stats", {})
	_render_stats_row()

	for child in bond_container.get_children():
		child.queue_free()
	var bonds: Array = character.get("bond_summaries", [])
	if bonds.is_empty():
		var empty_label := Label.new()
		empty_label.text = "暂无明确关系。"
		bond_container.add_child(empty_label)
	else:
		for bond in bonds:
			bond_container.add_child(_make_bond_row(bond))

	karma_label.text = "%s（%d%%）" % [
		character.get("karma_summary", "命运尚未显形"),
		character.get("karma_progress", 0),
	]

## 应用头像：优先 PortraitService 加载纹理；缺图时以色块 + 首字兜底。
func _apply_portrait(npc_id: String, display_name: String) -> void:
	if portrait_image == null:
		return
	var tex: Texture2D = PortraitService.get_portrait(npc_id)
	if tex != null:
		portrait_image.texture = tex
		portrait_image.visible = true
		portrait_initial.visible = false
	else:
		portrait_image.texture = null
		portrait_image.visible = false
		portrait_initial.text = PortraitService.get_initial(display_name)
		portrait_initial.modulate = PortraitService.get_color(npc_id)
		portrait_initial.visible = true

## 一条羁绊：小头像 + 关系文字。
func _make_bond_row(bond: Dictionary) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	var target_id: String = String(bond.get("target_npc_id", ""))
	var target_name: String = String(bond.get("target_display_name", "未知居民"))
	var avatar := _make_bond_avatar(target_id, target_name)
	row.add_child(avatar)
	var text_label := Label.new()
	text_label.text = "%s｜%s Lv.%d｜强度 %d" % [
		target_name,
		bond.get("bond_type", "陌生"),
		bond.get("level", 0),
		bond.get("strength", 0),
	]
	text_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(text_label)
	return row

const BOND_AVATAR_SIZE: int = 28

func _make_bond_avatar(npc_id: String, display_name: String) -> Control:
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(BOND_AVATAR_SIZE, BOND_AVATAR_SIZE)
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.set_corner_radius_all(BOND_AVATAR_SIZE / 2)
	style.set_border_width_all(1)
	style.border_color = Color(0.82, 0.72, 0.48, 0.7)
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
		initial.add_theme_font_size_override("font_size", 13)
		initial.add_theme_color_override("font_color", PortraitService.get_color(npc_id))
		initial.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		initial.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		initial.mouse_filter = Control.MOUSE_FILTER_IGNORE
		initial.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		initial.size_flags_vertical = Control.SIZE_EXPAND_FILL
		panel.add_child(initial)
	return panel

## 渲染能力值行：只读展示每项数值。
func _render_stats_row() -> void:
	if stats_row == null:
		return
	for child in stats_row.get_children():
		child.queue_free()
	var stat_defs: Array = [
		{"key": "mind", "label": "心智"},
		{"key": "body", "label": "体魄"},
		{"key": "charm", "label": "魅力"},
		{"key": "faith", "label": "信仰"},
	]
	for stat_def in stat_defs:
		var key: String = stat_def["key"]
		var label_text: String = stat_def["label"]
		var value: int = int(_stats.get(key, 0))
		var lbl := Label.new()
		lbl.text = "%s %d" % [label_text, value]
		lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		lbl.add_theme_font_size_override("font_size", 13)
		lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		stats_row.add_child(lbl)

func show_empty() -> void:
	_npc_id = ""
	_display_name = ""
	name_label.text = "人物"
	role_label.text = ""
	if chat_button != null:
		chat_button.disabled = true
	if _dream_button != null:
		_dream_button.disabled = true
		_dream_button.text = "托梦"
		_dream_button.tooltip_text = ""
	if portrait_image != null:
		portrait_image.texture = null
		portrait_image.visible = false
	if portrait_initial != null:
		portrait_initial.text = "?"
		portrait_initial.modulate = Color(0.6, 0.6, 0.65, 1)
		portrait_initial.visible = true
	bio_text.text = "此刻还没有可查看的居民。"
	_render_identity({})
	state_label.text = ""
	_stats = {}
	_render_stats_row()
	for child in bond_container.get_children():
		child.queue_free()
	karma_label.text = ""

## 渲染"身份"区块：一句话身份标签 + 特质筹码 + 背景钩子。
## 缺字段时按策划规范走占位文案，不破坏布局。
func _render_identity(character: Dictionary) -> void:
	if identity_label != null:
		var identity_tag: String = String(character.get("identity_tag", ""))
		if identity_tag == "":
			identity_tag = String(character.get("role", "身份未知"))
		identity_label.text = identity_tag
	_clear_traits()
	var trait_list: Array = character.get("traits", [])
	if trait_list.is_empty():
		var placeholder := Label.new()
		placeholder.text = "暂无特质"
		placeholder.add_theme_font_size_override("font_size", 12)
		placeholder.add_theme_color_override("font_color", Color(0.55, 0.58, 0.65, 1))
		if traits_row != null:
			traits_row.add_child(placeholder)
	else:
		for t in trait_list:
			_add_trait_chip(String(t))
	if backstory_label != null:
		var backstory: String = String(character.get("backstory_hint", ""))
		if backstory == "":
			backstory_label.text = ""
			backstory_label.visible = false
		else:
			backstory_label.text = "· %s" % backstory
			backstory_label.visible = true

func _clear_traits() -> void:
	if traits_row == null:
		return
	for child in traits_row.get_children():
		child.queue_free()

## 单个特质筹码：圆角小标签，沿用 .tscn 中的 trait_chip 样式。
func _add_trait_chip(trait_text: String) -> void:
	if traits_row == null or trait_text == "":
		return
	var chip := PanelContainer.new()
	var label := Label.new()
	label.text = trait_text
	label.add_theme_font_size_override("font_size", 12)
	label.add_theme_color_override("font_color", Color(1, 0.92, 0.7, 1))
	chip.add_child(label)
	var style := StyleBoxFlat.new()
	style.set_corner_radius_all(10)
	style.content_margin_left = 8
	style.content_margin_right = 8
	style.content_margin_top = 2
	style.content_margin_bottom = 2
	style.set_border_width_all(1)
	style.border_color = Color(0.82, 0.72, 0.48, 0.4)
	style.bg_color = Color(0.18, 0.22, 0.28, 1)
	chip.add_theme_stylebox_override("panel", style)
	traits_row.add_child(chip)

## 惰性创建托梦按钮，插到 ChatButton 之前。
## dream_ctx 缺失时按钮直接置灰（例如角色为空 / MainGameUI 尚未提供上下文）。
func _ensure_dream_button() -> void:
	if _dream_button != null:
		return
	if chat_button == null:
		return
	var parent := chat_button.get_parent()
	if parent == null:
		return
	_dream_button = Button.new()
	_dream_button.name = "DreamButton"
	_dream_button.text = "托梦"
	_dream_button.disabled = true
	_dream_button.pressed.connect(_on_dream_pressed)
	parent.add_child(_dream_button)
	parent.move_child(_dream_button, chat_button.get_index())

func _on_dream_pressed() -> void:
	if _npc_id == "":
		return
	dream_requested.emit(_npc_id, _display_name)

## 根据当前 game_state 与 npc 状态刷新托梦按钮的可用性与提示。
## dream_ctx 期望字段：{time_slot: String, divine_power: int, dream_used_today: bool, dream_cost: int}
func _update_dream_button(dream_ctx: Dictionary) -> void:
	if _dream_button == null:
		return
	if _npc_id == "":
		_dream_button.disabled = true
		_dream_button.text = "托梦"
		_dream_button.tooltip_text = "先选择一位居民"
		return
	if dream_ctx.is_empty():
		_dream_button.disabled = true
		_dream_button.text = "托梦"
		_dream_button.tooltip_text = ""
		return
	var slot: String = String(dream_ctx.get("time_slot", "Morning"))
	var used: bool = bool(dream_ctx.get("dream_used_today", false))
	var power: int = int(dream_ctx.get("divine_power", 0))
	var cost: int = int(dream_ctx.get("dream_cost", 3))
	if slot != "Night":
		_dream_button.disabled = true
		_dream_button.text = "托梦（限夜）"
		_dream_button.tooltip_text = "托梦须在夜晚。"
	elif used:
		_dream_button.disabled = true
		_dream_button.text = "托梦（今日已用）"
		_dream_button.tooltip_text = "今日已托过一梦，明夜再来。"
	elif power < cost:
		_dream_button.disabled = true
		_dream_button.text = "托梦（神力不足）"
		_dream_button.tooltip_text = "托梦需 %d 点神力，当前 %d 点。" % [cost, power]
	else:
		_dream_button.disabled = false
		_dream_button.text = "托梦 · 神力 %d" % cost
		_dream_button.tooltip_text = "在梦中写下最多 100 字，向 TA 递去启示。"
