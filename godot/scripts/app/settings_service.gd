extends Node

## 全局设置服务（Godot Autoload，全局访问名 Settings）。
## 持久化存储：ConfigFile -> user://settings.cfg
## 5 大分类：音频 / 显示 / 文本 / 操作 / 辅助功能
## 实时生效类：音频（音量调节立即生效）、显示（窗口模式/分辨率/缩放立即应用）
## 标记生效类：文本、操作、辅助功能仅存储，由对应系统自行读取
## 附加功能：结局画廊持久化存储（unlocked_endings / new_unlocks，同 ConfigFile 写入）

signal settings_changed()

## 配置文件存储路径
const CONFIG_PATH := "user://settings.cfg"

## 窗口分辨率选项
const RESOLUTIONS: Array[Vector2i] = [
	Vector2i(1280, 720),
	Vector2i(1600, 900),
	Vector2i(1920, 1080),
]

const DEFAULTS := {
	"audio": {
		"master": 0.8,
		"music": 0.7,
		"sfx": 0.8,
		"ambience": 0.6,
	},
	"display": {
		"window_mode": 0,    # 0 窗口化 / 1 全屏 / 2 无边框
		"resolution": 0,     # RESOLUTIONS 索引
		"pixel_scale": 0,    # 0 自动 / 1 / 2 / 3
		"screen_shake": true,
	},
	"text": {
		"typing_speed": 1,   # 0 慢 / 1 中 / 2 快
		"auto_speed": 1,
		"skip_read": false,
		"event_font_size": 1,  # 0 小 / 1 标准 / 2 大
	},
	"controls": {
		"key_hints": true,
		"mouse_hover_desc": true,
	},
	"accessibility": {
		"font_size": 1,      # 0 小 / 1 标准 / 2 大
		"reduce_motion": false,
		"high_contrast": false,
		"color_assist": true,
		"strong_confirm": true,
	},
}

var _values: Dictionary = {}

func _ready() -> void:
	load_settings()
	apply_all()

func load_settings() -> void:
	_values = DEFAULTS.duplicate(true)
	var config := ConfigFile.new()
	if config.load(CONFIG_PATH) != OK:
		return
	for section in _values.keys():
		for key in (_values[section] as Dictionary).keys():
			if config.has_section_key(section, key):
				_values[section][key] = config.get_value(section, key)

func save_settings() -> void:
	var config := ConfigFile.new()
	for section in _values.keys():
		for key in (_values[section] as Dictionary).keys():
			config.set_value(section, key, _values[section][key])
	config.save(CONFIG_PATH)
	settings_changed.emit()

func reset_to_defaults() -> void:
	_values = DEFAULTS.duplicate(true)
	apply_all()
	settings_changed.emit()

func get_value(section: String, key: String) -> Variant:
	if _values.has(section) and (_values[section] as Dictionary).has(key):
		return _values[section][key]
	if DEFAULTS.has(section) and (DEFAULTS[section] as Dictionary).has(key):
		return DEFAULTS[section][key]
	return null

func set_value(section: String, key: String, value: Variant) -> void:
	if not _values.has(section):
		return
	_values[section][key] = value
	match section:
		"audio":
			_apply_audio()
		"display":
			_apply_display()
	settings_changed.emit()

func apply_all() -> void:
	_apply_audio()
	_apply_display()

func _apply_audio() -> void:
	var audio: Dictionary = _values.get("audio", {})
	_apply_bus("Master", float(audio.get("master", 0.8)))
	_apply_bus("Music", float(audio.get("music", 0.7)))
	_apply_bus("SFX", float(audio.get("sfx", 0.8)))
	_apply_bus("Ambience", float(audio.get("ambience", 0.6)))

func _apply_bus(bus_name: String, linear: float) -> void:
	var idx := AudioServer.get_bus_index(bus_name)
	if idx < 0:
		return
	if linear <= 0.0:
		AudioServer.set_bus_mute(idx, true)
	else:
		AudioServer.set_bus_mute(idx, false)
		AudioServer.set_bus_volume_db(idx, linear_to_db(linear))

func _apply_display() -> void:
	var display: Dictionary = _values.get("display", {})
	var window := get_window()
	if window == null:
		return
	var mode: int = int(display.get("window_mode", 0))
	if mode == 1:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_FULLSCREEN)
	else:
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED)
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, mode == 2)
		if mode == 0:
			var res_idx: int = int(display.get("resolution", 0))
			if res_idx >= 0 and res_idx < RESOLUTIONS.size():
				DisplayServer.window_set_size(RESOLUTIONS[res_idx])
	var scale_opt: int = int(display.get("pixel_scale", 0))
	window.content_scale_factor = 1.0 if scale_opt == 0 else float(scale_opt)

## Gallery helpers (stored in the same ConfigFile, outside DEFAULTS).
func get_gallery_array(key: String) -> Array:
	var config := ConfigFile.new()
	if config.load(CONFIG_PATH) != OK:
		return []
	return Array(config.get_value("gallery", key, []))

func set_gallery_array(key: String, value: Array) -> void:
	var config := ConfigFile.new()
	config.load(CONFIG_PATH)
	config.set_value("gallery", key, value)
	config.save(CONFIG_PATH)

func unlock_ending(ending_id: String) -> void:
	var unlocked: Array = get_gallery_array("unlocked_endings")
	if not unlocked.has(ending_id):
		unlocked.append(ending_id)
		set_gallery_array("unlocked_endings", unlocked)
	var new_unlocks: Array = get_gallery_array("new_unlocks")
	if not new_unlocks.has(ending_id):
		new_unlocks.append(ending_id)
		set_gallery_array("new_unlocks", new_unlocks)

func is_ending_unlocked(ending_id: String) -> bool:
	return ending_id in get_gallery_array("unlocked_endings")

func is_ending_new(ending_id: String) -> bool:
	return ending_id in get_gallery_array("new_unlocks")

func clear_new_unlocks() -> void:
	set_gallery_array("new_unlocks", [])
