extends Control

## 设置界面覆盖层。音频/显示实时预览，应用才落盘；
## 返回时若有未保存更改弹确认还原。操作简介复用 DetailPopup。

signal closed()

const DETAIL_POPUP_SCENE: PackedScene = preload("res://scenes/ui/DetailPopup.tscn")
const CONFIRM_DIALOG_SCENE: PackedScene = preload("res://scenes/ui/ConfirmDialog.tscn")

const _PAGES_ROOT := "Dim/Panel/VBox/Body/ContentScroll/Pages/"

@onready var cat_audio: Button = $Dim/Panel/VBox/Body/CategoryList/AudioCat
@onready var cat_display: Button = $Dim/Panel/VBox/Body/CategoryList/DisplayCat
@onready var cat_text: Button = $Dim/Panel/VBox/Body/CategoryList/TextCat
@onready var cat_controls: Button = $Dim/Panel/VBox/Body/CategoryList/ControlsCat
@onready var cat_accessibility: Button = $Dim/Panel/VBox/Body/CategoryList/AccessibilityCat

@onready var audio_page: Control = get_node(_PAGES_ROOT + "AudioPage")
@onready var display_page: Control = get_node(_PAGES_ROOT + "DisplayPage")
@onready var text_page: Control = get_node(_PAGES_ROOT + "TextPage")
@onready var controls_page: Control = get_node(_PAGES_ROOT + "ControlsPage")
@onready var accessibility_page: Control = get_node(_PAGES_ROOT + "AccessibilityPage")

@onready var master_slider: HSlider = get_node(_PAGES_ROOT + "AudioPage/MasterRow/MasterSlider")
@onready var music_slider: HSlider = get_node(_PAGES_ROOT + "AudioPage/MusicRow/MusicSlider")
@onready var sfx_slider: HSlider = get_node(_PAGES_ROOT + "AudioPage/SfxRow/SfxSlider")
@onready var ambience_slider: HSlider = get_node(_PAGES_ROOT + "AudioPage/AmbienceRow/AmbienceSlider")

@onready var window_mode_option: OptionButton = get_node(_PAGES_ROOT + "DisplayPage/WindowModeRow/WindowModeOption")
@onready var resolution_option: OptionButton = get_node(_PAGES_ROOT + "DisplayPage/ResolutionRow/ResolutionOption")
@onready var pixel_scale_option: OptionButton = get_node(_PAGES_ROOT + "DisplayPage/PixelScaleRow/PixelScaleOption")
@onready var screen_shake_check: CheckButton = get_node(_PAGES_ROOT + "DisplayPage/ScreenShakeRow/ScreenShakeCheck")

@onready var typing_speed_slider: HSlider = get_node(_PAGES_ROOT + "TextPage/TypingSpeedRow/TypingSpeedSlider")
@onready var auto_speed_slider: HSlider = get_node(_PAGES_ROOT + "TextPage/AutoSpeedRow/AutoSpeedSlider")
@onready var skip_read_check: CheckButton = get_node(_PAGES_ROOT + "TextPage/SkipReadRow/SkipReadCheck")
@onready var event_font_size_option: OptionButton = get_node(_PAGES_ROOT + "TextPage/EventFontSizeRow/EventFontSizeOption")

@onready var key_hints_check: CheckButton = get_node(_PAGES_ROOT + "ControlsPage/KeyHintsRow/KeyHintsCheck")
@onready var mouse_hover_check: CheckButton = get_node(_PAGES_ROOT + "ControlsPage/MouseHoverRow/MouseHoverCheck")
@onready var operation_guide_button: Button = get_node(_PAGES_ROOT + "ControlsPage/OperationGuideRow/OperationGuideButton")

@onready var font_size_option: OptionButton = get_node(_PAGES_ROOT + "AccessibilityPage/FontSizeRow/FontSizeOption")
@onready var reduce_motion_check: CheckButton = get_node(_PAGES_ROOT + "AccessibilityPage/ReduceMotionRow/ReduceMotionCheck")
@onready var high_contrast_check: CheckButton = get_node(_PAGES_ROOT + "AccessibilityPage/HighContrastRow/HighContrastCheck")
@onready var color_assist_check: CheckButton = get_node(_PAGES_ROOT + "AccessibilityPage/ColorAssistRow/ColorAssistCheck")
@onready var strong_confirm_check: CheckButton = get_node(_PAGES_ROOT + "AccessibilityPage/StrongConfirmRow/StrongConfirmCheck")

@onready var close_button: Button = $Dim/Panel/VBox/Header/CloseButton
@onready var reset_button: Button = $Dim/Panel/VBox/Footer/ResetButton
@onready var apply_button: Button = $Dim/Panel/VBox/Footer/ApplyButton
@onready var back_button: Button = $Dim/Panel/VBox/Footer/BackButton

var _pages: Array[Control] = []
var _cat_buttons: Array[Button] = []
var _operation_popup: DetailPopup
var _confirm: ConfirmDialog
var _loading := false
var _dirty := false
var _pending_confirm := ""

func _ready() -> void:
	visible = false
	_pages = [audio_page, display_page, text_page, controls_page, accessibility_page]
	_cat_buttons = [cat_audio, cat_display, cat_text, cat_controls, cat_accessibility]

	_build_option_items()

	_operation_popup = DETAIL_POPUP_SCENE.instantiate()
	add_child(_operation_popup)
	_operation_popup.visible = false

	_confirm = CONFIRM_DIALOG_SCENE.instantiate()
	add_child(_confirm)
	_confirm.dialog_confirmed.connect(_on_confirm_confirmed)

	_connect_signals()
	_select_category(0)

func open() -> void:
	_loading = true
	_populate_controls()
	_loading = false
	_dirty = false
	visible = true
	_select_category(0)
	cat_audio.grab_focus()

func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return
	if event.is_action_pressed("ui_cancel"):
		_on_back()
		get_viewport().set_input_as_handled()

func _build_option_items() -> void:
	_set_items(window_mode_option, ["窗口化", "全屏", "无边框"])
	var res_labels: Array[String] = []
	for r: Vector2i in Settings.RESOLUTIONS:
		res_labels.append("%d × %d" % [r.x, r.y])
	_set_items(resolution_option, res_labels)
	_set_items(pixel_scale_option, ["自动", "1x", "2x", "3x"])
	_set_items(event_font_size_option, ["小", "标准", "大"])
	_set_items(font_size_option, ["小", "标准", "大"])

func _set_items(option: OptionButton, items: Array) -> void:
	option.clear()
	for item: String in items:
		option.add_item(item)

func _connect_signals() -> void:
	cat_audio.pressed.connect(func() -> void: _select_category(0))
	cat_display.pressed.connect(func() -> void: _select_category(1))
	cat_text.pressed.connect(func() -> void: _select_category(2))
	cat_controls.pressed.connect(func() -> void: _select_category(3))
	cat_accessibility.pressed.connect(func() -> void: _select_category(4))

	close_button.pressed.connect(_on_back)
	back_button.pressed.connect(_on_back)
	apply_button.pressed.connect(_on_apply)
	reset_button.pressed.connect(_on_reset)
	operation_guide_button.pressed.connect(_show_operation_guide)

	master_slider.value_changed.connect(func(v: float) -> void: _on_audio_changed("master", v))
	music_slider.value_changed.connect(func(v: float) -> void: _on_audio_changed("music", v))
	sfx_slider.value_changed.connect(func(v: float) -> void: _on_audio_changed("sfx", v))
	ambience_slider.value_changed.connect(func(v: float) -> void: _on_audio_changed("ambience", v))

	window_mode_option.item_selected.connect(func(i: int) -> void: _on_display_changed("window_mode", i))
	resolution_option.item_selected.connect(func(i: int) -> void: _on_display_changed("resolution", i))
	pixel_scale_option.item_selected.connect(func(i: int) -> void: _on_display_changed("pixel_scale", i))
	screen_shake_check.toggled.connect(func(p: bool) -> void: _on_display_changed("screen_shake", p))

	typing_speed_slider.value_changed.connect(func(v: float) -> void: _on_store_changed("text", "typing_speed", int(v)))
	auto_speed_slider.value_changed.connect(func(v: float) -> void: _on_store_changed("text", "auto_speed", int(v)))
	skip_read_check.toggled.connect(func(p: bool) -> void: _on_store_changed("text", "skip_read", p))
	event_font_size_option.item_selected.connect(func(i: int) -> void: _on_store_changed("text", "event_font_size", i))

	key_hints_check.toggled.connect(func(p: bool) -> void: _on_store_changed("controls", "key_hints", p))
	mouse_hover_check.toggled.connect(func(p: bool) -> void: _on_store_changed("controls", "mouse_hover_desc", p))

	font_size_option.item_selected.connect(func(i: int) -> void: _on_store_changed("accessibility", "font_size", i))
	reduce_motion_check.toggled.connect(func(p: bool) -> void: _on_store_changed("accessibility", "reduce_motion", p))
	high_contrast_check.toggled.connect(func(p: bool) -> void: _on_store_changed("accessibility", "high_contrast", p))
	color_assist_check.toggled.connect(func(p: bool) -> void: _on_store_changed("accessibility", "color_assist", p))
	strong_confirm_check.toggled.connect(func(p: bool) -> void: _on_store_changed("accessibility", "strong_confirm", p))

func _populate_controls() -> void:
	master_slider.value = float(Settings.get_value("audio", "master"))
	music_slider.value = float(Settings.get_value("audio", "music"))
	sfx_slider.value = float(Settings.get_value("audio", "sfx"))
	ambience_slider.value = float(Settings.get_value("audio", "ambience"))

	window_mode_option.select(int(Settings.get_value("display", "window_mode")))
	resolution_option.select(int(Settings.get_value("display", "resolution")))
	pixel_scale_option.select(int(Settings.get_value("display", "pixel_scale")))
	screen_shake_check.button_pressed = bool(Settings.get_value("display", "screen_shake"))

	typing_speed_slider.value = int(Settings.get_value("text", "typing_speed"))
	auto_speed_slider.value = int(Settings.get_value("text", "auto_speed"))
	skip_read_check.button_pressed = bool(Settings.get_value("text", "skip_read"))
	event_font_size_option.select(int(Settings.get_value("text", "event_font_size")))

	key_hints_check.button_pressed = bool(Settings.get_value("controls", "key_hints"))
	mouse_hover_check.button_pressed = bool(Settings.get_value("controls", "mouse_hover_desc"))

	font_size_option.select(int(Settings.get_value("accessibility", "font_size")))
	reduce_motion_check.button_pressed = bool(Settings.get_value("accessibility", "reduce_motion"))
	high_contrast_check.button_pressed = bool(Settings.get_value("accessibility", "high_contrast"))
	color_assist_check.button_pressed = bool(Settings.get_value("accessibility", "color_assist"))
	strong_confirm_check.button_pressed = bool(Settings.get_value("accessibility", "strong_confirm"))

func _select_category(idx: int) -> void:
	for i in _pages.size():
		_pages[i].visible = (i == idx)
		_cat_buttons[i].button_pressed = (i == idx)

func _on_audio_changed(key: String, value: float) -> void:
	if _loading:
		return
	Settings.set_value("audio", key, value)
	_dirty = true

func _on_display_changed(key: String, value: Variant) -> void:
	if _loading:
		return
	Settings.set_value("display", key, value)
	_dirty = true

func _on_store_changed(section: String, key: String, value: Variant) -> void:
	if _loading:
		return
	Settings.set_value(section, key, value)
	_dirty = true

func _on_apply() -> void:
	Settings.save_settings()
	_dirty = false

func _on_reset() -> void:
	_pending_confirm = "reset"
	_confirm.show_confirm("恢复默认设置", "确定将所有设置恢复为默认值吗？", "恢复", "取消")

func _on_back() -> void:
	if _dirty:
		_pending_confirm = "back"
		_confirm.show_confirm("放弃未保存更改", "尚有未保存的更改，确定放弃并返回吗？", "放弃", "取消")
	else:
		_close()

func _on_confirm_confirmed() -> void:
	match _pending_confirm:
		"back":
			Settings.load_settings()
			Settings.apply_all()
			_close()
		"reset":
			Settings.reset_to_defaults()
			_loading = true
			_populate_controls()
			_loading = false
			_dirty = true
	_pending_confirm = ""

func _close() -> void:
	visible = false
	closed.emit()

func _show_operation_guide() -> void:
	_operation_popup.show_popup("操作简介（键盘 / 鼠标）")
	var rows: Array = [
		["选择地点 / 人物 / 事件", "鼠标左键单击", "点击地图地点或底部列表条目，打开详情"],
		["确认按钮 / 选择干预", "鼠标左键单击", "点击按钮、选择一项干预"],
		["移动地图", "鼠标左键拖拽", "在地图区域拖拽平移"],
		["滚动地图 / 列表", "鼠标滚轮", "滚动地图或长列表"],
		["打开 / 关闭暂停菜单", "Esc", "游戏内开关暂停菜单"],
		["关闭弹窗", "Esc / 点击弹窗外", "关闭详情、确认等弹窗"],
		["UI 焦点切换", "Tab / 方向键", "在可聚焦控件间移动（键盘导航）"],
		["触发聚焦控件", "Enter / 空格", "激活当前聚焦的按钮"],
	]
	for row: Array in rows:
		_operation_popup.add_label("%s\n  输入：%s\n  %s" % [row[0], row[1], row[2]])
		_operation_popup.add_separator()
