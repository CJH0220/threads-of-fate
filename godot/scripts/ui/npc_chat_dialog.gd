extends Control
class_name NpcChatDialog

## NPC 对话弹窗。玩家（土地公视角）与选定 NPC 自由对话，回复由后端 LLM 生成。
## 依赖：Backend autoload（send_chat + npc_response 信号）。

signal closed()

@onready var title_label: Label = $Panel/VBox/HeaderRow/TitleLabel
@onready var npc_portrait_image: TextureRect = $Panel/VBox/HeaderRow/NpcPortrait/NpcPortraitImage
@onready var npc_portrait_initial: Label = $Panel/VBox/HeaderRow/NpcPortrait/NpcPortraitInitial
@onready var tudi_portrait_image: TextureRect = $Panel/VBox/HeaderRow/TudiPortrait/TudiPortraitImage
@onready var tudi_portrait_initial: Label = $Panel/VBox/HeaderRow/TudiPortrait/TudiPortraitInitial
@onready var history_text: RichTextLabel = $Panel/VBox/HistoryText
@onready var input_edit: LineEdit = $Panel/VBox/InputRow/InputEdit
@onready var send_button: Button = $Panel/VBox/InputRow/SendButton
@onready var close_button: Button = $Panel/VBox/InputRow/CloseButton
@onready var hint_label: Label = $Panel/VBox/HintLabel

var _npc_id: String = ""
var _npc_name: String = ""
var _current_day: int = 1
var _waiting_reply: bool = false
var _connected_backend: bool = false

func _ready() -> void:
	send_button.pressed.connect(_on_send)
	close_button.pressed.connect(_on_close)
	input_edit.text_submitted.connect(func(_t): _on_send())
	_apply_tudi_portrait()
	visible = false

func open(npc_id: String, npc_name: String, day: int) -> void:
	_npc_id = npc_id
	_npc_name = npc_name
	_current_day = day
	_waiting_reply = false
	title_label.text = "与 %s 交谈" % npc_name
	_apply_npc_portrait(npc_id, npc_name)
	history_text.clear()
	history_text.append_text("[color=#a4a6b0]（你以土地公之身，在无形中垂询 %s。）[/color]\n" % npc_name)
	input_edit.text = ""
	hint_label.text = ""
	_set_input_enabled(true)
	_ensure_backend_connected()
	visible = true
	input_edit.grab_focus()

## 应用对方 NPC 头像（顶栏左侧）
func _apply_npc_portrait(npc_id: String, display_name: String) -> void:
	if npc_portrait_image == null:
		return
	var tex: Texture2D = PortraitService.get_portrait(npc_id)
	if tex != null:
		npc_portrait_image.texture = tex
		npc_portrait_image.visible = true
		npc_portrait_initial.visible = false
	else:
		npc_portrait_image.texture = null
		npc_portrait_image.visible = false
		npc_portrait_initial.text = PortraitService.get_initial(display_name)
		npc_portrait_initial.modulate = PortraitService.get_color(npc_id)
		npc_portrait_initial.visible = true

## 应用玩家（土地公）头像（顶栏右侧），只在 _ready 时设置一次
func _apply_tudi_portrait() -> void:
	if tudi_portrait_image == null:
		return
	var tex: Texture2D = PortraitService.get_portrait("tudi_gong")
	if tex != null:
		tudi_portrait_image.texture = tex
		tudi_portrait_image.visible = true
		tudi_portrait_initial.visible = false
	else:
		tudi_portrait_initial.visible = true

func close() -> void:
	visible = false
	_disconnect_backend()
	closed.emit()

func _ensure_backend_connected() -> void:
	if _connected_backend:
		return
	if not Engine.has_singleton("Backend") and not _get_backend():
		return
	var backend: Node = _get_backend()
	if backend == null:
		return
	if not backend.npc_response.is_connected(_on_npc_response):
		backend.npc_response.connect(_on_npc_response)
	if not backend.error.is_connected(_on_backend_error):
		backend.error.connect(_on_backend_error)
	_connected_backend = true

func _disconnect_backend() -> void:
	if not _connected_backend:
		return
	var backend: Node = _get_backend()
	if backend != null:
		if backend.npc_response.is_connected(_on_npc_response):
			backend.npc_response.disconnect(_on_npc_response)
		if backend.error.is_connected(_on_backend_error):
			backend.error.disconnect(_on_backend_error)
	_connected_backend = false

func _get_backend() -> Node:
	return get_node_or_null("/root/Backend")

func _set_input_enabled(enabled: bool) -> void:
	input_edit.editable = enabled
	send_button.disabled = not enabled

func _on_send() -> void:
	if _waiting_reply:
		return
	var message: String = input_edit.text.strip_edges()
	if message == "":
		return
	if _npc_id == "":
		return

	var backend: Node = _get_backend()
	if backend == null:
		hint_label.text = "后端未就绪。"
		return
	if backend.use_mock_fallback:
		hint_label.text = "当前为 Mock 模式，无法调用大模型对话。"
		return

	history_text.append_text("[color=#f7e6a8]土地公：[/color]%s\n" % message)
	input_edit.text = ""
	_waiting_reply = true
	_set_input_enabled(false)
	hint_label.text = "……%s 正在思索。" % _npc_name
	backend.send_chat(_npc_id, message, _current_day)

func _on_npc_response(payload: Dictionary) -> void:
	if not visible:
		return
	var npc_id: String = String(payload.get("npc_id", ""))
	if npc_id != _npc_id:
		return
	var reply: String = String(payload.get("response", "")).strip_edges()
	if reply == "":
		reply = "（%s 沉默不语。）" % _npc_name
	history_text.append_text("[color=#b8e0d2]%s：[/color]%s\n" % [_npc_name, reply])
	hint_label.text = ""
	_waiting_reply = false
	_set_input_enabled(true)
	input_edit.grab_focus()

func _on_backend_error(message: String) -> void:
	if not visible or not _waiting_reply:
		return
	hint_label.text = "对话出错：%s" % message
	_waiting_reply = false
	_set_input_enabled(true)

func _on_close() -> void:
	close()

func _unhandled_input(event: InputEvent) -> void:
	if visible and event.is_action_pressed("ui_cancel"):
		_on_close()
		get_viewport().set_input_as_handled()
