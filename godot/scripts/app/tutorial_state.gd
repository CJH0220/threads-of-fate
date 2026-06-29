extends Node

## 教程显示状态持久化。记录每条教程是否已看，以及「不再提示」全局偏好。
## 存储 user://tutorial.cfg。供 TutorialOverlay 判断是否自动显示，设置中可重置。

const CONFIG_PATH := "user://tutorial.cfg"
const SECTION_SEEN := "seen"
const SECTION_PREF := "pref"
const KEY_SUPPRESS_ALL := "suppress_all"

var _config := ConfigFile.new()

func _ready() -> void:
	_config.load(CONFIG_PATH)

func should_show(tutorial_id: String) -> bool:
	if bool(_config.get_value(SECTION_PREF, KEY_SUPPRESS_ALL, false)):
		return false
	return not bool(_config.get_value(SECTION_SEEN, tutorial_id, false))

func mark_seen(tutorial_id: String) -> void:
	_config.set_value(SECTION_SEEN, tutorial_id, true)
	_save()

func suppress_all() -> void:
	_config.set_value(SECTION_PREF, KEY_SUPPRESS_ALL, true)
	_save()

func reset_all() -> void:
	_config = ConfigFile.new()
	_save()

func _save() -> void:
	_config.save(CONFIG_PATH)
