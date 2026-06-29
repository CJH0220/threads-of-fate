extends Node
class_name BackendClient

## 后端服务客户端（Godot Autoload，全局访问名 Backend）。
## 封装 FastAPI HTTP 接口与 WebSocket 流式通信。
## 特性：
##   - HTTP：/health（连通检查）、/new-game（新局）、/state（状态拉取）
##   - WebSocket：/ws/game（时间推进、事件流式推送、NPC 行动广播）
##   - 自动重连（断线后 3s 重试）
##   - Mock fallback：后端不可用时自动降级到本地 Mock

signal connected
signal disconnected
signal error(message: String)

## HTTP 响应事件（每个请求完成后触发）
signal health_completed(healthy: bool)
signal new_game_completed(state: Dictionary)
signal state_completed(state: Dictionary)
signal save_completed(data: Dictionary)
signal load_completed(state: Dictionary)

## WebSocket 服务端推送事件
signal time_advanced(data: Dictionary)
signal event_triggered(data: Dictionary)
signal npc_action(data: Dictionary)
signal settlement_complete(data: Dictionary)
signal npc_response(data: Dictionary)

## 后端地址配置
const DEFAULT_BASE_URL := "http://localhost:8000"
const WS_PATH := "/ws/game"

## 后端基址（可在 Settings 中覆盖，或由启动参数注入）
var base_url: String = DEFAULT_BASE_URL

## HTTP 客户端（复用连接）
var _http: HTTPRequest

## WebSocket 客户端
var _ws: WebSocketPeer

## WebSocket 连接状态
var _ws_connected: bool = false

## 重连计时器
var _reconnect_timer: Timer

## HTTP 超时计时器
var _http_timeout_timer: Timer

## 当前 request_id 序列号（用于消息关联）
var _request_seq: int = 0

## Mock 降级标记：true 表示后端不可达，所有调用均转发至 MockGameState
var use_mock_fallback: bool = false

func _ready() -> void:
	_http = HTTPRequest.new()
	## HTTP 超时：2 秒无响应则失败
	_http.timeout = 2.0
	add_child(_http)

	_ws = WebSocketPeer.new()

	_reconnect_timer = Timer.new()
	_reconnect_timer.wait_time = 3.0
	_reconnect_timer.one_shot = true
	_reconnect_timer.timeout.connect(_reconnect_ws)
	add_child(_reconnect_timer)

	_http_timeout_timer = Timer.new()
	_http_timeout_timer.one_shot = true
	add_child(_http_timeout_timer)

func _process(_delta: float) -> void:
	if _ws_connected:
		_poll_ws()

# ──────────────────────────────────────────
# HTTP API
# ──────────────────────────────────────────

## 健康检查。2 秒超时自动降级到 Mock。
func check_health() -> void:
	var url = base_url + "/health"
	var err = _http.request(url)
	if err != OK:
		use_mock_fallback = true
		health_completed.emit(false)
		return
	_http.request_completed.connect(_on_health_completed, CONNECT_ONE_SHOT)
	## 超时兜底：2 秒后自动降级
	_http_timeout_timer.wait_time = 2.0
	_http_timeout_timer.timeout.connect(_on_health_timeout, CONNECT_ONE_SHOT)
	_http_timeout_timer.start()

func _on_health_timeout() -> void:
	## HTTP 超时：强制降级到 Mock
	_http.cancel_request()
	use_mock_fallback = true
	health_completed.emit(false)

func _on_health_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	## 取消超时计时器
	_http_timeout_timer.stop()
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		use_mock_fallback = true
		health_completed.emit(false)
		return
	var json = JSON.new()
	if json.parse(body.get_string_from_utf8()) != OK:
		use_mock_fallback = true
		health_completed.emit(false)
		return
	var data = json.data as Dictionary
	use_mock_fallback = false
	health_completed.emit(data.get("status", "") == "ok")

## 创建新游戏。触发 new_game_completed 信号。
func new_game() -> void:
	if use_mock_fallback:
		# 由 BackendGameState 本地处理
		new_game_completed.emit({})
		return
	var url = base_url + "/new-game"
	var err = _http.request(url, [], HTTPClient.METHOD_POST)
	if err != OK:
		error.emit("POST /new-game 失败: %d" % err)
		return
	_http.request_completed.connect(_on_new_game_completed, CONNECT_ONE_SHOT)

func _on_new_game_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		error.emit("创建游戏失败: HTTP %d" % response_code)
		return
	var json = JSON.new()
	if json.parse(body.get_string_from_utf8()) != OK:
		error.emit("响应解析失败")
		return
	var wrapper = json.data as Dictionary
	if bool(wrapper.get("success", false)):
		new_game_completed.emit(wrapper.get("data", {}))
	else:
		error.emit(wrapper.get("error", "未知错误"))

## 拉取当前游戏完整状态。触发 state_completed 信号。
func get_state() -> void:
	if use_mock_fallback:
		state_completed.emit({})
		return
	var url = base_url + "/state"
	var err = _http.request(url)
	if err != OK:
		error.emit("GET /state 失败: %d" % err)
		return
	_http.request_completed.connect(_on_state_completed, CONNECT_ONE_SHOT)

func _on_state_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		error.emit("拉取状态失败: HTTP %d" % response_code)
		return
	var json = JSON.new()
	if json.parse(body.get_string_from_utf8()) != OK:
		error.emit("响应解析失败")
		return
	var wrapper = json.data as Dictionary
	if bool(wrapper.get("success", false)):
		state_completed.emit(wrapper.get("data", {}))
	else:
		error.emit(wrapper.get("error", "未知错误"))

# ──────────────────────────────────────────
# WebSocket API
# ──────────────────────────────────────────

## 连接 WebSocket 游戏通道。
func connect_ws() -> void:
	if _ws_connected:
		return
	var ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + WS_PATH
	var err = _ws.connect_to_url(ws_url)
	if err != OK:
		error.emit("WebSocket 连接失败: %d" % err)
		_reconnect_timer.start()
		return

## 断开 WebSocket。
func disconnect_ws() -> void:
	if not _ws_connected:
		return
	_ws.close()
	_ws_connected = false
	disconnected.emit()

func _poll_ws() -> void:
	if _ws.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
		if _ws_connected:
			_ws_connected = false
			disconnected.emit()
			_reconnect_timer.start()
		return
	if not _ws_connected:
		_ws_connected = true
		connected.emit()
	while _ws.get_available_packet_count() > 0:
		var packet = _ws.get_packet().get_string_from_utf8()
		_dispatch_ws_message(packet)

func _reconnect_ws() -> void:
	if not _ws_connected:
		connect_ws()

## 分发服务端推送消息。
func _dispatch_ws_message(raw: String) -> void:
	var json = JSON.new()
	if json.parse(raw) != OK:
		return
	var msg = json.data as Dictionary
	var msg_type = String(msg.get("type", ""))
	var payload = msg.get("payload", {}) as Dictionary

	match msg_type:
		"time_advanced":
			time_advanced.emit(payload)
		"event_triggered":
			event_triggered.emit(payload)
		"npc_action":
			npc_action.emit(payload)
		"settlement_complete":
			settlement_complete.emit(payload)
		"game_created":
			new_game_completed.emit(payload)
		"game_state":
			state_completed.emit(payload)
		"game_saved":
			save_completed.emit(payload)
		"game_loaded":
			load_completed.emit(payload)
		"npc_response":
			npc_response.emit(payload)
		"error":
			error.emit(String(payload.get("message", "未知错误")))

## 发送 advance_time 消息推进一个时段。
func send_advance_time() -> void:
	if use_mock_fallback:
		return
	if not _ws_connected:
		error.emit("WebSocket 未连接")
		return
	_request_seq += 1
	var msg = {
		"type": "advance_time",
		"request_id": "adv_%d" % _request_seq,
		"timestamp": Time.get_unix_time_from_system(),
	}
	_ws.send_text(JSON.stringify(msg))

## 发送 chat 消息与 NPC 对话。
func send_chat(npc_id: String, message: String, day: int = 1) -> void:
	if use_mock_fallback:
		return
	if not _ws_connected:
		error.emit("WebSocket 未连接")
		return
	_request_seq += 1
	var msg = {
		"type": "chat",
		"request_id": "chat_%d" % _request_seq,
		"timestamp": Time.get_unix_time_from_system(),
		"payload": {
			"npc_id": npc_id,
			"message": message,
			"day": day,
		},
	}
	_ws.send_text(JSON.stringify(msg))

## 通过 WS 获取游戏状态（替代 HTTP 轮询）。
func send_get_state() -> void:
	if use_mock_fallback:
		return
	if not _ws_connected:
		error.emit("WebSocket 未连接")
		return
	_request_seq += 1
	var msg = {
		"type": "get_state",
		"request_id": "state_%d" % _request_seq,
		"timestamp": Time.get_unix_time_from_system(),
	}
	_ws.send_text(JSON.stringify(msg))

## 发送干预执行请求。
func send_intervention(event_id: String, intervention_id: String) -> void:
	if use_mock_fallback:
		return
	if not _ws_connected:
		error.emit("WebSocket 未连接")
		return
	_request_seq += 1
	var msg = {
		"type": "apply_intervention",
		"request_id": "int_%d" % _request_seq,
		"timestamp": Time.get_unix_time_from_system(),
		"payload": {
			"event_id": event_id,
			"intervention_id": intervention_id,
		},
	}
	_ws.send_text(JSON.stringify(msg))

## 通过 WS 请求保存游戏。
func send_save(slot: int = 1) -> void:
	if use_mock_fallback:
		return
	if not _ws_connected:
		error.emit("WebSocket 未连接")
		return
	_request_seq += 1
	var msg = {
		"type": "save_game",
		"request_id": "save_%d" % _request_seq,
		"timestamp": Time.get_unix_time_from_system(),
		"payload": {"slot": slot},
	}
	_ws.send_text(JSON.stringify(msg))

## 通过 WS 请求加载存档。
func send_load(slot: int = 1) -> void:
	if use_mock_fallback:
		return
	if not _ws_connected:
		error.emit("WebSocket 未连接")
		return
	_request_seq += 1
	var msg = {
		"type": "load_game",
		"request_id": "load_%d" % _request_seq,
		"timestamp": Time.get_unix_time_from_system(),
		"payload": {"slot": slot},
	}
	_ws.send_text(JSON.stringify(msg))
