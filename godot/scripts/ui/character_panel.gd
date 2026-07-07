extends VBoxContainer
class_name CharacterPanel

signal chat_requested(npc_id: String, display_name: String)

@onready var name_label: Label = $Header/HeaderText/NameLabel
@onready var role_label: Label = $Header/HeaderText/RoleLabel
@onready var chat_button: Button = $Header/ChatButton
@onready var portrait_panel: PanelContainer = $Header/Portrait
@onready var portrait_image: TextureRect = $Header/Portrait/PortraitImage
@onready var portrait_initial: Label = $Header/Portrait/PortraitInitial
@onready var bio_text: RichTextLabel = $BioText

var _npc_id: String = ""
var _display_name: String = ""

func _ready() -> void:
	if chat_button != null:
		chat_button.pressed.connect(_on_chat_pressed)

func _on_chat_pressed() -> void:
	if _npc_id == "":
		return
	chat_requested.emit(_npc_id, _display_name)
@onready var morning_location_label: Label = $ScheduleSection/MorningRow/MorningLocationLabel
@onready var afternoon_location_label: Label = $ScheduleSection/AfternoonRow/AfternoonLocationLabel
@onready var night_location_label: Label = $ScheduleSection/NightRow/NightLocationLabel
@onready var state_label: Label = $StatsSection/StateLabel
@onready var mind_label: Label = $StatsSection/StatsRow/MindLabel
@onready var body_label: Label = $StatsSection/StatsRow/BodyLabel
@onready var charm_label: Label = $StatsSection/StatsRow/CharmLabel
@onready var faith_label: Label = $StatsSection/StatsRow/FaithLabel
@onready var bond_container: VBoxContainer = $BondSection/BondContainer
@onready var karma_label: Label = $KarmaSection/KarmaLabel

func show_character(character: Dictionary, location_label_provider: Callable) -> void:
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
	bio_text.text = character.get("description", "暂无简介。")

	var schedule: Dictionary = character.get("schedule", {})
	morning_location_label.text = location_label_provider.call(schedule.get("Morning", ""))
	afternoon_location_label.text = location_label_provider.call(schedule.get("Afternoon", ""))
	night_location_label.text = location_label_provider.call(schedule.get("Night", ""))

	state_label.text = character.get("current_state", "暂无状态。")

	var stats: Dictionary = character.get("stats", {})
	mind_label.text = "心智 %d" % stats.get("mind", 0)
	body_label.text = "体魄 %d" % stats.get("body", 0)
	charm_label.text = "魅力 %d" % stats.get("charm", 0)
	faith_label.text = "信仰 %d" % stats.get("faith", 0)

	for child in bond_container.get_children():
		child.queue_free()
	var bonds: Array = character.get("bond_summaries", [])
	if bonds.is_empty():
		var empty_label := Label.new()
		empty_label.text = "暂无明确关系。"
		bond_container.add_child(empty_label)
	else:
		for bond in bonds:
			var bond_label := Label.new()
			bond_label.text = "%s｜%s Lv.%d｜强度 %d" % [
				bond.get("target_display_name", "未知居民"),
				bond.get("bond_type", "陌生"),
				bond.get("level", 0),
				bond.get("strength", 0),
			]
			bond_container.add_child(bond_label)

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

func show_empty() -> void:
	_npc_id = ""
	_display_name = ""
	name_label.text = "人物"
	role_label.text = ""
	if chat_button != null:
		chat_button.disabled = true
	if portrait_image != null:
		portrait_image.texture = null
		portrait_image.visible = false
	if portrait_initial != null:
		portrait_initial.text = "?"
		portrait_initial.modulate = Color(0.6, 0.6, 0.65, 1)
		portrait_initial.visible = true
	bio_text.text = "此刻还没有可查看的居民。"
	morning_location_label.text = "—"
	afternoon_location_label.text = "—"
	night_location_label.text = "—"
	state_label.text = ""
	mind_label.text = ""
	body_label.text = ""
	charm_label.text = ""
	faith_label.text = ""
	for child in bond_container.get_children():
		child.queue_free()
	karma_label.text = ""
