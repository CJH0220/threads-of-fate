# 《命运的织线》系统整合指南

> 最后更新：2026-06-28  
> 状态：Godot MVP 完成 + Python 后端完成，准备集成

---

## 目录

1. [系统总览](#1-系统总览)
2. [前后端技术栈对比](#2-前后端技术栈对比)
3. [核心变量对应表](#3-核心变量对应表)
4. [模块连接架构图](#4-模块连接架构图)
5. [API 对接清单](#5-api-对接清单)
6. [Godot 集成路线图](#6-godot-集成路线图)
7. [数据契约对比](#7-数据契约对比)
8. [前后端功能映射](#8-前后端功能映射)

---

## 1. 系统总览

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         玩家设备                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     Godot 前端                            │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │  UI 层：菜单 / HUD / VN演出 / 结局 / 事件历史       │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │  MockGameState：MVP 模拟状态（JSON mock 数据）       │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  │  ┌─────────────────────────────────────────────────────┐ │   │
│  │  │  APIClient：HTTP REST + WebSocket 客户端（待接入）   │ │   │
│  │  └─────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                            │                                        │
│                            ▼ HTTP / WebSocket                        │
└────────────────────────────┼────────────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────────────┐
│                  后端服务器 (FastAPI)                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  API 层：REST + WebSocket                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  GameSession：5 模块容器（time/resource/bond/karma/agents）│  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AI 层：NpcAgent x14（static/dynamic/memory + LLM）          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  数据层：CSV 蓝图 + JSON 存档 + LLM（Qwen3-14B）            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 当前状态

| 层 | 状态 | 说明 |
|---|------|------|
| **Godot 前端** | ✅ MVP 完成 | 完整 UI 系统，使用 MockGameState 从本地 JSON 加载 |
| **Python 后端** | ✅ 完成 | 完整引擎 + API + 14 个 NPC Agent，308 测试通过 |
| **集成层** | ⏳ 待接入 | Godot 需要添加 HTTP/WebSocket 客户端，替换 MockGameState |

---

## 2. 前后端技术栈对比

| 维度 | Godot 前端 | Python 后端 |
|------|-----------|-------------|
| **引擎/框架** | Godot 4.4 | FastAPI 0.124.4 + Pydantic v2 |
| **语言** | GDScript | Python 3.8+ |
| **状态管理** | `MockGameState` 类 | `GameSession` dataclass |
| **NPC 数据** | `characters.json` 静态数据 | `NPC基础表.csv` 动态加载 + 3层结构 |
| **事件系统** | `events.json` 静态触发 | CSV 事件池 + 权重匹配 + 多模块结算 |
| **时间系统** | 3时段/天，60天 | `TimeState`，周阶段系统，终局检测 |
| **资源系统** | 4资源（香火/神力/阴德/阳德） | `ResourceState`，每日结算，周结算公式 |
| **缘线系统** | UI 显示（BondView） | `BondManager`，有向图，LLM prompt 注入 |
| **业线系统** | UI 显示（KarmaView） | `KarmaManager`，节点定义，进度追踪 |
| **对话系统** | 预设分段文本 | 实时 LLM 生成，每个 NPC 独立记忆 |
| **存档** | Settings 内存储结局画廊 | `JsonStorage`，完整快照，4 槽位 |

---

## 3. 核心变量对应表

### 3.1 资源变量

| 含义 | Godot (MockGameState) | Python 后端 (ResourceState) | 取值范围 |
|-----|----------------------|-----------------------------|---------|
| 香火 | `incense` | `incense` | 0 ~ ∞ |
| 神力 | `divine_power` | `divine_power_current` / `divine_power_max` | 0 ~ 20 |
| 阳德 | `yang_de` | `yang_de` | 0 ~ ∞ |
| 阴德 | `yin_de` | `yin_de` | 0 ~ ∞ |

> **注意**：Godot 当前只有 `divine_power`，后端区分了 `current` 和 `max`，每日恢复到 max

### 3.2 时间变量

| 含义 | Godot | Python 后端 | 取值 |
|-----|-------|-------------|------|
| 天数 | `day` | `TimeState.day` | 1 ~ 60 |
| 时段 | `time_slot` | `TimeState.slot` (Slot 枚举) | morning / noon / night |
| 周数 | 无 | `TimeState.week` | 1 ~ 9 |
| 周阶段 | 无 | `TimeState.phase_name` | 9 个叙事阶段名 |

> **注意**：Godot 当前是 3 时段（morning/afternoon/night），后端也是 3 时段但枚举值是 `MORNING/NOON/NIGHT`，需统一

### 3.3 NPC 三层结构对比

| 层 | Godot (简化) | Python 后端 (完整) |
|---|--------------|---------------------|
| **静态层** | `NpcData`：id/name/age/bond_summaries | `NpcStatic`：id/name/age/occupation/tier/background + FixedAttributes(4维) + Personality(5维) + core_wish |
| **动态层** | `current_location` / `karma_progress` | `NpcDynamic`：location/happiness/energy/emotion/current_goal + karma_main_progress + karma_side_progress |
| **记忆层** | 无 | `AgentMemory`：event_chain(50) + key_memories(30) + impressions + memory_overflow_count |

### 3.4 地点对应表

| Godot Location | Python Location 枚举 | 中文名 |
|---------------|---------------------|-------|
| `temple` | `TEMPLE` | 寺庙 |
| `school` | `SCHOOL` | 学校 |
| `port` | `PORT` | 港口 |
| `coffee_shop` | `CAFE` | 咖啡厅 |
| `wine_bar` | - (待添加) | 酒吧 |
| `seafood_shop` | - (待添加) | 海鲜店 |
| `clinic` | `CLINIC` | 诊所 |
| `beach` | `BEACH` | 沙滩 |
| `plaza` | `PLAZA` | 广场 |
| `police_station` | `POLICE_STATION` | 警局 |
| `mountain_forest` | `MOUNTAIN_FOREST` | 山林 |
| - | `SHOPPING_STREET` | 商业街 |
| - | `BOOKSTORE` | 书店 |
| - | `RESIDENCE` | 住所 |

> **差异**：后端有 12 个地点，Godot 当前有 10 个，缺少 `shopping_street` / `bookstore` / `residence`，Godot 多了 `wine_bar` / `seafood_shop`

### 3.5 情绪对应表

| Godot | Python Emotion 枚举 |
|-------|---------------------|
| - (未实现) | `HAPPY` |
| - | `SAD` |
| - | `ANGRY` |
| - | `FEARFUL` |
| - | `CALM` |
| - | `EXCITED` |
| - | `ANXIOUS` |
| - | `NEUTRAL` |

---

## 4. 模块连接架构图

### 4.1 Godot 内部模块连接

```
Main.gd (场景根)
├── ScreenRoot (Control)
│   ├── MainMenu 场景
│   │   ├── new_game → _on_new_game_requested()
│   │   ├── load_game → Toast
│   │   ├── settings → SettingsScreen
│   │   ├── credits → CreditsScreen
│   │   └── quit → 退出
│   └── MainGameUI 场景
│       ├── bind_state(MockGameState)
│       ├── TopBar：时间/资源显示
│       ├── MapContent：地图 + 地点瓦片 + 危险警告
│       ├── BottomPanel：NPC/Event Tab + Detail 面板
│       ├── BondView：缘线覆盖层
│       ├── KarmaView：业线覆盖层
│       ├── DialogueEventScreen：VN 演出
│       └── TimeTransition：时段过渡动画
├── Global Overlays（覆盖层）
│   ├── SettingsScreen（设置）
│   ├── CreditsScreen（关于我们）
│   ├── PauseMenu（暂停菜单，Esc 呼出）
│   ├── FinalSummaryScreen（60天总评）
│   ├── EndingScreen（结局展示）
│   ├── GameOverScreen（失败）
│   ├── WeekSummaryScreen（周结算）
│   ├── EventHistoryScreen（事件历史回顾）
│   ├── EndingGalleryScreen（结局画廊）
│   └── TutorialOverlay（教程引导）
├── ToastPanel（全局提示）
├── SettlementPanel（结算面板）
└── ConfirmDialog（确认对话框）
```

### 4.2 Python 后端内部模块连接

```
FastAPI 应用 (server/main.py)
├── Middleware：CORS + 异常捕获
├── REST Routes（server/routes/）
│   ├── health：GET /health
│   └── game：/new-game, /state, /chat/{npc_id}, /save, /load, /saves
└── WebSocket Route：/ws/game（实时通信）
    ├── Client → Server：advance_time / chat / get_state / new_game / save_game / load_game
    └── Server → Client：time_advanced / event_triggered / npc_action / settlement_complete / npc_response / game_state

GameSession（engine/game_session.py）
├── TimeState：时间推进，天/时段/周/阶段
├── ResourceState：资源管理 + 每日/周结算
├── BondManager：缘线有向图，关系账本
├── KarmaManager：业线节点 + 进度追踪
└── AgentManager：批量管理 14 个 NpcAgent

NpcAgent（ai/npc_agent/）
├── static：NpcStatic（不可变属性）
├── dynamic：DynamicState（可变状态 + delta 追踪）
├── memory：MemoryStore（事件链 + 关键记忆 + 印象）
├── templates：SystemPrompt 生成（性格 + 缘线注入）
├── llm_client：Qwen3-14B 客户端（负载均衡 + 降级）
└── public API：think() / respond() / remember()
```

### 4.3 前后端通信连接图

```
┌─────────────────────────────────────────────────────────────┐
│                    Godot 前端                                 │
│                                                               │
│  ┌──────────────┐      ┌───────────────────────────┐       │
│  │ MainMenu     │─────▶│  APIClient (HTTP)         │       │
│  │  - 新游戏    │      │  POST /new-game           │       │
│  │  - 读档      │      │  POST /save/{slot}        │       │
│  └──────────────┘      │  POST /load/{slot}        │       │
│          │              │  GET  /state              │       │
│          │              │  POST /chat/{npc_id}      │       │
│          ▼              └─────────────┬─────────────┘       │
│  ┌──────────────┐                    │                     │
│  │ MainGameUI   │                    │ HTTP                │
│  │  - 推进时间  │                    │                     │
│  │  - 查看NPC   │                    ▼                     │
│  │  - 干预事件  │      ┌───────────────────────────┐       │
│  │  - NPC对话   │◀────│  WSClient (WebSocket)      │       │
│  └──────────────┘      │  advance_time             │       │
│          │              │  chat (real-time)         │       │
│          │              │  save_game / load_game    │       │
│          │              └─────────────┬─────────────┘       │
│          ▼                            │                     │
│  ┌──────────────┐                    │ WebSocket           │
│  │ VN 演出      │                    │                     │
│  │ 事件历史     │◀───────────────────┘                     │
│  │ 周/终结算    │                                          │
│  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI 后端                               │
│                                                               │
│  ┌──────────────┐    ┌────────────────────────────────┐   │
│  │  /new-game   │    │  /ws/game                       │   │
│  │  /state      │    │  ├─ advance_time → 流式推送     │   │
│  │  /save       │    │  ├─ event_triggered            │   │
│  │  /load       │    │  ├─ npc_action                  │   │
│  │  /saves      │    │  └─ settlement_complete         │   │
│  └──────────────┘    └────────────────────────────────┘   │
│         │                             │                      │
│         ▼                             ▼                      │
│  ┌─────────────────────────────────────────────┐            │
│  │              GameSession                     │            │
│  └─────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. API 对接清单

### 5.1 REST 端点（HTTP）

| 端点 | 方法 | Godot 调用时机 | 返回 |
|-----|------|---------------|------|
| `/health` | GET | 启动时检查后端连接 | `{"success": true}` |
| `/new-game` | POST | 主菜单「新游戏」点击 | `GameStateResponse`（初始状态） |
| `/state` | GET | 进入 HUD 时 / 定时同步 | `GameStateResponse`（完整状态） |
| `/chat/{npc_id}` | POST | NPC 详情页 / 地图点击 NPC 对话 | NPC 回复（LLM 生成） |
| `/save/{slot}` | POST | 暂停菜单「保存」 | 保存成功确认 |
| `/load/{slot}` | POST | 主菜单「读档」/ 暂停菜单「读档」 | `GameStateResponse` |
| `/saves` | GET | 主菜单存档列表 / 读档界面 | 4 槽位存档信息 |
| `/saves/{slot}` | DELETE | 删除存档 | 删除确认 |

**GameStateResponse 结构（前后端契约）：**
```gdscript
# Godot 侧需匹配此结构
var response = {
    "success": true,
    "data": {
        "day": 1,
        "slot": "morning",
        "incense": 50,
        "divine_power": 10,
        "yin_de": 0,
        "yang_de": 0,
        "npcs": [  # NpcSnapshot 数组
            {
                "static": { "id": "lin_chaoyin", "name": "林潮音", ... },
                "dynamic": { "location": "school", "happiness": 50, ... },
                "memory_summary": { ... }
            },
            ...
        ],
        "npc_total": 14
    },
    "error": ""
}
```

### 5.2 WebSocket 端点（实时流式）

**连接地址**：`ws://localhost:8000/ws/game`

#### 客户端 → 服务端消息

| type | payload | 触发时机 |
|------|---------|---------|
| `new_game` | `{}` | 新游戏（可选，用 REST 也可） |
| `advance_time` | `{}` | 点击「推进时间」按钮 |
| `chat` | `{"npc_id": "...", "message": "...", "day": 1}` | NPC 对话 |
| `get_state` | `{}` | 请求完整状态 |
| `save_game` | `{"slot": 1}` | 保存游戏 |
| `load_game` | `{"slot": 1}` | 加载游戏 |

#### 服务端 → 客户端消息（流式推送）

| type | 说明 | Godot 处理 |
|------|------|-----------|
| `time_advanced` | 时间已推进 | 更新 TopBar 时间显示 |
| `event_triggered` | 事件触发结果 | 显示事件详情 / VN 演出 |
| `npc_action` | 单个 NPC 行为决策 | 更新 NPC 状态 / 地图气泡 |
| `settlement_complete` | 结算完毕 | 更新资源 / 周结算界面 |
| `npc_response` | NPC 对话回复 | 显示对话框 |
| `game_state` | 完整状态快照 | 全量同步 |
| `game_created` / `game_loaded` / `game_saved` | 操作确认 | Toast 提示 |

---

## 6. Godot 集成路线图

### 6.1 阶段一：HTTP 基础通信（0.5 天）

**目标**：Godot 能与后端建立连接，获取初始游戏状态

- [ ] 创建 `HTTPClientWrapper` 单例
- [ ] 实现 `/health` 连接检查
- [ ] 实现 `/new-game` 请求与 `GameStateResponse` 解析
- [ ] 实现 `/state` 请求
- [ ] 改造 `MockGameState`：添加 `from_api_response()` 方法

### 6.2 阶段二：WebSocket 流式通信（1 天）

**目标**：时间推进触发后端结算，接收流式事件

- [ ] 创建 `WebSocketClientWrapper` 单例
- [ ] 实现连接 / 重连 / 心跳机制
- [ ] 实现 `advance_time` 消息发送
- [ ] 接收并处理 `time_advanced` → 更新时间显示
- [ ] 接收并处理 `event_triggered` → 触发事件 UI
- [ ] 接收并处理 `npc_action` → 更新 NPC 状态
- [ ] 接收并处理 `settlement_complete` → 资源结算

### 6.3 阶段三：NPC 对话系统接入（0.5 天）

**目标**：VN 演出从预设文本变为 LLM 实时生成

- [ ] 复用 HTTP 客户端调用 `/chat/{npc_id}`
- [ ] 或通过 WebSocket 发送 `chat` 消息
- [ ] 改造 `DialogueEventScreen`：支持动态文本分段
- [ ] 添加「正在思考…」加载状态
- [ ] LLM 回复格式适配（角色名 + 对话内容）

### 6.4 阶段四：存档系统对接（0.5 天）

**目标**：从后端读取/保存游戏，替换本地简单存储

- [ ] 主菜单「继续游戏」/「读取存档」调用 `/saves` + `/load`
- [ ] 暂停菜单「保存」调用 `/save`
- [ ] 结局画廊从后端 `/saves` 获取已解锁结局
- [ ] 删除 Settings 本地结局存储

### 6.5 阶段五：数据结构对齐（1 天）

**目标**：消除 Godot MVP 与后端数据结构差异

- [ ] 统一时段命名：`afternoon` → `noon`
- [ ] 补充 Godot 地点枚举到 12 个
- [ ] 扩展 NPC 数据：从扁平结构到 static/dynamic/memory 三层
- [ ] 资源系统：添加 `divine_power_current` 和 `divine_power_max` 区分
- [ ] 添加情绪字段到 NPC 显示

### 6.6 阶段六：事件与干预系统对接（1 天）

**目标**：事件从静态 JSON 改为后端动态匹配结算

- [ ] 接收 `event_triggered` 消息，解析事件数据
- [ ] 显示事件详情面板（动态内容）
- [ ] 玩家选择干预选项 → 发送干预请求到后端
- [ ] 接收干预结算结果 → SettlementPanel 显示
- [ ] 事件历史：从后端 `event_history` 获取，不再本地记录

### 6.7 阶段七：缘线与业线数据同步（0.5 天）

**目标**：BondView / KarmaView 显示后端实时数据

- [ ] BondView：从 `GameStateResponse` 的 NPC `bond_summaries` 渲染
- [ ] KarmaView：从 NPC `karma_main_progress` / `karma_side_progress` 渲染
- [ ] 每次结算后更新缘线/业线显示

### 6.8 阶段八：结局判定从后端获取（0.5 天）

**目标**：终局由后端判定，不再本地计算

- [ ] 移除 Godot 本地 `evaluate_ending()` 逻辑
- [ ] 第 60 天推进后接收后端 `game_over` 或 `ending` 消息
- [ ] 根据返回结局类型打开对应结局界面
- [ ] 结局画廊：后端统一管理解锁状态

---

## 7. 数据契约对比

### 7.1 Godot MVP 数据契约

```gdscript
# godot/data/mock/*.json

characters.json → NpcData {
    npc_id, name, age, occupation, current_location,
    bond_summaries[], karma_summary, karma_progress, risk_level
}

events.json → EventData {
    event_id, event_name, location_id, time_slot,
    dialogue_segments[], available_intervention_ids[]
}

game_state.json → {
    day, time_slot, incense, divine_power,
    yang_de, yin_de, current_hint
}
```

### 7.2 Python 后端数据契约

```python
# src/backend/models/npc.py (Pydantic)

NpcStatic {
    id, name, age, occupation, tier, background,
    attributes: FixedAttributes(mind/faith/physique/charm),
    personality: Personality(kindness/aggression/sensibility/rationality/curiosity),
    core_wish
}

NpcDynamic {
    location, happiness, energy, emotion,
    current_goal, karma_main_progress, karma_side_progress{}
}

AgentMemory {
    event_chain[50], key_memories[30], impressions{}, memory_overflow_count
}

GameStateResponse {
    day, slot, incense, divine_power, yin_de, yang_de,
    npcs: NpcSnapshot[static/dynamic/memory_summary]
}
```

### 7.3 整合策略

**短期方案（快速集成）**：
1. Godot 保留 `MockGameState` 类名，内部改为从 API 填充
2. 添加 `ApiGameState` 子类，实现相同接口
3. 通过工厂模式切换：`GameStateFactory.create(use_backend: bool)`

**长期方案（架构清晰）**：
1. 抽象 `IGameState` 接口（interface）
2. `MockGameState` 实现：从本地 JSON 加载（开发调试用）
3. `BackendGameState` 实现：从 API 同步（正式发布用）

---

## 8. 前后端功能映射

### 8.1 主菜单功能映射

| 功能 | Godot MVP | Python 后端 | 集成 |
|-----|----------|------------|------|
| 新游戏 | 本地初始化 | POST `/new-game` | ✅ 后端接管 |
| 继续游戏 | Toast 占位 | GET `/saves` + POST `/load` | ✅ 后端有完整实现 |
| 读取存档 | Toast 占位 | POST `/load/{slot}` | ✅ 后端有 |
| 设置 | SettingsScreen + 本地存储 | Settings 仍本地 | ⚠️ 设置保留本地 |
| 关于我们 | 静态文本 | 无需后端 | ✅ 不变 |
| 退出游戏 | `get_tree().quit()` | 无需后端 | ✅ 不变 |

### 8.2 HUD 功能映射

| 功能 | Godot MVP | Python 后端 | 集成 |
|-----|----------|------------|------|
| 时间显示 | 本地 state | WebSocket `time_advanced` | ✅ 后端推送 |
| 资源显示 | 本地 state | WebSocket `settlement_complete` | ✅ 后端结算 |
| 地图渲染 | 本地瓦片数据 | 后端 NPC locations | ✅ 从快照更新 |
| 危险警告 | 本地事件匹配 | 后端 `event_triggered` | ✅ 后端匹配 |
| NPC 列表 | 本地 JSON | GameStateResponse.npcs | ✅ 后端提供 |
| 事件列表 | 本地 JSON | 后端事件系统匹配 | ✅ 后端匹配结算 |
| 推进时间 | 本地结算 | WebSocket `advance_time` | ✅ 后端流式结算 |
| 缘线视图 | 本地 bond_summaries | BondManager 数据 | ✅ 从快照获取 |
| 业线视图 | 本地 karma_progress | KarmaManager 数据 | ✅ 从快照获取 |
| NPC 详情 | 本地静态数据 | NpcSnapshot | ✅ 三层完整数据 |
| 事件详情 | 本地 dialogue_segments | 事件系统 + LLM 对话 | ✅ 后端实时生成 |

### 8.3 结局流程映射

| 界面 | Godot MVP 触发 | 后端触发 |
|-----|----------------|---------|
| 周结算 | 本地 day%7==0 | 后端 `is_new_week` 判定 → WS 推送 |
| 总评界面 | 本地 day>=60 | 后端 `can_advance()==false` → game_over/ending |
| 结局界面 | 本地 `evaluate_ending()` | 后端结局判定 → 发送结局数据 |
| 失败界面 | 本地 incense<100 | 后端资源结算判定 → 发送失败数据 |

---

## 附录 A：Godot → Python 字段重命名对照表

| Godot 字段名 | Python 字段名 | 说明 |
|-------------|---------------|------|
| `time_slot` | `slot` | 时段 |
| `divine_power` | `divine_power_current` / `divine_power_max` | 神力分当前/上限 |
| `bond_summaries` | `bond_summaries`（同） | 缘线摘要 |
| `karma_progress` | `karma_main_progress` | 主业线进度 |
| - | `karma_side_progress` | 支线进度（Godot 需新增） |
| `current_location` | `location` | 当前位置 |
| - | `happiness` / `energy` / `emotion` | 幸福度/精力/情绪（Godot 需新增） |
| - | `memory_summary` | 记忆摘要（Godot 需新增） |

---

## 附录 B：启动与调试命令

### 启动后端
```bash
cd /mnt/c/dev/game1
conda activate fate-weaver
uvicorn src.backend.server.main:app --reload --host 0.0.0.0 --port 8000
```

### 访问 API 文档
- Swagger UI：http://localhost:8000/docs
- ReDoc：http://localhost:8000/redoc

### 运行后端测试
```bash
pytest src/backend/tests/ -v
```

### 运行 Godot
```bash
cd /mnt/c/dev/game1/godot
./Godot_v4.4-stable_win64.exe --path .
```

---

## 附录 C：事件池系统对接

### C.1 事件数据流

```
Godot 前端                    Python 后端
   │                              │
   │  advance_time()          ┌─────────────────┐
   ├─────────────────────────▶│  event_matcher  │  匹配触发条件
   │                          └────────┬────────┘
   │                                   │
   │                          ┌────────▼─────────┐
   │                          │  event_executor  │  执行资源/缘线/业线变化
   │                          └────────┬────────┘
   │                                   │
   │  event_triggered + settlement    │
   ◀──────────────────────────────────┘
   │
   ▼
VN 演出 / 弹窗提示 / 更新 UI
```

### C.2 前后端事件字段映射

| 字段 | Godot 前端 | Python 后端 | 说明 |
|------|-----------|------------|------|
| 事件 ID | `event_id` | `EventTemplate.id` | 唯一标识，命名规范：`{scope}_{npc}_{desc}` |
| 事件名称 | `event_name` | `EventTemplate.name` | 中文显示名 |
| 类型 | `event_type` | `EventTemplate.event_type` | `Anchor` / `Key` / `Daily` |
| 风险等级 | `risk_level` | `EventTemplate.risk_level` | `Low` / `Medium` / `High` / `Fatal` |
| 周范围 | 由前端计算 | `EventTemplate.week_range` | `W1` / `W2-W4` / `Final` |
| 天范围 | 由前端计算 | `EventTemplate.day_range` | `Day1` / `Day3-5` / 空=任意 |
| 时段 | `time_slot` | `EventTemplate.time_slot` | `Morning` / `Afternoon` / `Night` / `Any` |
| 地点 | `location_id` | `EventTemplate.location` | 见地点对应表 |
| 参与 NPC | `participants` | `EventTemplate.participants` | NPC ID 数组 |
| 权重 | `weight` | `EventTemplate.weight` | 1~1000，>=1000 为锚点必触发 |
| 触发条件 | 由后端计算 | `trigger_conditions` | 复合条件表达式 |
| AI 对话策略 | 前端 VN 系统 | `ai_text_policy` | `None` / `DialogueAllowed` |
| 结局列表 | 由后端推送 | `EventTemplate.outcomes` | 多结局分支 |

### C.3 事件 WebSocket 消息

**事件触发推送（后端 → 前端）**

```json
{
  "type": "event_triggered",
  "request_id": "evt_123",
  "payload": {
    "event_id": "w1_chaoyin_study",
    "event_name": "海边苦读的少女",
    "event_type": "Key",
    "risk_level": "Low",
    "location": "beach",
    "participants": ["lin_chaoyin"],
    "outcome_id": "out_w1_chaoyin_study_default",
    "outcome_name": "静观其变",
    "description": "潮音在海边读一本奇怪的书，似乎遇到了困难...",
    "resource_changes": {
      "incense": +2,
      "divine_power": 0
    },
    "bond_changes": {
      "bond_chaoyin_fanghua": +5
    },
    "karma_changes": {
      "chaoyin_witch_line": +5
    },
    "has_intervention_options": true,
    "available_interventions": [
      {"id": "int_chaoyin_hint", "name": "托梦提示", "cost": 2},
      {"id": "int_chaoyin_distract", "name": "制造声响转移注意", "cost": 1}
    ]
  }
}
```

**干预执行请求（前端 → 后端）**

```json
{
  "type": "apply_intervention",
  "request_id": "int_456",
  "payload": {
    "event_id": "w1_chaoyin_study",
    "intervention_id": "int_chaoyin_hint"
  }
}
```

### C.4 事件池 CSV 配置（参考设计/event-pool-design.md）

| 配置文件 | 说明 | 状态 |
|---------|------|------|
| `events.csv` | 事件主表：ID/名称/类型/时间/地点/参与人/权重/条件/描述 | ✅ 后端已有结构 |
| `event_outcomes.csv` | 事件结果表：多分支/资源/缘线/业线/NPC状态/后续事件 | ✅ 后端已有结构 |
| `interventions.csv` | 可执行干预列表：名称/神力消耗/效果描述/条件 | ⏳ 待定义 |

### C.5 事件历史 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/events/history` | GET | 获取已触发事件列表 |
| `/api/events/{event_id}/detail` | GET | 获取单个事件完整详情 |
| `/api/events/triggered-ids` | GET | 获取已触发事件 ID 集合（条件判断用） |

---

> **集成总工作量估算**：约 5 ~ 6 个开发日完成全部对接
