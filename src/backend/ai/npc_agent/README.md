# NPC Agent 模块文档

> 模块路径：`src/backend/ai/npc_agent/`  
> 更新日期：2026-06-13  
> 状态：核心骨架完成，LLM 客户端为桩实现

---

## 目录

1. [概述](#1-概述)
2. [三层架构](#2-三层架构)
3. [模块文件说明](#3-模块文件说明)
4. [数据模型](#4-数据模型)
5. [核心流程](#5-核心流程)
6. [API 参考](#6-api-参考)
7. [使用示例](#7-使用示例)
8. [LLM 集成](#8-llm-集成)
9. [扩展指南](#9-扩展指南)
10. [常量与配置](#10-常量与配置)

---

## 1. 概述

NPC Agent 模块是《命运的织线》中 **NPC 人工智能的核心**。每个 NPC 拥有独立的 Agent 实例，包含三层数据结构（静态/动态/记忆），并通过 LLM 进行自主行为决策和对话生成。

### 设计原则

| 原则 | 说明 |
|------|------|
| **独立实例** | 每个 NPC 拥有独立的 Agent、独立的记忆、独立的 LLM 对话历史 |
| **三层分离** | 静态属性（不可变）、动态状态（每时段变）、记忆（持续积累）严格分离 |
| **LLM 可选** | LLM 不可用时自动降级为规则兜底，游戏不中断 |
| **可序列化** | 所有状态可完整序列化/反序列化，支持存档读档 |

### 文件结构

```
ai/npc_agent/
├── __init__.py      # 模块入口
├── static.py        # 静态属性（不可变层）
├── dynamic.py       # 动态状态（可变层 + delta 追踪）
├── memory.py        # 记忆系统（事件链 + 印象 + 溢出处理）
├── templates.py     # System Prompt 模板生成
├── agent.py         # NpcAgent 主类（组装三层）
├── manager.py       # AgentManager（批量管理）
└── README.md        # 本文档
```

**外部依赖：** `src/backend/models/npc.py`（Pydantic 数据模型）

---

## 2. 三层架构

```
┌─────────────────────────────────────────────┐
│               NpcAgent                       │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  static: NpcStatic (不可变)           │   │
│  │  ├─ 姓名、年龄、职业                  │   │
│  │  ├─ 背景故事                         │   │
│  │  ├─ 固定属性 (心智/信仰/体魄/魅力)     │   │
│  │  ├─ 性格模型 (五维 0~1)               │   │
│  │  └─ 核心愿望                         │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  dynamic: DynamicState (每时段更新)    │   │
│  │  ├─ 当前位置 (12 个地点)              │   │
│  │  ├─ 幸福度 (0~100)                   │   │
│  │  ├─ 精力 (0~100)                     │   │
│  │  ├─ 情绪                              │   │
│  │  ├─ 当前目标                         │   │
│  │  └─ 业线进度 (%)                     │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  memory: MemoryStore (持续积累)        │   │
│  │  ├─ 事件链 (最多 50 条)               │   │
│  │  ├─ 关键记忆 (Top 30，按重要性排序)    │   │
│  │  ├─ 情感印象 (好感度/信任度/标签)      │   │
│  │  └─ 溢出摘要 (自动精简历史)            │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  llm: LLMClient (独立对话上下文)       │   │
│  │  ├─ chat() / chat_stream()           │   │
│  │  ├─ 对话历史管理                     │   │
│  │  └─ 降级兜底                         │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## 3. 模块文件说明

### 3.1 `static.py` — 静态属性

**职责：** 定义 NPC 不可变属性，提供构建函数和 Demo NPC 预设。

| 函数 | 签名 | 说明 |
|------|------|------|
| `build_static(data)` | `dict → NpcStatic` | 从配置字典构建 NpcStatic |
| `demo_lin_chaoyin()` | `() → NpcStatic` | 林潮音的静态数据（17岁，灵力少女，S 级） |
| `demo_chen_yuanzhou()` | `() → NpcStatic` | 陈远舟的静态数据（18岁，离岛梦想者，S 级） |
| `demo_npcs()` | `() → list[NpcStatic]` | 获取所有 Demo NPC |

**扩展方式：** 后期从 CSV `NPC基础表.csv` 批量加载，替换硬编码预设。

### 3.2 `dynamic.py` — 动态状态

**职责：** 管理 NPC 的可变状态，追踪每次变更（delta），支持增量同步给前端。

**核心类：`DynamicState`**

| 方法 | 说明 |
|------|------|
| `current` | 返回当前 `NpcDynamic` |
| `deltas` | 返回并清空变更记录列表 |
| `snapshot()` | 返回状态摘要字典（给 LLM 用） |
| `set_location(id, loc, reason)` | 变更位置 |
| `set_happiness(id, delta, reason)` | 增减幸福度（自动钳制 0~100） |
| `set_energy(id, delta, reason)` | 增减精力 |
| `set_emotion(id, emotion, reason)` | 变更情绪 |
| `set_goal(id, goal, reason)` | 变更当前目标 |
| `set_karma_main(id, progress, reason)` | 更新主业线进度 |

**辅助类：`DynamicDelta`** — 单次变更记录，包含 `npc_id`, `field`, `old_value`, `new_value`, `reason`。

```python
# 变更追踪示例
state.set_happiness("lin_chaoyin", delta=-10, reason="evt_betrayal_001")
state.set_location("lin_chaoyin", Location.BEACH, reason="决定去海边散步")
deltas = state.deltas
# → [
#     DynamicDelta("lin_chaoyin", "happiness", 60, 50, "evt_betrayal_001"),
#     DynamicDelta("lin_chaoyin", "location", "residence", "beach", "决定去海边散步"),
#   ]
```

### 3.3 `memory.py` — 记忆系统

**职责：** 管理 NPC 的记忆存储，包括事件记忆、关键记忆排名、情感印象管理、溢出自动精简。

**核心类：`MemoryStore`**

**查询方法：**

| 方法 | 返回 | 说明 |
|------|------|------|
| `event_count` | `int` | 事件链总条数 |
| `key_count` | `int` | 关键记忆条数 |
| `overflow_count` | `int` | 溢出次数（调试用） |
| `recent_events(n=10)` | `list[MemoryEntry]` | 最近 n 条事件 |
| `top_key_memories(n=5)` | `list[MemoryEntry]` | 最重要的 n 条关键记忆 |
| `get_impression(npc_id)` | `Impression \| None` | 对某 NPC 的印象 |
| `all_impressions()` | `dict[str, Impression]` | 所有印象 |
| `context_for_llm(max_events=10)` | `str` | LLM 可用的记忆上下文文本 |

**写入方法：**

| 方法 | 签名 | 说明 |
|------|------|------|
| `remember()` | `(day, slot, description, importance, emotion, event_id) → MemoryEntry` | 记录事件记忆，自动判定是否需要加入关键记忆 |
| `set_impression()` | `(npc_id, affinity, trust, label) → Impression` | 直接设置印象 |
| `update_impression()` | `(npc_id, affinity_delta, trust_delta, label) → Impression` | 增量更新印象 |

**溢出处理机制（对应策划案 §8.6.6）：**

```
事件链 > 50 条
  → 按重要性排名保留 Top 10
  → 按时间保留最近 20 条
  → 去重合并（上限约 30 条）
  → 被移除的事件合并为摘要文本
  → overflow_count += 1
```

**配置常量：**

| 常量 | 值 | 说明 |
|------|----|------|
| `MAX_EVENT_CHAIN` | 50 | 事件链上限 |
| `MAX_KEY_MEMORIES` | 30 | 关键记忆上限 |
| `IMPORTANCE_THRESHOLD` | 7 | 重要性 ≥ 此值自动进入关键记忆 |

### 3.4 `templates.py` — Prompt 模板

**职责：** 根据 NPC 性格生成个性化的 `system_prompt`，确保每个 NPC 从自己的视角看世界。

**性格 → 自然语言映射：**

| 维度 | 高（≥0.7） | 中（0.3-0.7） | 低（≤0.3） |
|------|-----------|---------------|------------|
| 善良 | 非常善良，优先考虑他人 | 心地善良 | 冷漠 |
| 激进 | 性格激进，容易爆发 | — | 性格温和 |
| 感性 | 非常感性，受情绪影响 | — | 依赖逻辑和事实 |
| 理性 | 非常理性，分析利弊 | — | 凭直觉和冲动 |
| 好奇心 | 好奇心旺盛 | — | 安于现状 |

**两种 Prompt：**

| 函数 | 用途 | 区别 |
|------|------|------|
| `build_system_prompt()` | 对话回应 | 末尾：请以{name}的身份回应 |
| `build_decision_prompt()` | 行为决策 | 末尾：只输出一行行动描述（15字以内） |

**行为规则（所有 NPC 共享）：**

1. 只做符合性格和身份的事
2. 只基于记忆和当前处境做决定，不用上帝视角
3. 用中文回应，语气符合当前情绪
4. 不意识到自己是游戏角色
5. 不确定时给出最自然的反应

### 3.5 `agent.py` — NpcAgent 主类

**职责：** 组装静态层 + 动态层 + 记忆层 + LLM 客户端，提供统一的 NPC 交互接口。

**构造函数：**

```python
NpcAgent(
    static: NpcStatic,                    # 必填：静态属性
    dynamic: DynamicState | None = None,  # 可选：动态状态（默认创建）
    memory: MemoryStore | None = None,    # 可选：记忆存储（默认创建）
    llm: LLMClient | None = None,         # 可选：LLM 客户端（默认桩）
)
```

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `npc_id` | `str` | NPC 唯一标识 |
| `name` | `str` | 中文名 |
| `tier` | `AgentTier` | Agent 等级 |
| `location` | `Location` | 当前位置 |
| `emotion` | `Emotion` | 当前情绪 |

**核心方法：**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `think(day, slot)` | `str` | NPC 行为决策（异步，走 LLM 或规则兜底） |
| `respond(context, speaker_name)` | `str` | NPC 对话回应（异步） |
| `remember(day, slot, description, importance, emotion)` | — | 记录一条记忆 |
| `set_location(location, reason)` | — | 变更位置 |
| `set_happiness(delta, reason)` | — | 增减幸福度 |
| `set_emotion(emotion, reason)` | — | 变更情绪 |
| `snapshot()` | `NpcSnapshot` | 生成当前快照（给前端） |
| `to_dict()` | `dict` | 序列化（存档用） |
| `from_dict(data, static)` | `NpcAgent` | 从存档反序列化（类方法） |

**默认行为规则（LLM 不可用时）：**

| 时段 | 默认行动 |
|------|----------|
| 早晨 | "在{地点}开始新的一天。" |
| 中午 | "在{地点}度过午后时光。" |
| 夜晚 | "在{地点}休息，为明天做准备。" |

**默认对话：**
- 感性 ≤ 0.3 → "……（沉默）"
- 其他 → "嗯。"

### 3.6 `manager.py` — Agent 管理器

**职责：** 管理所有 NPC Agent 实例的生命周期。

**创建方法：**

| 方法 | 说明 |
|------|------|
| `add(agent)` | 添加一个已创建的 Agent |
| `add_from_static(static)` | 从静态数据创建并注册 |
| `init_from_demo()` | 加载 Demo NPC（林潮音 + 陈远舟） |
| `init_from_statics(statics)` | 从静态数据列表批量创建 |

**查询方法：**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `get(npc_id)` | `NpcAgent \| None` | 按 ID 获取 |
| `list_all()` | `list[NpcAgent]` | 获取全部 |
| `list_by_tier(tier)` | `list[NpcAgent]` | 按等级筛选 |
| `list_at_location(loc)` | `list[NpcAgent]` | 按地点筛选 |
| `count` | `int` | Agent 总数 |
| `npc_ids` | `list[str]` | 所有 NPC ID |

**批量操作：**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `all_think(day, slot)` | `dict[str, str]` | S/A 级并发 LLM 调用，B/C 级规则兜底；异常自动降级 |
| `all_remember(day, slot, descriptions, importance)` | — | 批量记录记忆 |

**前端接口：**

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `snapshot(npc_id)` | `NpcSnapshot \| None` | 单个 NPC 完整快照 |
| `all_snapshots()` | `NpcListResponse` | 所有 NPC 快照列表 |

**序列化：**

| 方法 | 说明 |
|------|------|
| `to_dict()` | 序列化所有 Agent |
| `from_dict(data, static_map)` | 从存档反序列化（类方法） |

---

## 4. 数据模型

所有数据结构定义在 `src/backend/models/npc.py`，使用 Pydantic，自动生成 JSON Schema。

### 4.1 枚举类型

| 枚举 | 值 | 来源 |
|------|----|------|
| `AgentTier` | S, A, B, C | 策划案 §8.7.2 |
| `Slot` | morning, noon, night | 策划案 §4 |
| `Emotion` | happy, sad, angry, fearful, calm, excited, anxious, neutral | — |
| `Location` | mountain_forest, beach, school, clinic, shopping_street, bookstore, plaza, cafe, police_station, temple, residence, port | 策划案 §19.3 |

### 4.2 模型继承关系

```
BaseModel
├── Personality          # 五维性格 (0~1)
├── FixedAttributes      # 四围属性 (1~10)
├── NpcStatic            # 静态层
├── NpcDynamic           # 动态层
├── MemoryEntry          # 单条记忆
├── Impression           # 情感印象
├── AgentMemory          # 记忆层
├── NpcSnapshot          # 完整快照（给前端）
└── NpcListResponse      # 快照列表响应
```

### 4.3 数据约束

| 模型 | 字段 | 约束 |
|------|------|------|
| `Personality` | 全部 | 0.0 ~ 1.0，两位小数 |
| `FixedAttributes` | 全部 | 1 ~ 10 |
| `NpcStatic` | id | 字母/数字/下划线 |
| `NpcStatic` | age | 10 ~ 100 |
| `NpcDynamic` | happiness, energy | 0 ~ 100 |
| `NpcDynamic` | karma_main_progress | 0.0 ~ 100.0 |
| `AgentMemory` | event_chain | 最多 50 条 |
| `AgentMemory` | key_memories | 最多 30 条 |
| `MemoryEntry` | importance | 1 ~ 10 |
| `MemoryEntry` | day | 1 ~ 60 |
| `Impression` | affinity, trust | 0 ~ 100 |

---

## 5. 核心流程

### 5.1 游戏启动（新游戏）

```
FastAPI POST /new-game
  → AgentManager.init_from_statics(statics)    # 从 CSV 加载所有 NPC 静态数据
  → 为每个 NPC 创建 AgentManager.add_from_static()
     → 每个 Agent 内部创建默认 DynamicState
     → 每个 Agent 内部创建空 MemoryStore
  → AgentManager.all_snapshots()               # 返回全量初始状态给 Godot
```

### 5.2 时段推进（玩家点击"推进时间"）

```
Godot WebSocket → Python /advance-time
  → 事件引擎结算（确定性规则）
     → 根据事件结果更新 Agent 状态
        → agent.set_happiness(-10, reason="evt_001")
        → agent.set_emotion(Emotion.SAD)
        → agent.remember(day, slot, "和陈远舟吵架了", importance=8)
  → AgentManager.all_think(day, next_slot)
     → S/A 级：并发 LLM 调用，决定下时段行动
     → B/C 级：规则兜底
  → 返回增量结算结果（事件列表 + NPC 变化 + 缘线变化）
```

### 5.3 记忆生命周期

```
新游戏 ──→ 空记忆
   ↓
Day 1~10 ──→ 积累事件（event_chain 增长，关键记忆逐渐形成）
   ↓
Day 11+  ──→ event_chain > 50 → 触发溢出精简
   ↓          ↓
   保留 Top 10 + 最近 20    被移除的合并为 MemorySummary
   ↓
终局 ──→ 记忆写入存档
```

### 5.4 LLM 调用与兜底

```
agent.think(day, slot)
  │
  ├── 构建 system_prompt + decision_prompt
  │     ├── 性格描述（来自 static.personality）
  │     ├── 记忆上下文（来自 memory.context_for_llm()）
  │     └── 当前状态（位置、情绪、精力、幸福度）
  │
  ├── llm.chat(messages)          ← 异步 LLM 调用
  │     │
  │     ├── 成功返回行动描述      → 返回给引擎
  │     │
  │     └── 超时/异常/返回空      → _default_action(day, slot)
  │                                   → 按日常日程表返回
```

---

## 6. API 参考

### 6.1 NpcAgent

```python
from src.backend.ai.npc_agent.agent import NpcAgent
from src.backend.ai.npc_agent.static import demo_lin_chaoyin
from src.backend.models.npc import Location, Slot, Emotion

# 创建
agent = NpcAgent(static=demo_lin_chaoyin())

# 属性
agent.npc_id       # "lin_chaoyin"
agent.name         # "林潮音"
agent.tier         # AgentTier.S
agent.location     # Location.RESIDENCE
agent.emotion      # Emotion.NEUTRAL

# 行为
action = await agent.think(day=1, slot=Slot.MORNING)
# → "去学校上课，今天有考试。"

# 对话
reply = await agent.respond("你今天看起来不太开心，发生什么了？", speaker_name="陈远舟")
# → "没什么……只是昨晚又做了那个梦。"

# 状态更新
agent.set_location(Location.SCHOOL, reason="上学")
agent.set_happiness(-5, reason="考试没考好")
agent.set_emotion(Emotion.SAD, reason="被母亲责备")

# 记忆
agent.remember(day=1, slot=Slot.NOON, description="数学考试没及格",
               importance=7, emotion=Emotion.SAD)
# importance >= 7 → 自动进入关键记忆

# 快照
snapshot = agent.snapshot()
# → NpcSnapshot(static=..., dynamic=..., memory_summary={...})

# 存档
data = agent.to_dict()
# → {"static_id": "lin_chaoyin", "dynamic": {...}, "memory": {...}}

# 读档
restored = NpcAgent.from_dict(data, static=demo_lin_chaoyin())
```

### 6.2 AgentManager

```python
from src.backend.ai.npc_agent.manager import AgentManager
from src.backend.models.npc import Slot

# 初始化
manager = AgentManager()
manager.init_from_demo()       # 加载 Demo NPC
# 或
manager.init_from_statics(statics_from_csv)

# 查询
agent = manager.get("lin_chaoyin")
s_tier = manager.list_by_tier(AgentTier.S)
at_school = manager.list_at_location(Location.SCHOOL)
print(manager.count)           # 2

# 批量思考（时段推进）
actions = await manager.all_think(day=1, slot=Slot.MORNING)
# → {"lin_chaoyin": "去学校上课", "chen_yuanzhou": "到书店复习"}

# 批量记忆
manager.all_remember(
    day=1, slot=Slot.NOON,
    event_descriptions={
        "lin_chaoyin": "和陈远舟在学校门口相遇",
        "chen_yuanzhou": "和林潮音在学校门口相遇",
    },
    importance=6
)

# 返回给前端
response = manager.all_snapshots()
# → NpcListResponse(npcs=[...], total=2)

# 存档
data = manager.to_dict()

# 读档需要 static_map
static_map = {"lin_chaoyin": demo_lin_chaoyin(), "chen_yuanzhou": demo_chen_yuanzhou()}
restored = AgentManager.from_dict(data, static_map)
```

### 6.3 MemoryStore

```python
from src.backend.ai.npc_agent.memory import MemoryStore
from src.backend.models.npc import Slot, Emotion

store = MemoryStore(npc_id="lin_chaoyin")

# 记录记忆
store.remember(
    day=5, slot=Slot.NIGHT,
    description="陈远舟在海边对她说想带她离开小镇",
    importance=9, emotion=Emotion.EXCITED,
)
store.remember(
    day=8, slot=Slot.NOON,
    description="慧圆和尚找她谈话，提到巫女的事情",
    importance=8, emotion=Emotion.ANXIOUS,
)

# 查询
store.event_count    # 2
store.key_count      # 2（两条 importance >= 7）
recent = store.recent_events(5)
top = store.top_key_memories(3)

# 印象
store.update_impression("chen_yuanzhou", affinity_delta=10, trust_delta=5, label="爱慕")
store.update_impression("hui_yuan", affinity_delta=-5, label="警惕")
impression = store.get_impression("chen_yuanzhou")
# → Impression(npc_id="chen_yuanzhou", affinity=60, trust=55, label="爱慕")

# LLM 上下文
ctx = store.context_for_llm(max_events=10)
# → """
# 【最近经历】
#   Day5 night: 陈远舟在海边对她说想带她离开小镇（重要性9，excited）
#   Day8 noon: 慧圆和尚找她谈话，提到巫女的事情（重要性8，anxious）
# 【对他人印象】
#   chen_yuanzhou: 好感60 信任55 (爱慕)
#   hui_yuan: 好感45 信任50 (警惕)
# """
```

### 6.4 DynamicState

```python
from src.backend.ai.npc_agent.dynamic import DynamicState, create_initial_dynamic
from src.backend.models.npc import Location, Emotion

state = create_initial_dynamic(location=Location.SCHOOL)

# 查询
state.current.location    # Location.SCHOOL
state.current.happiness   # 50
state.snapshot()          # dict 给 LLM 用

# 修改（自动追踪 delta）
state.set_location("lin_chaoyin", Location.BEACH, reason="放学后去海边")
state.set_happiness("lin_chaoyin", delta=15, reason="考了第一名")
state.set_emotion("lin_chaoyin", Emotion.HAPPY, reason="好消息")

# 获取变更
deltas = state.deltas
# → [DynamicDelta("lin_chaoyin", "location", ...), ...]
# deltas 读取后自动清空，下次读取只包含新的变更
```

---

## 7. 使用示例

### 7.1 完整的 Demo 启动流程

```python
import asyncio
from src.backend.ai.npc_agent.manager import AgentManager
from src.backend.ai.npc_agent.static import demo_npcs
from src.backend.models.npc import Slot, Location, Emotion

async def demo_session():
    # 1. 创建管理器
    manager = AgentManager()
    manager.init_from_demo()

    # 2. 获取林潮音
    chaoyin = manager.get("lin_chaoyin")
    print(f"初始状态: {chaoyin.name} 在 {chaoyin.location.value}, "
          f"幸福度 {chaoyin.dynamic.current.happiness}")

    # 3. 移动到学校，开始第一天早晨
    chaoyin.set_location(Location.SCHOOL, reason="上学")

    # 4. NPC 思考
    actions = await manager.all_think(day=1, slot=Slot.MORNING)
    for npc_id, action in actions.items():
        print(f"  {npc_id}: {action}")

    # 5. 模拟事件：两人在学校相遇
    chaoyin.remember(day=1, slot=Slot.MORNING,
                     description="在学校门口遇到陈远舟，他说要去书店",
                     importance=6, emotion=Emotion.CALM)
    chaoyin.set_happiness(5, reason="见到陈远舟")

    yuanzhou = manager.get("chen_yuanzhou")
    yuanzhou.remember(day=1, slot=Slot.MORNING,
                      description="在学校门口遇到林潮音，她看起来有点累",
                      importance=5, emotion=Emotion.NEUTRAL)

    # 6. 更新彼此的印象
    chaoyin.memory.update_impression("chen_yuanzhou", affinity_delta=3)
    yuanzhou.memory.update_impression("lin_chaoyin", affinity_delta=2)

    # 7. 模拟对话
    reply = await chaoyin.respond(
        "周末要不要一起去书店？", speaker_name="陈远舟"
    )
    print(f"\n陈远舟: 周末要不要一起去书店？")
    print(f"林潮音: {reply}")

    # 8. 查看记忆
    print(f"\n林潮音的记忆 ({chaoyin.memory.event_count} 条):")
    for e in chaoyin.memory.recent_events(3):
        print(f"  Day{e.day}: {e.description} (重要性{e.importance})")

    # 9. 查看快照
    response = manager.all_snapshots()
    print(f"\n活跃 NPC: {response.total} 人")

asyncio.run(demo_session())
```

### 7.2 时段推进 + 事件结算

```python
async def advance_time(manager: AgentManager, day: int, slot: Slot):
    """模拟一个时段的推进和结算。"""

    # Step 1: 所有 NPC 决定这个时段要做什么
    actions = await manager.all_think(day, slot)

    # Step 2: 事件引擎在这里结算（未来实现）
    # events = event_engine.resolve(actions)

    # Step 3: 对每个参与了事件的 NPC 记录记忆
    manager.all_remember(day, slot, {
        "lin_chaoyin": "在咖啡店遇到了叶可可，聊了巫女的事情",
        "chen_yuanzhou": "整个下午都在书店复习数学",
    }, importance=5)

    # Step 4: 收集增量变更返回给 Godot
    deltas = {}
    for agent in manager.list_all():
        deltas[agent.npc_id] = agent.dynamic.deltas

    return {
        "actions": actions,
        "deltas": deltas,
        "day": day,
        "slot": slot.value,
    }
```

---

## 8. LLM 集成

### 8.1 当前状态：桩实现

`agent.py` 中的 `LLMClient` 是**桩**——所有方法返回空字符串或不执行操作。game 逻辑通过 `_default_action()` 和 `_default_response()` 兜底。

### 8.2 替换为真实 LLM

实现 `LLMClient` 接口即可：

```python
# ai/llm_client/deepseek_client.py

class DeepSeekClient:
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self._api_key = api_key
        self._model = model
        self._history: list[dict] = []

    async def chat(self, messages: list[dict]) -> str:
        # 调用 DeepSeek API
        response = await httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": messages},
        )
        return response.json()["choices"][0]["message"]["content"]

    async def chat_stream(self, messages: list[dict]):
        # 流式调用
        ...

    def add_to_history(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})

    def get_history(self) -> list[dict]:
        return self._history

    def clear_history(self) -> None:
        self._history.clear()
```

**切换方式：** 创建 Agent 时注入不同的 LLM 客户端。

```python
agent = NpcAgent(
    static=demo_lin_chaoyin(),
    llm=DeepSeekClient(api_key="sk-xxx"),
)
```

### 8.3 Agent 等级与 LLM 调用策略

| 等级 | LLM 调用时机 | 记忆保留 | NPC 数量 |
|------|-------------|----------|----------|
| S | 每时段 think() + 对话 respond() | 完整事件链 + 关键记忆 + 印象 | 6 |
| A | 事件触发时 think()，对话 respond() | 关键记忆 + 印象 | 4 |
| B | 无 LLM | 无记忆 | 3 |
| C | 无 LLM | 无记忆 | 8+ |

---

## 9. 扩展指南

### 9.1 添加新 NPC

```python
# 在 static.py 中添加
def demo_chen_haisheng() -> NpcStatic:
    return NpcStatic(
        id="chen_haisheng",
        name="陈海生",
        age=45,
        occupation="渔民",
        tier=AgentTier.S,
        background="归潮镇本地渔民...",
        attributes=FixedAttributes(mind=4, faith=3, physique=8, charm=4),
        personality=Personality(
            kindness=0.3, aggression=0.8,
            sensibility=0.4, rationality=0.3, curiosity=0.2,
        ),
        core_wish="重新证明自己是有用的男人",
    )
```

### 9.2 自定义性格 Prompt

修改 `templates.py` 中的 `_describe_personality()` 和 `SYSTEM_PROMPT_TEMPLATE`。

### 9.3 自定义溢出策略

修改 `memory.py` 中的 `MAX_EVENT_CHAIN` 和 `_compact_event_chain()` 实现。

### 9.4 从 CSV 批量加载

```python
# 未来实现 data/csv_loader.py
statics = load_npc_statics_from_csv("design/data/NPC基础表.csv")
manager.init_from_statics(statics)
```

---

## 10. 常量与配置

| 模块 | 常量 | 值 | 说明 |
|------|------|----|------|
| memory | `MAX_EVENT_CHAIN` | 50 | 事件链上限 |
| memory | `MAX_KEY_MEMORIES` | 30 | 关键记忆上限 |
| memory | `IMPORTANCE_THRESHOLD` | 7 | 自动进入关键记忆的阈值 |
| dynamic | happiness 范围 | 0 ~ 100 | 自动钳制 |
| dynamic | energy 范围 | 0 ~ 100 | 自动钳制 |
| dynamic | karma_main_progress 范围 | 0.0 ~ 100.0 | 自动钳制 |
| models | NPC age 范围 | 10 ~ 100 | Pydantic 校验 |
| models | importance 范围 | 1 ~ 10 | Pydantic 校验 |
| models | affinity/trust 范围 | 0 ~ 100 | Pydantic 校验 |
| templates | 决策输出长度 | ≤ 15 字 | Prompt 约束 |

---

## 附录 A：文件依赖关系

```
models/npc.py (Pydantic)
    │
    ├──→ static.py      (依赖: NpcStatic, Personality, FixedAttributes, AgentTier)
    ├──→ dynamic.py     (依赖: NpcDynamic, Location, Emotion, Slot)
    ├──→ memory.py      (依赖: AgentMemory, MemoryEntry, Impression, Emotion, Slot)
    ├──→ templates.py   (依赖: NpcStatic, Personality)
    │
    └──→ agent.py       (依赖: 以上全部 + LLMClient)
              │
              └──→ manager.py  (依赖: NpcAgent + 所有模型)
```

## 附录 B：与策划案的对应关系

| 代码模块 | 策划案章节 |
|----------|-----------|
| `static.py` | §8.6.2 静态层示例 |
| `dynamic.py` | §8.6.1 动态层 |
| `memory.py` | §8.6.3 Agent Memory 层 + §8.6.6 溢出处理 |
| `templates.py` | —（架构新增） |
| `agent.py` | §8.7 NPC 角色设计 + §8.7.2 Agent 级别说明 |
| `manager.py` | —（架构新增） |
| `models/npc.py` | §8.6.1 NPC 数据结构总览 + §8.6.5 历史互动层 |
