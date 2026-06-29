# 前后端集成指南

## 概述

Godot 前端已实现与 Python FastAPI 后端的完整通信层，包含 HTTP 接口与 WebSocket 流式推送。

## 文件结构

```
godot/scripts/
├── app/
│   ├── backend_client.gd          # 后端客户端 Autoload（全局名 Backend）
│   └── main.gd                    # 主场景：USE_BACKEND 开关控制
└── adapters/
    ├── mock_game_state.gd         # 本地 Mock（MVP 竖切）
    └── backend_game_state.gd      # 后端适配器（API 与 Mock 一致）
```

## 切换后端 / Mock

在 `main.gd` 第 60 行：

```gdscript
## true = 使用真实后端，false = 使用本地 Mock
const USE_BACKEND := true
```

**降级机制**：当 `USE_BACKEND=true` 但后端健康检查失败时，自动降级到 `MockGameState`。

## BackendClient API

### HTTP 接口

| 方法 | 说明 | 信号 |
|------|------|------|
| `check_health()` | 后端连通检查 | `health_completed(healthy: bool)` |
| `new_game()` | 创建新游戏 | `new_game_completed(state: Dictionary)` |
| `get_state()` | 拉取完整状态 | `state_completed(state: Dictionary)` |

### WebSocket 接口

| 方法 | 说明 |
|------|------|
| `connect_ws()` | 连接 `/ws/game` |
| `disconnect_ws()` | 断开连接 |
| `send_advance_time()` | 推进一个时段 |
| `send_chat(npc_id, message, day)` | 与 NPC 对话 |
| `send_get_state()` | WS 通道拉取状态 |

### WebSocket 接收事件

| 信号 | 触发时机 |
|------|----------|
| `connected` | WS 连接成功 |
| `disconnected` | WS 断开 |
| `time_advanced(data)` | 时间推进结果 |
| `event_triggered(data)` | 事件触发 |
| `npc_action(data)` | NPC AI 决策 |
| `settlement_complete(data)` | 时段结算完成 |
| `error(message)` | 任意错误 |

## 数据契约对齐

### 时间槽映射

| 后端枚举 | 前端枚举 | 中文 |
|----------|----------|------|
| `morning` | `Morning` | 早晨 |
| `noon` | `Afternoon` | 下午 |
| `night` | `Night` | 夜晚 |

### NPC 数据结构转换

后端嵌套结构：
```python
{
  "static": {"id": "...", "name": "...", ...},
  "dynamic": {"location": "...", "happiness": 50, ...},
  "memory_summary": {...}
}
```

前端扁平化（便于 UI 绑定）：
```gdscript
{
  "npc_id": "...",
  "name": "...",
  "occupation": "...",
  "location": "...",
  "happiness": 50,
  ...
}
```

## 集成清单

### Phase 1 已完成 ✅
- [x] `BackendClient` Autoload 封装
- [x] HTTP `/health` 健康检查
- [x] HTTP `/new-game` 新局创建
- [x] HTTP `/state` 状态拉取
- [x] Mock 自动降级机制

### Phase 2 已完成 ✅
- [x] WebSocket `/ws/game` 连接管理
- [x] 自动重连（断开后 3s 重试）
- [x] `advance_time` 发送与接收
- [x] `event_triggered` 事件推送
- [x] `settlement_complete` 结算推送
- [x] `npc_action` NPC 行动推送
- [x] `chat` 对话发送

### Phase 3 待实现 ⏳
- [ ] `/save/{slot}` 存档接口
- [ ] `/load/{slot}` 读档接口
- [ ] `/saves` 存档列表接口
- [ ] 干预执行接口（POST `/intervene`）
- [ ] 缘线数据同步（bond changes）
- [ ] 业线数据同步（karma changes）

## 后端启动方式

```bash
cd /mnt/c/dev/game1
conda activate fate-weaver
uvicorn src.backend.server.main:app --reload --host 0.0.0.0 --port 8000
```

## 测试流程

1. 启动后端服务（见上）
2. `USE_BACKEND := true`
3. Godot 启动 → 健康检查通过 → `BackendGameState` 实例化 → WS 自动连接
4. 点击「新游戏」→ 后端 `/new-game` → Intro VN → HUD 显示后端数据
5. 点击「推进时间」→ WS `advance_time` → 接收 `time_advanced` → `settlement_complete`
