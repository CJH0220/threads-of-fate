extends Control

signal new_game_requested
signal toast_requested(message: String)
signal settings_requested
signal credits_requested
signal quit_requested

@onready var new_game_button: Button = $Panel/Root/NewGameButton
@onready var quit_button: Button = $Panel/Root/QuitButton
@onready var continue_button: Button = $Panel/Root/ContinueButton
@onready var load_game_button: Button = $Panel/Root/LoadGameButton
@onready var settings_button: Button = $Panel/Root/SettingsButton
@onready var credits_button: Button = $Panel/Root/CreditsButton
@onready var quit_confirm_dialog: ConfirmationDialog = $QuitConfirmDialog

func _ready() -> void:
	new_game_button.pressed.connect(func() -> void: new_game_requested.emit())
	quit_button.pressed.connect(_on_quit_pressed)
	continue_button.pressed.connect(func() -> void: toast_requested.emit("暂无可继续的存档。"))
	load_game_button.pressed.connect(func() -> void: toast_requested.emit("读档功能将在前端竖切后接入。"))
	settings_button.pressed.connect(func() -> void: settings_requested.emit())
	credits_button.pressed.connect(func() -> void: credits_requested.emit())
	quit_confirm_dialog.confirmed.connect(_on_quit_confirmed)
	new_game_button.grab_focus()

func _on_quit_pressed() -> void:
	quit_confirm_dialog.popup_centered()

func _on_quit_confirmed() -> void:
	quit_requested.emit()
