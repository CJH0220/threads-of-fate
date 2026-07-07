extends Control

## 结局画廊覆盖层。展示已解锁/未解锁的最终结局。

signal closed()

const ENTRIES := [
    {"ending_id": "game_over_incense_out", "title": "香火熄灭", "type": "Failure", "hint": "香火是神位的根基。"},
    {"ending_id": "neutral_god", "title": "旧庙余香", "type": "Neutral", "hint": "既非善也非恶，只是走过。"},
    {"ending_id": "righteous_god", "title": "天界善神", "type": "Righteous", "hint": "阳德积累到一定程度，命运会偏向光明。"},
    {"ending_id": "evil_god", "title": "地府邪神", "type": "Evil", "hint": "阴德的道路也有它的尽头。"},
    {"ending_id": "legend_guardian", "title": "归潮传说", "type": "Legend", "hint": "需要极高的香火与阳德才能触达的传说。"},
]

const STYLE_COLORS := {
    "Righteous": Color(0.86, 0.70, 0.30),
    "Evil": Color(0.38, 0.12, 0.20),
    "Neutral": Color(0.44, 0.41, 0.37),
    "Legend": Color(0.55, 0.40, 0.72),
    "Failure": Color(0.20, 0.20, 0.23),
}

@onready var entry_list: VBoxContainer = $Dim/Panel/VBox/Scroll/EntryList
@onready var detail_panel: Control = $Dim/Panel/VBox/DetailPanel
@onready var detail_title: Label = $Dim/Panel/VBox/DetailPanel/DetailTitle
@onready var detail_illustration: ColorRect = $Dim/Panel/VBox/DetailPanel/DetailIllustration
@onready var detail_text: RichTextLabel = $Dim/Panel/VBox/DetailPanel/DetailText
@onready var close_button: Button = $Dim/Panel/VBox/Header/CloseButton

func _ready() -> void:
	visible = false
	close_button.pressed.connect(close)
	detail_panel.visible = false

func open() -> void:
	_rebuild_list()
	visible = true
	close_button.grab_focus()

func close() -> void:
	visible = false
	closed.emit()

func _rebuild_list() -> void:
	_clear_list()
	for entry in ENTRIES:
		var item := _create_entry_item(entry)
		entry_list.add_child(item)

func _clear_list() -> void:
	for child in entry_list.get_children():
		child.queue_free()

func _create_entry_item(entry: Dictionary) -> Control:
	var id: String = String(entry.get("ending_id", ""))
	var unlocked := Settings.is_ending_unlocked(id)
	var is_new := Settings.is_ending_new(id)
	var ending_type := String(entry.get("type", "Neutral"))
	var tint: Color = STYLE_COLORS.get(ending_type, STYLE_COLORS["Neutral"])

	var btn := Button.new()
	btn.custom_minimum_size = Vector2(0, 56)
	btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	btn.alignment = HORIZONTAL_ALIGNMENT_LEFT

	var hbox := HBoxContainer.new()
	hbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	btn.add_child(hbox)

	var thumb := ColorRect.new()
	thumb.custom_minimum_size = Vector2(48, 48)
	thumb.color = tint.darkened(0.35) if unlocked else Color(0.15, 0.15, 0.17)
	hbox.add_child(thumb)

	var vbox := VBoxContainer.new()
	vbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(vbox)

	var title := Label.new()
	title.add_theme_font_size_override("font_size", 16)
	if unlocked:
		title.text = String(entry.get("title", "???"))
		title.add_theme_color_override("font_color", tint.lightened(0.2))
	else:
		title.text = "?????"
		title.add_theme_color_override("font_color", Color(0.4, 0.4, 0.45))
	vbox.add_child(title)

	var hint := Label.new()
	hint.add_theme_font_size_override("font_size", 13)
	hint.add_theme_color_override("font_color", Color(0.5, 0.55, 0.6))
	if unlocked:
		hint.text = String(entry.get("hint", ""))
	else:
		hint.text = "这条命运仍未显现。"
	vbox.add_child(hint)

	if is_new:
		var badge := Label.new()
		badge.add_theme_font_size_override("font_size", 12)
		badge.add_theme_color_override("font_color", Color(1, 0.86, 0.4))
		badge.text = " 新"
		hbox.add_child(badge)

	btn.pressed.connect(func() -> void: _show_detail(entry, unlocked, tint))
	return btn

func _show_detail(entry: Dictionary, unlocked: bool, tint: Color) -> void:
	detail_panel.visible = true
	if unlocked:
		detail_title.text = String(entry.get("title", ""))
		detail_title.add_theme_color_override("font_color", tint.lightened(0.2))
		detail_illustration.color = tint.darkened(0.35)
		var ending_id: String = String(entry.get("ending_id", ""))
		detail_text.text = _ending_text_for(ending_id)
	else:
		detail_title.text = "?????"
		detail_title.add_theme_color_override("font_color", Color(0.4, 0.4, 0.45))
		detail_illustration.color = Color(0.12, 0.12, 0.14)
		detail_text.text = "这条命运仍未显现。\n" + String(entry.get("hint", ""))

func _ending_text_for(ending_id: String) -> String:
	match ending_id:
		"game_over_incense_out":
			return "土地庙前最后一缕香火散去。\n归潮镇不再记得你的名字，潮水照旧涨落，只是再没有人来上香。"
		"neutral_god":
			return "土地公勉强通过了考核。\n归潮镇的日子照常继续，许多问题仍没有答案，潮水来了又去。"
		"righteous_god":
			return "归潮镇的人们仍会在清晨点燃第一炷香。\n他们不知道是谁改变了命运，但他们记得风从海边吹来时的安宁。"
		"evil_god":
			return "小镇依旧供奉着你，香火比从前更旺，只是人们低头上香时，眼里多了一分畏惧。"
		"legend_guardian":
			return "灾后的小镇重新升起炊烟。\n人们说不清是谁守住了这片海岸，却仍有人在清晨低声念起岛爷的名字。"
		_:
			return ""

func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		close()
		get_viewport().set_input_as_handled()
