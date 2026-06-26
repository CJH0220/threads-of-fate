# 后端架构文档

> 文件位置：`src/backend/ARCHITECTURE.md`  
> 更新日期：2026-06-26  
> **每次编写后端代码前请先阅读本文档。**

---

## 目录

1. [目录结构](#1-目录结构)
2. [模块职责](#2-模块职责)
3. [核心概念](#3-核心概念)
4. [数据流](#4-数据流)
5. [关键设计决策](#5-关键设计决策)
6. [命名规范](#6-命名规范)
7. [外部依赖](#7-外部依赖)
8. [开发节奏](#8-开发节奏)

---

## 1. 目录结构

```
src/backend/
│
├── ARCHITECTURE.md                # ← 本文档（代码前必读）
│
├── models/                        # 🔷 数据合同层
│   ├── npc.py                     #   NPC 三层结构、枚举
│   └── common.py                  #   ApiResponse、GameStateResponse
│
├── ai/                            # 🧠 AI 子系统
│   ├── llm_client/
│   │   ├── interface.py           #   BaseLLMClient 抽象接口
│   │   └── load_balanced.py       #   负载均衡 + 并发控制 + 故障转移
│   └── npc_agent/
│       ├── README.md              #   模块完整文档
│       ├── static.py              #   静态属性（不可变）+ build_static()
│       ├── dynamic.py             #   动态状态（可变）+ delta 追踪
│       ├── memory.py              #   记忆系统（事件链 + 印象 + 溢出）
│       ├── templates.py           #   System prompt 模板（含缘线注入）
│       ├── agent.py               #   NpcAgent 主类（think/respond/remember）
│       └── manager.py             #   AgentManager（批量管理 + 序列化）
│
├── graph_storage/                 # 📊 图存储（设计期离线工具）
│   ├── graph.py                   #   RelationshipGraph（邻接表 + 边字典）
│   ├── graph_models.py            #   NPC / Edge dataclass
│   ├── persistence.py             #   JSON 序列化
│   └── api.py                     #   对外便捷接口
│
├── server/                        # 🌐 FastAPI 服务器
│   ├── main.py                    #   应用入口（create_app + uvicorn）
│   ├── state.py                   #   全局 GameSession 单例
│   ├── middleware.py              #   CORS + 全局异常捕获
│   └── routes/
│       ├── health.py              #   GET /health
│       ├── game.py                #   REST 端点（11 个）
│       └── ws_game.py             #   WebSocket 端点 /ws/game
│
├── engine/                        # ⚙️ 游戏逻辑引擎
│   ├── game_session.py            #   GameSession — 5 模块容器
│   ├── time/                      #   时间系统（天/时段/周推进 + 9 周阶段）
│   ├── resource/                  #   资源系统（香火/神力/阴德/阳德）
│   ├── event/                     #   事件系统（触发 + 结算 + 命运硬币）
│   ├── bond/                      #   缘线系统（运行时关系账本）
│   └── karma/                     #   业线系统（节点推进 + 进度追踪）
│
├── data/                          # 📁 配置数据加载
│   ├── npc_loader.py              #   CSV → NpcStatic + 初始位置
│   └── __init__.py                #   导出 load_npcs
│
├── storage/                       # 💾 存档持久化
│   ├── interface.py               #   SaveStorage 抽象接口
│   └── json_storage.py            #   JSON 全量快照（3 手动档 + 1 自动档）
│
└── tests/                         # 🧪 测试（308 个）
    ├── test_npc_agent.py          #   NPC Agent（48）
    ├── test_graph.py              #   图存储（34）
    ├── test_time.py               #   时间系统（39）
    ├── test_resource.py           #   资源系统（46）
    ├── test_event.py              #   事件系统（25）
    ├── test_bond.py               #   缘线系统（29）
    ├── test_karma.py              #   业线系统（27）
    └── test_storage.py            #   存档系统（12）
```

---

## 2. 模块职责

### 2.1 `models/` — 数据合同层

**一句话：前后端共享的数据结构定义。**

- 使用 **Pydantic v2**，自动生成 JSON Schema（FastAPI 自动渲染为 OpenAPI 文档）
- 包含所有枚举（AgentTier, Slot, Emotion, Location）和数据模型（三层 NPC 结构）
- 前端人员**直接看这个目录**就能知道 API 返回什么字段、什么类型、什么范围
- **不包含任何业务逻辑**，只有数据结构 + 校验规则

**关键模型：**

| 模型 | 说明 | 所属层 |
|------|------|--------|
| `Personality` | 五维性格 0~1 | 静态 |
| `FixedAttributes` | 四围属性 1~10 | 静态 |
| `NpcStatic` | NPC 不可变属性（姓名/年龄/背景/性格） | 静态 |
| `NpcDynamic` | 每时段可变状态（位置/情绪/精力/业线进度） | 动态 |
| `MemoryEntry` | 单条事件记忆 | 记忆 |
| `Impression` | 对另一个 NPC 的情感印象 | 记忆 |
| `AgentMemory` | 完整记忆存储（事件链+关键记忆+印象） | 记忆 |
| `NpcSnapshot` | 三层聚合快照（给前端） | 视图 |
| `NpcListResponse` | 所有 NPC 快照列表 | 视图 |
| `ApiResponse` | 统一 REST 响应外壳（success + data + error） | 通用 |
| `GameStateResponse` | 游戏完整状态（资源 + NPC 列表） | 视图 |

### 2.2 `ai/npc_agent/` — NPC Agent 模块

**一句话：每个 NPC 拥有独立的 LLM 代理实例。**

**设计原则：**
- 每个 NPC **独立实例**：独立的记忆、独立的 LLM 对话历史、独立的性格
- 三层分离：static（不可变）→ dynamic（每时段变）→ memory（持续积累）
- **LLM 可选**：LLM 不可用时自动降级为规则兜底，游戏不中断
- 可序列化：支持存档读档
- **缘线注入**：NPC 的关系网络自动注入 system prompt

**文件依赖链：**

```
models/npc.py          ← 基础
  ↓
static.py             ← 构建 NPC 不可变属性
dynamic.py            ← 管理可变状态 + delta 追踪
memory.py             ← 管理记忆（事件链 + 印象 + 溢出）
templates.py          ← 性格 + 缘线 → system_prompt 模板
  ↓
agent.py              ← 组装以上四者 + LLM 调用
  ↓
manager.py            ← 管理所有 Agent 实例
```

**详细文档：** `ai/npc_agent/README.md`

### 2.3 `ai/llm_client/` — LLM 客户端

**一句话：负载均衡 + 并发控制 + 故障转移。**

- `LoadBalancedClient`：轮询端点 + 每端点 Semaphore 并发限流
- 故障转移：一个端点失败自动尝试下一个
- 全局降级：所有端点不可用 → 返回 None → 触发规则兜底
- 支持 `default_extra_body` 注入（Qwen3 需关闭 thinking 模式）

### 2.4 `graph_storage/` — 图存储模块

**一句话：NPC 关系的离线管理工具。**

- 用于**设计期**创建和验证 NPC 关系图数据
- `RelationshipGraph`：邻接表 + 边字典双索引，有向图
- 边属性：type（红/金/蓝/灰/黑）、strength（0-100）、glow（0-100）
- 在架构决策中，此模块**不直接参与游戏运行时**——运行时的缘线由 `engine/bond/` 负责

### 2.5 `server/` — FastAPI 服务器

**一句话：对外暴露 REST + WebSocket 接口。**

**启动方式：** `uvicorn src.backend.server.main:app --reload --host 0.0.0.0 --port 8000`

| 层 | 协议 | 用途 |
|----|------|------|
| REST | HTTP | 一次性操作：创建游戏、查询状态、对话、存档 |
| WebSocket | WS | 持续连接：时间推进结算、事件流、NPC 行动推送 |

**REST 端点：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/new-game` | POST | 创建新游戏，加载 14 个 NPC |
| `/state` | GET | 查询当前游戏完整状态 |
| `/chat/{npc_id}` | POST | 与指定 NPC 对话（LLM 驱动） |
| `/save/{slot}` | POST | 保存到槽位（0=自动, 1-3=手动） |
| `/load/{slot}` | POST | 从槽位加载 |
| `/saves` | GET | 列出所有存档 |
| `/saves/{slot}` | DELETE | 删除存档 |

**WebSocket 端点：**

| 端点 | 说明 |
|------|------|
| `/ws/game` | 游戏主通道 |

**WS 消息类型（客户端→服务端）：**

| type | 说明 |
|------|------|
| `new_game` | 创建新游戏 |
| `advance_time` | 推进一个时段（触发完整结算链） |
| `chat` | NPC 对话 |
| `get_state` | 查询状态 |
| `save_game` | 存档 |
| `load_game` | 读档 |

**WS 消息类型（服务端→客户端）：**

| type | 说明 |
|------|------|
| `time_advanced` | 时间已推进（day/slot/week/phase） |
| `event_triggered` | 事件触发及其结果 |
| `npc_action` | 单个 NPC 的行为决策（流式返回） |
| `settlement_complete` | 结算完毕（汇总资源状态） |
| `npc_response` | NPC 对话回应 |
| `game_state` | 完整游戏状态 |
| `game_created` / `game_loaded` / `game_saved` | 存档操作确认 |

**状态管理：** `server/state.py` 持有全局 `GameSession` 单例，包含所有 5 个引擎模块。后期可替换为会话池。

### 2.6 `engine/` — 游戏逻辑引擎

**一句话：所有游戏规则的实现。**

| 子系统 | 职责 | 关键逻辑 |
|--------|------|----------|
| `game_session.py` | 5 模块容器 + to_dict/from_dict | 存档序列化的入口 |
| `time/` | 天/时段/周推进 | 60天, 3时段/天, 9周阶段, 终局检测 |
| `resource/` | 资源增减 | 香火每日-1, 神力回满, 阴德/阳德只增不减, 周结算公式 |
| `event/` | 事件触发与结算 | CSV 事件池 + 权重概率 + 结果选择 + 多模块执行 |
| `bond/` | 缘线变化 | 有向关系账本 + Delta 解析 + LLM prompt 注入 |
| `karma/` | 业线推进 | 节点定义 + 进度追踪 + 节点自动切换 |

**引擎与 Agent 的关系：**

```
时间推进（time/）
  → 事件匹配（event/）
     → 事件执行：resource + bond + karma + agent.remember()
  → agent.think() — 决定下时段行为（S/A 级 LLM, B/C 级规则兜底）
  → 流式返回所有结果给 Godot
```

### 2.7 `data/` — 配置数据加载

**一句话：从 `design/data/` CSV 加载蓝图数据。**

- `load_npcs()` → `list[NpcStatic]`（14 个 NPC 完整属性）
- `load_npc_initial_dynamic()` → `{npc_id: location}`（初始位置）
- CSV 是蓝图（启动加载，只读），GameSession 是实例（运行时变化）

### 2.8 `storage/` — 存档系统

**一句话：游戏状态的持久化。**

- 抽象接口 `SaveStorage` → 当前实现 `JsonStorage`（全量 JSON 快照）
- 3 手动档 + 1 自动档
- 存档内容 = `GameSession.to_dict()` 的完整序列化快照
- 存档文件位于 `saves/` 目录

---

## 3. 核心概念

| 概念 | 在代码中的位置 | 说明 |
|------|---------------|------|
| **NPC 三层结构** | `models/npc.py` + `ai/npc_agent/` | static(不变) + dynamic(变) + memory(累积) |
| **缘线** | `engine/bond/` | NPC 之间的人际关系（红/金/蓝/灰/黑, 0-100），有向 |
| **业线** | `engine/karma/` | NPC 的人生目标（5-10 节点, 0-100% 进度） |
| **命运硬币** | `engine/event/` | 事件结算的随机判定机制（CSV 数据驱动） |
| **Agent 分级** | `models/npc.py` AgentTier | S 完整Agent / A 半完整 / B 规则驱动 / C 轻量 |
| **GameSession** | `engine/game_session.py` | 5 模块运行时容器，存档的序列化单元 |
| **增量同步** | `engine/event/` + WS 流式 | 时段结算后逐条推送变化，而非全量 |

---

## 4. 数据流

### 4.1 新游戏初始化

```
POST /new-game 或 WS new_game
  → data/ 加载 CSV 配置（14 NPC）
  → 创建 BondManager（注入初始缘线）
  → 创建 KarmaManager（加载节点定义）
  → 为每个 NPC 创建 NpcAgent（static + dynamic + bond + name_map）
  → 创建 GameSession（time + resource + agents + bonds + karma）
  → 返回全量初始状态
```

### 4.2 时段推进（WebSocket /ws/game）

```
WS → advance_time
  → time.advance()                                    # 推进时段，返回 TimeAdvanceResult
  → if is_new_day: resource.apply_daily()             # 香火 -1, 神力回满
  → event.match_events(day, slot, week, locations)    # 按时间/地点/权重匹配
  → event.execute_events(matched, resource, agents)   # 执行结算
     → resource.apply_delta()                         #   资源变化
     → agent_manager 更新 NPC 状态                   #   NPC 变化
     → agent.remember()                               #   记忆写入
     → bonds.apply_delta()                            #   缘线变化
     → karma.apply_delta()                            #   业线推进
  → WS 流式推送：time_advanced → event_triggered → npc_action × N
  → WS settlement_complete                            # 结算完毕
```

### 4.3 存档

```
POST /save/1 或 WS save_game
  → session.to_dict() — 5 模块全量序列化
  → storage/JsonStorage.save() — 写入 saves/slot_1.json
```

### 4.4 读档

```
POST /load/1 或 WS load_game
  → storage/JsonStorage.load() — 读取 JSON
  → GameSession.from_dict() — 重建 5 模块
  → 重新注入 LLM 客户端 + name_map + bond_manager
  → 返回恢复后的完整状态
```

---

## 5. 关键设计决策

| # | 决策 | 结论 |
|----|------|------|
| D1 | 技术路线 | Godot(表现层) + Python(逻辑层) |
| D2 | 框架 | FastAPI (REST + WebSocket) |
| D3 | 通信格式 | JSON，统一 Message / ApiResponse 外壳 |
| D4 | 数据粒度 | 初始化全量，结算流式推送 |
| D5 | LLM 调用 | 每 NPC 独立实例 + 异步并发 + 规则兜底 |
| D6 | 记忆存储 | 内存 + JSON 序列化 |
| D7 | 存档 | 全量 JSON 快照，GameSession 容器，抽象接口预留扩展 |
| D8 | 配置 vs 状态 | CSV 是蓝图（`design/data/`，只读），GameSession 是实例（运行时变化） |
| D9 | 容错 | 任何单一失败不影响游戏整体（LLM 超时→规则兜底） |
| D10 | NPC 行动 | S/A 级 LLM 决策，B/C 级规则兜底 |
| D11 | 服务器状态管理 | 全局 GameSession 单例，Demo 阶段只支持单局 |
| D12 | 事件触发 | CSV 事件池 + 权重概率（非 LLM 自由生成） |
| D13 | 缘线运行时 | engine/bond/ 独立管理，不依赖 graph_storage |
| D14 | LLM 关系注入 | BondManager 数据自动注入 system prompt |

---

## 6. 命名规范

| 类别 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `npc_agent.py`, `time_state.py` |
| 类名 | PascalCase | `NpcAgent`, `AgentManager`, `TimeState` |
| 函数/方法 | snake_case | `build_system_prompt()`, `apply_delta()` |
| 私有方法 | `_` 前缀 | `_default_action()`, `_compute_result()` |
| 常量 | UPPER_SNAKE | `MAX_EVENT_CHAIN`, `DEFAULT_INCENSE` |
| NPC ID | snake_case 英文 | `lin_chaoyin`, `chen_yuanzhou` |
| 事件 ID | 语义前缀 | `w1_chaoyin_study`, `intro_heaven_notice` |
| 字段名 | snake_case | `karma_main_progress`, `divine_power_max` |
| 枚举值 | 小写英文 | `morning`, `school`, `happy` |

---

## 7. 外部依赖

当前 Python 环境：**Conda base, Python 3.8.5**

| 包 | 版本 | 用途 | 状态 |
|----|------|------|------|
| `pydantic` | 2.10.6 | 数据模型 | ✅ |
| `pytest` | 8.3.5 | 测试框架 | ✅ |
| `fastapi` | 0.124.4 | Web 框架（REST + WS） | ✅ |
| `uvicorn` | 0.33.0 | ASGI 服务器 | ✅ |
| `httpx` | 0.28.1 | 异步 HTTP 客户端（LLM API） | ✅ |
| `websockets` | ≥12.0 | WebSocket 客户端（测试用） | ✅ |

### 7.1 LLM 服务连接

| 配置项 | 值 |
|--------|-----|
| 主机 | `172.21.125.241` |
| 端口 | `8080` |
| API 路径 | `/v1/chat/completions` |
| 模型 | Qwen3-14B Q4_K_M |
| 特殊参数 | `chat_template_kwargs: {enable_thinking: false}` |

---

## 8. 开发节奏

### ✅ 全部完成

| 模块 | 测试 | 说明 |
|------|------|------|
| `models/` | — | 数据合同层 |
| `ai/npc_agent/` | 48 | NPC Agent |
| `ai/llm_client/` | — | LLM 客户端 |
| `graph_storage/` | 34 | 图存储（设计期） |
| `server/` | — | REST + WebSocket（11 端点） |
| `engine/time/` | 39 | 时间系统 |
| `engine/resource/` | 46 | 资源系统 |
| `engine/event/` | 25 | 事件系统 |
| `engine/bond/` | 29 | 缘线系统 |
| `engine/karma/` | 27 | 业线系统 |
| `data/` | — | CSV 配置加载 |
| `storage/` | 12 | 存档系统 |

```
308 tests passed, 0 failures
12 模块全部就绪
```
