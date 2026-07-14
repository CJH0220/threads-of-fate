extends Control

## 「命运的织线」Godot 前端主场景入口。
## 职责：屏幕切换（主菜单/HUD）、全局覆盖层路由、状态转换控制、信号中转。
## 覆盖层采用 Main 根节点下常驻实例模式，切换屏幕时仅替换 ScreenRoot 子节点。
## 流程：MainMenu → 新游戏 → reset_to_new_game → MainGameUI(HUD) → Intro VN → 教程 → 主循环

## 主菜单场景预制件
const MAIN_MENU_SCENE: PackedScene = preload("res://scenes/ui/MainMenu.tscn")
## HUD 主界面场景预制件
const HUD_SCENE: PackedScene = preload("res://scenes/ui/MainGameUI.tscn")

## 新游戏开场 VN 数据（世界观简介）。复用 DialogueEventScreen 机制，不新建场景。
const INTRO_DATA := {
	"event_id": "intro_prologue",
	"event_name": "序章：归潮",
	"location_id": "temple",
	"location_label": "土地庙",
	"dialogue_segments": [
		{"speaker_id": "", "speaker_name": "", "line_type": "narration", "position": "center", "text": "归潮镇，一座靠海的小镇。潮水每天涨落，镇上的日子看似平静。"},
		{"speaker_id": "", "speaker_name": "", "line_type": "narration", "position": "center", "text": "你是这片土地的土地公，守护着归潮镇与它的居民。"},
		{"speaker_id": "", "speaker_name": "", "line_type": "narration", "position": "center", "text": "「天界监察司」土地公，天庭命你执掌命运织线器。六十日为限，香火不绝，神位可保。"},
		{"speaker_id": "", "speaker_name": "", "line_type": "narration", "position": "center", "text": "你能观察居民的命运，也能用神力轻轻推一把。但命运有自己的韧性……"},
		{"speaker_id": "", "speaker_name": "", "line_type": "narration", "position": "center", "text": "六十天后，潮水将带来一场大灾。你能守住这座小镇吗？"},
	],
}

## 屏幕替换根节点（主菜单/HUD 在此切换）
@onready var screen_root: MarginContainer = $ScreenRoot
## 全局吐司提示容器
@onready var toast_panel: PanelContainer = $ToastPanel
## 吐司提示文本
@onready var toast_label: Label = $ToastPanel/ToastLabel
## 时间/干预结算面板
@onready var settlement_panel: SettlementPanel = $SettlementPanel
## 全局通用确认对话框
@onready var confirm_dialog: ConfirmDialog = $ConfirmDialog
## 暂停菜单（Esc 呼出）
@onready var pause_menu: PauseMenu = $PauseMenu
## 设置界面覆盖层
@onready var settings_screen: Control = $SettingsScreen
## 关于我们覆盖层
@onready var credits_screen: Control = $CreditsScreen
## 60天总评覆盖层（正常局终）
@onready var final_summary_screen: Control = $FinalSummaryScreen
## 最终结局覆盖层（从总评进入）
@onready var ending_screen: Control = $EndingScreen
## 失败结局覆盖层（Game Over）
@onready var game_over_screen: Control = $GameOverScreen
## 周结算覆盖层（每7天夜后推进触发）
@onready var week_summary_screen: Control = $WeekSummaryScreen
## 首次系统教程提示覆盖层
@onready var tutorial_overlay: Control = $TutorialOverlay
## 事件历史回顾覆盖层
@onready var event_history_screen: Control = $EventHistoryScreen
## 结局画廊/成就覆盖层
@onready var ending_gallery_screen: Control = $EndingGalleryScreen

## 当前游戏状态实例类型。
## true = 使用真实后端（BackendGameState），false = 使用本地 Mock（MockGameState）
const USE_BACKEND := true

## 当前游戏状态实例（基类，兼容 MockGameState 与 BackendGameState）
var game_state
## 当前屏幕（主菜单或 HUD）
var current_screen: Control
## 是否处于游戏中（HUD 活跃时为 true，控制 Esc 暂停菜单是否可呼出）
var in_game := true

func _ready() -> void:
	# 连接暂停菜单信号
	pause_menu.settings_requested.connect(_on_settings_requested)
	pause_menu.load_requested.connect(_on_load_requested)
	pause_menu.return_to_menu_requested.connect(show_main_menu)
	pause_menu.quit_requested.connect(_on_quit_requested)
	pause_menu.event_history_requested.connect(_on_event_history_requested)
	# 连接设置/关于我们信号
	settings_screen.closed.connect(_on_settings_closed)
	credits_screen.closed.connect(_on_credits_closed)
	# 连接结局流程信号
	final_summary_screen.view_ending_requested.connect(_on_view_ending_requested)
	final_summary_screen.review_requested.connect(_on_ending_review_requested)
	final_summary_screen.return_to_menu_requested.connect(_on_ending_return_to_menu)
	ending_screen.restart_requested.connect(_on_restart_requested)
	ending_screen.return_to_menu_requested.connect(_on_ending_return_to_menu)
	ending_screen.review_requested.connect(_on_ending_review_requested)
	game_over_screen.load_requested.connect(_on_load_requested)
	game_over_screen.restart_requested.connect(_on_restart_requested)
	game_over_screen.review_requested.connect(_on_ending_review_requested)
	game_over_screen.return_to_menu_requested.connect(_on_ending_return_to_menu)
	# 连接周结算信号
	week_summary_screen.continue_requested.connect(_on_week_continue)
	# 连接事件历史信号
	event_history_screen.closed.connect(_on_event_history_closed)
	# 连接结局画廊信号
	ending_gallery_screen.closed.connect(_on_gallery_closed)

	if USE_BACKEND:
		## 真实后端：先检查健康，失败自动降级到 Mock
		Backend.health_completed.connect(_on_backend_health, CONNECT_ONE_SHOT)
		Backend.check_health()
	else:
		## 本地 Mock
		game_state = MockGameState.new()
		_connect_game_state()

## 后端健康检查响应：根据结果创建对应 state 实例
func _on_backend_health(healthy: bool) -> void:
	if healthy:
		## 通过字符串类名动态创建，避免静态解析依赖
		var backend_class: Script = load("res://scripts/adapters/backend_game_state.gd")
		game_state = backend_class.new()
		## 自动连接 WS
		Backend.connect_ws()
	else:
		game_state = MockGameState.new()
	_connect_game_state()

## 连接 game_state 的 state_changed 信号（用于 UI 刷新）
func _connect_game_state() -> void:
	if game_state.has_signal("state_changed"):
		game_state.state_changed.connect(_on_game_state_changed)
	## 启动时显示主菜单
	show_main_menu()

func _on_game_state_changed() -> void:
	## 状态变化时 HUD 会自动重新绑定，此处预留扩展点
	pass

## Esc 键全局处理：游戏中且无模态覆盖层时呼出/关闭暂停菜单
func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and in_game and not settlement_panel.visible and not settings_screen.visible and not week_summary_screen.visible and not tutorial_overlay.visible and not _ending_flow_active():
		if pause_menu.visible:
			pause_menu.close()
		else:
			pause_menu.open()
		get_viewport().set_input_as_handled()

## 结局流程是否激活中（总评/结局/失败任意一个可见），用于屏蔽 Esc 暂停
func _ending_flow_active() -> bool:
	return final_summary_screen.visible or ending_screen.visible or game_over_screen.visible

## 切换到主菜单屏幕：关闭暂停菜单、重置 in_game、连接菜单信号
func show_main_menu() -> void:
	in_game = false
	pause_menu.close()
	var menu := MAIN_MENU_SCENE.instantiate()
	_set_screen(menu)
	menu.new_game_requested.connect(_on_new_game_requested)
	menu.toast_requested.connect(show_toast)
	menu.settings_requested.connect(_on_settings_requested)
	menu.credits_requested.connect(_on_credits_requested)
	menu.quit_requested.connect(_on_quit_requested)

## 切换到 HUD 屏幕：绑定 game_state、连接 HUD 各信号（Toast/返回菜单/结算/局终/周结算）
func show_hud() -> void:
	in_game = true
	var hud := HUD_SCENE.instantiate()
	_set_screen(hud)
	hud.bind_state(game_state)
	hud.toast_requested.connect(show_toast)
	hud.return_to_menu_requested.connect(show_main_menu)
	hud.settlement_requested.connect(show_settlement)
	hud.run_finished.connect(_on_run_finished)
	hud.week_finished.connect(_on_week_finished)

## 显示主地图首次教程（Intro VN 结束后触发）
func _show_main_map_tutorial() -> void:
	tutorial_overlay.try_show(
		"main_map",
		"欢迎来到归潮镇",
		"这里是归潮镇地图。点击地点查看停留的居民与正在发生的事件。\n准备好后点「推进时间」，居民的位置和命运都会随之变化。"
	)

## 显示全局 Toast 提示，1.8 秒后自动消失
func show_toast(message: String) -> void:
	toast_label.text = message
	toast_panel.visible = true
	await get_tree().create_timer(1.8).timeout
	toast_panel.visible = false

## 显示时间推进或干预结算结果面板
func show_settlement(settlement_data: Dictionary) -> void:
	settlement_panel.show_settlement(settlement_data)

## 弹出全局通用确认对话框
func show_confirm(
	title: String,
	message: String,
	confirm_text: String = "确定",
	cancel_text: String = "取消"
) -> void:
	confirm_dialog.show_confirm(title, message, confirm_text, cancel_text)

## 替换当前屏幕：释放旧屏幕并添加新屏幕到 ScreenRoot
func _set_screen(screen: Control) -> void:
	if current_screen != null:
		current_screen.queue_free()
	current_screen = screen
	screen_root.add_child(current_screen)

## 新游戏请求处理：重置状态 → 显示 HUD → 打开 Intro VN → 结束后弹教程
func _on_new_game_requested() -> void:
	game_state.reset_to_new_game()
	show_hud()
	var dlg: Control = current_screen.get_node("DialogueEventScreen")
	dlg.finished.connect(_on_intro_finished, CONNECT_ONE_SHOT)
	dlg.open(INTRO_DATA)

## Intro VN 播放完毕：显示主地图首次教程
func _on_intro_finished() -> void:
	_show_main_map_tutorial()

## 退出游戏请求
func _on_quit_requested() -> void:
	get_tree().quit()

## 打开设置界面请求
func _on_settings_requested() -> void:
	settings_screen.open()

func _on_settings_closed() -> void:
	pass

## 打开事件历史回顾：先关闭暂停菜单再打开历史界面
func _on_event_history_requested() -> void:
	pause_menu.close()
	event_history_screen.open(game_state.get_event_history())

func _on_event_history_closed() -> void:
	pass

## 打开关于我们界面请求
func _on_credits_requested() -> void:
	credits_screen.open()

func _on_credits_closed() -> void:
	pass

## 读档请求：MVP 阶段显示占位 Toast
func _on_load_requested() -> void:
	show_toast("读档将在存档系统接入后开放。")

## 局终处理：关闭暂停菜单，解锁画廊记录，失败开 GameOverScreen，正常开 FinalSummaryScreen
func _on_run_finished(ending: Dictionary) -> void:
	pause_menu.close()
	var ending_id: String = String(ending.get("ending_id", ""))
	if ending_id != "":
		Settings.unlock_ending(ending_id)
	if bool(ending.get("is_failure", false)):
		game_over_screen.open(ending, false)
	else:
		final_summary_screen.open(ending)

## 周结算处理：关闭暂停菜单，打开周结算界面
func _on_week_finished(week_data: Dictionary) -> void:
	pause_menu.close()
	week_summary_screen.open(week_data)

## 周结算「继续」按钮：关闭周结算界面，回到 HUD 主循环
func _on_week_continue() -> void:
	week_summary_screen.close()

## 总评「查看最终结局」：关闭总评，打开最终结局界面
func _on_view_ending_requested(ending: Dictionary) -> void:
	final_summary_screen.close()
	ending_screen.open(ending)

## 结局回顾请求：打开结局画廊界面
func _on_ending_review_requested() -> void:
	ending_gallery_screen.open()

func _on_gallery_closed() -> void:
	pass

## 重新开始请求：关闭所有结局界面，重置状态，重开 HUD
func _on_restart_requested() -> void:
	_close_ending_flow()
	game_state.reset_to_new_game()
	show_hud()

## 结局流程返回主菜单：关闭所有结局界面，回到主菜单
func _on_ending_return_to_menu() -> void:
	_close_ending_flow()
	show_main_menu()

## 关闭结局流程全部三个覆盖层（总评/结局/失败）
func _close_ending_flow() -> void:
	final_summary_screen.close()
	ending_screen.close()
	game_over_screen.close()

func _on_confirm_requested(title: String, message: String, confirm_text: String, cancel_text: String) -> void:
	show_confirm(title, message, confirm_text, cancel_text)
