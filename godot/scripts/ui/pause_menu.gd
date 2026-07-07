extends Control
class_name PauseMenu

signal save_requested()
signal load_requested()
signal settings_requested()
signal event_history_requested()
signal return_to_menu_requested()
signal quit_requested()

@onready var resume_button: Button = $Dim/Panel/ButtonList/ResumeButton
@onready var save_button: Button = $Dim/Panel/ButtonList/SaveButton
@onready var load_button: Button = $Dim/Panel/ButtonList/LoadButton
@onready var settings_button: Button = $Dim/Panel/ButtonList/SettingsButton
@onready var event_history_button: Button = $Dim/Panel/ButtonList/EventHistoryButton
@onready var main_menu_button: Button = $Dim/Panel/ButtonList/MainMenuButton
@onready var quit_button: Button = $Dim/Panel/ButtonList/QuitButton
@onready var confirm_dialog: ConfirmationDialog = $ConfirmDialog

var _pending_action := ""

func _ready() -> void:
	visible = false
	resume_button.pressed.connect(close)
	save_button.pressed.connect(func() -> void: save_requested.emit())
	load_button.pressed.connect(func() -> void: load_requested.emit())
	settings_button.pressed.connect(func() -> void: settings_requested.emit())
	event_history_button.pressed.connect(func() -> void: event_history_requested.emit())
	main_menu_button.pressed.connect(_on_main_menu_pressed)
	quit_button.pressed.connect(_on_quit_pressed)
	confirm_dialog.confirmed.connect(_on_confirmed)

func open() -> void:
	visible = true
	resume_button.grab_focus()

func close() -> void:
	visible = false

func _on_main_menu_pressed() -> void:
	_pending_action = "menu"
	confirm_dialog.title = "返回主菜单"
	confirm_dialog.dialog_text = "返回主菜单将丢失未保存的进度，确定吗？"
	confirm_dialog.popup_centered()

func _on_quit_pressed() -> void:
	_pending_action = "quit"
	confirm_dialog.title = "退出游戏"
	confirm_dialog.dialog_text = "确定要离开归潮镇吗？"
	confirm_dialog.popup_centered()

func _on_confirmed() -> void:
	match _pending_action:
		"menu":
			visible = false
			return_to_menu_requested.emit()
		"quit":
			quit_requested.emit()
	_pending_action = ""
