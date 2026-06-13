# 后端架构文档

> 文件位置：`src/backend/ARCHITECTURE.md`  
> 更新日期：2026-06-13  
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
│   └── npc.py                     #   Pydantic 模型：NPC 三层结构、枚举
│
├── ai/                            # 🧠 AI 子系统
│   └── npc_agent/
│       ├── README.md              #   模块完整文档
│       ├── static.py              #   静态属性（不可变）+ Demo NPC 预设
│       ├── dynamic.py             #   动态状态（可变）+ delta 追踪
│       ├── memory.py              #   记忆系统（事件链 + 印象 + 溢出）
│       ├── templates.py           #   System prompt 模板生成
│       ├── agent.py               #   NpcAgent 主类（组装三层 + think/respond）
│       └── manager.py             #   AgentManager（批量管理）
│
├── graph_storage/                 # 📊 图存储模块（离线工具）
│   ├── graph.py                   #   RelationshipGraph（邻接表 + 边字典）
│   ├── graph_models.py            #   NPC / Edge dataclass
│   ├── persistence.py             #   JSON 序列化
│   ├── api.py                     #   对外便捷接口
│   └── ARCHITECTURE.md            #   图存储架构文档
│
├── server/                        # 🌐 FastAPI 服务器（待实现）
│   ├── main.py                    #   应用启动入口
│   ├── routes/                    #   REST 路由
│   ├── websocket/                 #   WebSocket 处理
│   └── middleware.py              #   全局异常处理
│
├── engine/                        # ⚙️ 游戏逻辑引擎（待实现）
│   ├── time/                      #   时间系统（天/时段/周推进）
│   ├── event/                     #   事件系统（触发 + 结算 + 命运硬币）
│   ├── resource/                  #   资源系统（香火/神力/阴德/阳德）
│   ├── bond/                      #   缘线系统（关系颜色/强度/活跃度变化）
│   └── karma/                     #   业线系统（节点推进 + 跳关 + 结局判定）
│
├── data/                          # 📁 配置数据加载（待实现）
│
├── storage/                       # 💾 存档持久化（待实现）
│   ├── interface.py               #   抽象接口
│   └── json_storage.py            #   JSON 全量快照实现
│
└── tests/                         # 🧪 测试
    ├── test_graph.py              #   图存储 34 个测试
    └── test_npc_agent.py          #   NPC Agent 48 个测试
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

### 2.2 `ai/npc_agent/` — NPC Agent 模块

**一句话：每个 NPC 拥有独立的 LLM 代理实例。**

**设计原则：**
- 每个 NPC **独立实例**：独立的记忆、独立的 LLM 对话历史、独立的性格
- 三层分离：static（不可变）→ dynamic（每时段变）→ memory（持续积累）
- **LLM 可选**：LLM 不可用时自动降级为规则兜底，游戏不中断
- 可序列化：支持存档读档

**文件依赖链：**

```
models/npc.py          ← 基础
  ↓
static.py             ← 构建 NPC 不可变属性
dynamic.py            ← 管理可变状态 + delta 追踪
memory.py             ← 管理记忆（事件链 + 印象 + 溢出）
templates.py          ← 性格 → system_prompt 模板
  ↓
agent.py              ← 组装以上四者 + LLM 调用
  ↓
manager.py            ← 管理所有 Agent 实例
```

**详细文档：** `ai/npc_agent/README.md`

### 2.3 `graph_storage/` — 图存储模块

**一句话：NPC 关系的离线管理工具。**

- 用于**设计期**创建和验证 NPC 关系图数据
- `RelationshipGraph`：邻接表 + 边字典双索引，有向图
- 边属性：type（红/金/蓝/灰/黑）、strength（0-100）、glow（0-100）
- JSON 序列化支持
- 在架构决策中，此模块**不直接参与游戏运行时**——游戏运行时的缘线管理由 `engine/bond/` 负责

### 2.4 `server/` — FastAPI 服务器（待实现）

**一句话：对外暴露 REST + WebSocket 接口。**

| 层 | 协议 | 用途 |
|----|------|------|
| REST | HTTP | 简单同步操作：`/health`, `/new-game`, `/state`, `/save`, `/load` |
| WebSocket | WS | 双向实时通信：时间推进结算、LLM 流式文本、关键警报 |

**核心端点（规划）：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/new-game` | POST | 创建新游戏，返回全量初始状态 |
| `/state` | GET | 查询当前完整状态 |
| `/save/{slot}` | POST | 保存到指定槽位 |
| `/load/{slot}` | POST | 从指定槽位加载 |
| `/saves` | GET | 列出所有存档 |
| `/saves/{slot}` | DELETE | 删除存档 |
| `/ws/game` | WS | 游戏主通信通道 |

**统一响应格式：**

```python
class ApiResponse(BaseModel):
    success: bool
    data: Any | None = None
    error: str | None = None
    changed_fields: list[str] | None = None  # 增量模式
```

**统一 WebSocket 消息格式：**

```python
class Message(BaseModel):
    type: str            # "advance_time" | "settlement" | "npc_dialogue" | "alert" | "llm_stream"
    payload: dict
    timestamp: float
    request_id: str | None = None
```

### 2.5 `engine/` — 游戏逻辑引擎（待实现）

**一句话：所有游戏规则的实现。**

每个子模块的职责：

| 子系统 | 职责 | 关键逻辑 |
|--------|------|----------|
| `time/` | 天/时段/周推进 | 60天, 3时段/天, 9周阶段 |
| `event/` | 事件触发与结算 | 责任链模式, 命运硬币, 结果分发 |
| `resource/` | 资源增减 | 香火每日-1, 神力消耗, 阴德/阳德只增不减 |
| `bond/` | 缘线变化 | 关系颜色/强度/活跃度变更 |
| `karma/` | 业线推进 | 节点触发, 跳关, 结局判定 |

**引擎与 Agent 的关系：**

```
事件引擎（engine/event/）
  │ 决定：什么事发生了
  │ 决定：资源怎么变、业线怎么推进
  │
  └──→ 调用 Agent.remember() — 记录事件记忆
  └──→ 调用 Agent.think()    — 决定下时段行为（LLM 或规则）
```

### 2.6 `storage/` — 存档系统（待实现）

**一句话：游戏状态的持久化。**

- 抽象接口 `SaveStorage` → 当前实现 `JsonStorage`（全量 JSON 快照）
- 3 手动档 + 1 自动档
- 存档内容 = GameSession 的完整序列化快照（所有 NPC 状态 + 动态 + 记忆 + 世界状态）

---

## 3. 核心概念

| 概念 | 在代码中的位置 | 说明 |
|------|---------------|------|
| **NPC 三层结构** | `models/npc.py` + `ai/npc_agent/` | static(不变) + dynamic(变) + memory(累积) |
| **缘线** | `graph_storage/` → 未来 `engine/bond/` | NPC 之间的人际关系（红/金/蓝/灰/黑, 0-100） |
| **业线** | 未来 `engine/karma/` | NPC 的人生目标（5-10 节点, 0-100% 进度） |
| **命运硬币** | 未来 `engine/event/` | 事件结算的随机判定机制 |
| **Agent 分级** | `models/npc.py` AgentTier | S 完整Agent / A 半完整 / B 规则驱动 / C 轻量 |
| **GameSession** | 未来 `engine/` | 一局游戏的完整运行时状态（所有引擎模块共享） |
| **增量同步** | `ai/npc_agent/dynamic.py` DynamicDelta | 时段结算后只返回变化的部分给前端 |

---

## 4. 数据流

### 4.1 新游戏初始化

```
POST /new-game
  → data/ 加载 CSV 配置（静态）
  → 为每个 NPC 创建 NpcAgent（static + dynamic + 空 memory）
  → 加载初始缘线到 RelationshipGraph
  → 创建 GameSession
  → 返回 NpcListResponse（全量初始状态）
```

### 4.2 时段推进

```
WS /ws/game → advance_time
  → engine/time/ 推进时间
  → engine/event/ 检查触发条件 → 结算事件（命运硬币）
     → engine/resource/ 更新资源
     → engine/bond/ 更新缘线
     → engine/karma/ 推进业线
     → agent.remember() 记录记忆
  → agent.think() 决定下时段行为（S/A 级并发 LLM, B/C 级规则）
  → 收集所有 delta → 返回增量结果给 Godot
```

### 4.3 存档

```
POST /save/{slot}
  → AgentManager.to_dict() — 所有 Agent 的快照
  → engine/ 各模块序列化
  → storage/JsonStorage.save() — 写入 JSON 文件
```

---

## 5. 关键设计决策

以下决策已在 `design/架构决策/框架与相关问题.md` 中详细记录，此处仅列要点：

| # | 决策 | 结论 |
|----|------|------|
| D1 | 技术路线 | Godot(表现层) + Python(逻辑层) |
| D2 | 框架 | FastAPI (REST + WebSocket) |
| D3 | 通信格式 | JSON，统一 Message / ApiResponse 外壳 |
| D4 | 数据粒度 | 初始化全量，结算增量 |
| D5 | LLM 调用 | 每 NPC 独立实例 + 异步并发 + 规则兜底 |
| D6 | 记忆存储 | 内存 + JSON 序列化，预留 SQLite 接口 |
| D7 | 存档 | 全量 JSON 快照，抽象接口预留扩展 |
| D8 | 配置 vs 状态 | CSV 是蓝图（启动加载，只读），GameSession 是实例（运行时变化） |
| D9 | 容错 | 任何单一失败不影响游戏整体（LLM 超时→规则兜底，Python 挂→Godot 提示） |
| D10 | NPC 行动 | LLM 决定 NPC 意图，规则引擎决定后果（待最终确认） |
| D11 | 服务器状态管理 | **单例内存**：`server/state.py` 持有全局 AgentManager，Demo 阶段只支持单局；后期替换为会话池 |

**待讨论问题（标记在框架文档 §2）：**
- Q1: LLM 决策范围 — NPC 意图 vs 游戏状态修改
- Q2: 业线结局判定时机 — 立即 vs 60 天终局

---

## 6. 命名规范

| 类别 | 规范 | 示例 |
|------|------|------|
| 文件名 | snake_case | `npc_agent.py`, `graph_storage/` |
| 类名 | PascalCase | `NpcAgent`, `AgentManager`, `MemoryStore` |
| 函数/方法 | snake_case | `build_system_prompt()`, `all_think()` |
| 私有方法 | `_` 前缀 | `_default_action()`, `_compact_event_chain()` |
| 常量 | UPPER_SNAKE | `MAX_EVENT_CHAIN`, `IMPORTANCE_THRESHOLD` |
| NPC ID | snake_case 英文 | `lin_chaoyin`, `chen_yuanzhou` |
| 事件 ID | `evt_` 前缀 | `evt_exam_001`, `evt_cult_meeting` |
| 字段名 | snake_case | `karma_main_progress`, `memory_overflow_count` |
| 枚举值 | 小写英文 | `morning`, `school`, `happy` |

---

## 7. 外部依赖

当前 Python 环境：**Conda base, Python 3.8.5**

| 包 | 版本 | 用途 | 状态 |
|----|------|------|------|
| `pydantic` | 2.10.6 | 数据模型 | ✅ 已安装 |
| `pytest` | 8.3.5 | 测试框架 | ✅ 已安装 |
| `fastapi` | ≥0.115 | Web 框架 | ⏳ 待安装 |
| `uvicorn` | ≥0.30 | ASGI 服务器 | ⏳ 待安装 |
| `websockets` | ≥12.0 | WebSocket 支持 | ⏳ 待安装 |
| `httpx` | ≥0.27 | 异步 HTTP 客户端（LLM API） | ⏳ 待安装 |
| `python-dotenv` | ≥1.0 | 环境变量管理 | ⏳ 待安装 |

**环境配置文件已在项目根目录：**
- `environment.yml` — Conda 环境（推荐，Python 3.10）
- `requirements.txt` — Pip 依赖清单

---

## 8. 开发节奏

### 已完成

| 阶段 | 内容 | 测试 |
|------|------|------|
| ✅ 数据模型 | `models/npc.py` — Pydantic 三层结构 + 枚举 | — |
| ✅ NPC Agent | `ai/npc_agent/` — 6 文件 + README | 48 个测试 |
| ✅ 图存储 | `graph_storage/` — RelationshipGraph + 持久化 | 34 个测试 |

### 待开发（按优先级）

| 优先级 | 模块 | 产出 |
|--------|------|------|
| **P0** | `server/` — FastAPI 入口 + health 端点 | 服务器可启动 |
| **P0** | `server/routes/game.py` — `/new-game` 端点 | Demo 可跑通 |
| **P1** | `data/` — CSV 配置加载 | 从数据表初始化 |
| **P1** | `engine/time/` — 时间系统 | 天/时段/周推进 |
| **P1** | `engine/resource/` — 资源系统 | 香火/神力/阴德/阳德 |
| **P2** | `engine/event/` — 事件系统 | 触发+结算+命运硬币 |
| **P2** | `engine/bond/` — 缘线系统 | 关系变化 |
| **P2** | `engine/karma/` — 业线系统 | 节点推进+跳关 |
| **P3** | `storage/` — 存档系统 | 存读档 |
| **P3** | `server/websocket/` — WebSocket | 实时通信 |
| **P4** | `ai/llm_client/` — LLM 接入 | DeepSeek / 本地模型 |
