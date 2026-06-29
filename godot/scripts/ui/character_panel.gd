extends VBoxContainer
class_name CharacterPanel

@onready var name_label: Label = $Header/NameLabel
@onready var role_label: Label = $Header/RoleLabel
@onready var bio_text: RichTextLabel = $BioText
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
	name_label.text = "%s｜%s｜%s" % [
		character.get("display_name", "未知居民"),
		character.get("role", "身份未知"),
		character.get("age_range", ""),
	]
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

func show_empty() -> void:
	name_label.text = "人物"
	role_label.text = ""
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
