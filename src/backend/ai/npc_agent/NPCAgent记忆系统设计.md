# NPC Agent 记忆系统设计

> 模块：`ai/npc_agent/`  
> 更新日期：2026-06-18  
> 状态：设计定稿，待实现

---

## 目录

1. [记忆三分类总览](#1-记忆三分类总览)
2. [工作记忆](#2-工作记忆)
3. [情景记忆](#3-情景记忆)
4. [语义记忆](#4-语义记忆)
5. [检索流水线](#5-检索流水线)
6. [配置参数](#6-配置参数)
7. [LLM 提取流程](#7-llm-提取流程)
8. [数据结构汇总](#8-数据结构汇总)
9. [与现有代码的对接](#9-与现有代码的对接)

---

## 1. 记忆三分类总览

```
┌─────────────────────────────────────────────────┐
│              NPC Agent 记忆系统                   │
│                                                  │
│  工作记忆         情景记忆          语义记忆       │
│  (临时视图)       (双库双索引)      (知识图谱)     │
│                                                  │
│  当前在关注什么    经历过什么         学到了什么     │
│  全量放入 LLM     向量+结构检索       向量+图谱检索  │
│  不存档           全量存档           全量存档       │
│  5~10 条          ≤50 → 精简至~30    不限 → 溢出   │
└─────────────────────────────────────────────────┘
```

| 维度 | 工作记忆 | 情景记忆 | 语义记忆 |
|------|----------|----------|----------|
| **是什么** | 当前关注的上下文 | 过去经历的具体事件 | 从经历提炼的抽象认知 |
| **存储** | 不存储，每次临时拼装 | 结构库 + 向量库（双库） | statement + 知识图谱 |
| **检索** | 全量放入 LLM 上下文 | 向量相似度 + 时间衰减 + 重要性加权 + 阈值过滤 | 向量检索 + 图谱关系推理，并行合并 |
| **创建方式** | `think()/respond()` 时从各层提取 | 事件引擎结算后 `remember()` | LLM 定期从情景记忆中提取 |
| **数量** | 5-10 条 | ≤50 条（溢出精简至 ~30） | 不限（溢出时提取进图谱） |
| **存档** | 不存档 | 全量序列化 | 全量序列化 |

三层的关系：

```
事件结算 → agent.remember()
              │
              ▼
         情景记忆（具体经历）
              │  LLM 提取（日终/溢出）
              ▼
         语义记忆（抽象认知）
              │  LLM 提取（同上）
              ▼
         知识图谱（实体+关系）
              │
              └──→ 每时段 think()/respond() 时
                   三层并行检索 → 拼接 → LLM 上下文
```

---

## 2. 工作记忆

### 2.1 定义

工作记忆是 NPC 在**当前时刻**脑子里的决策负荷。不独立存储——每次 `think()` 或 `respond()` 调用时，从其他各层临时拼装。

### 2.2 组装内容

```python
def build_working_memory(agent: NpcAgent, day: int, slot: Slot) -> dict:
    """每次调用 think()/respond() 时临时组装。"""
    state = agent.dynamic.current
    
    return {
        # 从 dynamic 取——当前状态
        "current_location": state.location.value,
        "current_emotion": state.emotion.value,
        "current_goal": state.current_goal,
        "current_time": f"Day {day} {slot.value}",
        
        # 从 today_events 取——今天刚发生的（情景记忆的尾部）
        "today_events": [
            e.description 
            for e in agent.memory.recent_events(10)
            if e.day == day  # 只取当天的
        ],
        
        # 从 conversation 取——当前对话上下文（如果有）
        "conversation": agent.current_conversation or [],
    }
```

### 2.3 特征

| 维度 | 说明 |
|------|------|
| 存储 | 不独立存储，临时拼装 |
| 放入 LLM | 全量（5-10 条，体积小） |
| 存档 | 不存档（新时段重建） |
| 生命周期 | 一个 `think()` / `respond()` 调用期间 |

---

## 3. 情景记忆

### 3.1 定义

情景记忆是 NPC 经历的**具体事件的时间日志**——"Day15 下午，慧圆在寺庙推举我为巫女候选"。

### 3.2 双库存储

同一条记忆在两个库中各存一份，用 `memory_id` 关联：

```
┌─────────────────────────────┐    ┌──────────────────────────┐
│       结构库                 │    │        向量库             │
│                              │    │                          │
│  memory_id: "mem_001"       │◄───│  memory_id: "mem_001"    │
│  day: 15                    │    │  embedding: [0.12, ...]   │
│  slot: noon                 │    │      ↑                   │
│  importance: 9              │    │  description 的向量        │
│  emotion: anxious           │    │                          │
│  participants: [慧圆, 林潮音]│   │                          │
│  description: "慧圆在..."    │    │                          │
└─────────────────────────────┘    └──────────────────────────┘
```

| 库 | 存储内容 | 用途 |
|----|----------|------|
| **结构库** | day, slot, importance, emotion, participants, event_id | 结构化筛选 + 时间衰减计算 |
| **向量库** | memory_id, embedding | 语义相似度匹配 |

### 3.3 检索公式

```python
def calculate_episode_score(
    hit,
    current_day: int,
    base_decay: float = 30.0,
    vec_weight: float = 0.8,
    recency_weight: float = 0.2,
    imp_weight_base: float = 0.8,
    imp_weight_scale: float = 0.4,
) -> float:
    """
    情景记忆评分。

    公式：
        norm_imp = importance / 10
        S = base_decay * norm_imp               # 记忆强度
        recency_score = e^(-days_elapsed / S)    # 艾宾浩斯遗忘
        base_relevance = vec_score * vec_weight
                       + recency_score * recency_weight
        importance_weight = imp_weight_base + norm_imp * imp_weight_scale
        final = base_relevance * importance_weight
    """
    norm_imp = hit.importance / 10.0
    days_elapsed = current_day - hit.day

    # 艾宾浩斯遗忘
    S = base_decay * norm_imp
    recency_score = math.exp(-days_elapsed / S) if S > 0 else 0.0

    # 基础相关度（语义为主，近因为辅）
    base_relevance = hit.vector_score * vec_weight + recency_score * recency_weight

    # 重要性加权
    importance_weight = imp_weight_base + norm_imp * imp_weight_scale

    return base_relevance * importance_weight
```

### 3.4 计算示例

当前 Day 30，`base_decay=30`：

| 事件 | imp | 天数差 | vec | recency | base | imp_w | 最终 |
|------|-----|--------|-----|---------|------|-------|------|
| Day15 巫女推举 | 10 | 15 | 0.90 | e^(-15/30)=0.61 | 0.84 | 1.20 | **1.01** |
| Day28 和远舟说话 | 5 | 2 | 0.70 | e^(-2/15)=0.88 | 0.74 | 1.00 | 0.74 |
| Day5 海边聊天 | 8 | 25 | 0.60 | e^(-25/24)=0.35 | 0.55 | 1.12 | 0.62 |
| Day22 日常 | 5 | 8 | 0.50 | e^(-8/15)=0.59 | 0.52 | 1.00 | 0.52 |
| Day3 路过游客 | 3 | 27 | 0.20 | e^(-27/9)=0.05 | 0.17 | 0.92 | 0.16 |
| Day1 买了早餐 | 2 | 29 | 0.10 | e^(-29/6)=0.01 | 0.08 | 0.88 | **0.07** |

- 巫女推举（imp=10, 15天前）排第一
- Day5 海边聊天（imp=8）虽然 25 天前，但重要性高 → 超过 Day22 日常
- Day1 早餐和 Day3 游客得分极低 → 被阈值过滤

### 3.5 阈值过滤

得分 < `threshold`（默认 0.15）的记忆视为"已遗忘"，不进入 LLM 上下文。上例中 Day1 早餐（0.07）被丢弃。

### 3.6 现有对应的代码

| 功能 | 现有代码 | 待升级 |
|------|----------|--------|
| 存储 | `MemoryStore._event_chain` + `_key_memories` | 拆为结构库 + 向量库 |
| 保存 | `MemoryStore.remember()` | 追加写入双库 |
| 检索 | `MemoryStore.context_for_llm()` | 替换为上述检索公式 |
| 溢出 | `MemoryStore._compact_event_chain()` | 双库同步精简 |

---

## 4. 语义记忆

### 4.1 定义

语义记忆是从经历中**提炼的抽象知识**——"成为巫女意味着再也无法离开小镇"。

### 4.2 数据结构

```python
class SemanticCategory(str, Enum):
    PERSON = "person"        # 关于人的认知
    LOCATION = "location"    # 关于地点的认知
    SELF = "self"            # 关于自己的认知
    RULE = "rule"            # 关于世界规律的认知
    ITEM = "item"            # 关于物品的认知

class SemanticEntry(BaseModel):
    statement: str           # 自然语言陈述
    confidence: float        # 信念强度 0.0 ~ 1.0
    category: SemanticCategory
    source_events: list[str] # 来源事件 ID（可追溯）
    created_day: int         # 创建时的天数
    embedding: list[float]   # 向量（128 或 256 维）

class SemanticMemory(BaseModel):
    npc_id: str
    entries: list[SemanticEntry]
    pending_episodic: list[str]          # 待处理的情景记忆 ID
    last_extraction_day: int
    last_graph_extraction_day: int
```

### 4.3 知识图谱结构

```python
class KnowledgeGraph(BaseModel):
    npc_id: str
    entities: dict[str, Entity]
    relations: list[Relation]

class Entity(BaseModel):
    name: str                # "慧圆"
    type: str                # "person" | "location" | "concept" | "item"
    mentions: int            # 被多少条语义记忆提到

class Relation(BaseModel):
    subject: str             # "慧圆"
    predicate: str           # "推举"
    object: str              # "巫女"
    source_statement: str    # 来源语义记忆
    frequency: int           # 被验证次数
```

### 4.4 检索策略

**方案 C：向量检索 + 图谱检索并行，合并去重归一排序。**

```
当前情境 → RetrievalContext
  │
  ├──→ 向量检索：embedding 余弦相似度 → Top K
  │
  └──→ 图谱检索：上下文实体 两跳 → 关联 statement
        │
        ▼
   合并去重 → 归一化得分 → 排序 → Top N → 放入 LLM 上下文
```

### 4.5 图谱得分公式

```python
def calculate_graph_score(
    statement_entities: list[str],
    context_entities: set[str],
    relations: list[Relation],
    hop_weights: dict[int, float],
    max_hops: int = 2,
) -> float:
    """
    图谱得分 = Σ( 1/d(e,C) × hop_weight[d] )

    d(e,C) = 实体 e 到最近上下文实体的最短路径跳数
    hop_weight = {0: 1.0, 1: 0.5, 2: 0.25}
    > max_hops 的实体权重为 0
    """
    raw = 0.0
    for entity in statement_entities:
        min_dist = min(
            graph_distance(entity, ctx, relations)
            for ctx in context_entities
        )
        if min_dist <= max_hops:
            raw += hop_weights.get(min_dist, 0.0)
    return raw
```

### 4.6 最终合并

```python
final_score = alpha * vector_score + beta * normalized_graph_score

# alpha=0.6（向量为主），beta=0.4（图谱为辅）
```

### 4.7 置信度

- 同一条 statement 被新事件验证 → confidence 上升
- 遇到矛盾证据 → confidence 下降
- 低于 `confidence_min`（默认 0.3）的 statement 不纳入检索

---

## 5. 检索流水线

每次 `agent.think()` 或 `agent.respond()` 调用时，三层记忆按以下顺序组装：

```
┌──────────────────────────────────────────────────┐
│  输入: RetrievalContext                           │
│    location, emotion, goal, day, slot, entities   │
├──────────────────────────────────────────────────┤
│                                                  │
│  ① 工作记忆（临时拼装）                            │
│     dynamic 当前状态 + 当天的情景记忆 + 对话上下文    │
│     → 全量放入（5~10 条）                         │
│                                                  │
│  ② 情景记忆（双库检索）                            │
│     结构库: 参与者/地点筛选                        │
│     向量库: description embedding 余弦相似度       │
│     → calculate_episode_score()                  │
│     → 阈值过滤 (>= threshold)                    │
│     → Top K 放入                                 │
│                                                  │
│  ③ 语义记忆（向量+图谱并行）                       │
│     向量检索: embedding → Top K                   │
│     图谱检索: 实体两跳 → 关联 statement            │
│     → 合并去重归一化                              │
│     → 最终得分 = alpha*vector + beta*graph        │
│     → Top N 放入                                 │
│                                                  │
├──────────────────────────────────────────────────┤
│  输出: 拼接为 LLM system_prompt 的记忆段落          │
│                                                  │
│  【当前状态】    ← 工作记忆                        │
│  【最近经历】    ← 情景记忆（检索后）               │
│  【你学到的】    ← 语义记忆（检索后）               │
│  【对他人的印象】← 情景记忆中的 impressions          │
└──────────────────────────────────────────────────┘
```

---

## 6. 配置参数

所有可调参数从配置文件读取（`config/memory.yaml`）：

```yaml
memory:
  # ── 情景记忆 ──
  episodic:
    struct_store: "memory_struct"       # 结构库名称
    vector_store: "memory_vector"       # 向量库名称
    base_decay: 30.0                    # 遗忘基础天数
    vec_weight: 0.8                     # 向量得分权重
    recency_weight: 0.2                 # 近因得分权重
    imp_weight_base: 0.8                # 重要性加权基础值
    imp_weight_scale: 0.4              # 重要性加权缩放系数
    threshold: 0.15                     # 筛选阈值（低于此分丢弃）
    top_k: 12                           # 返回给 LLM 的条数
    max_event_chain: 50                 # 事件链溢出上限
    max_key_memories: 30                # 关键记忆上限
    importance_threshold: 7             # 进入关键记忆的 importance 阈值

  # ── 语义记忆 ──
  semantic:
    # LLM 提取触发
    episodic_pending_threshold: 10      # 积累 N 条情景记忆触发提取
    semantic_overflow_threshold: 30     # 语义记忆超过 N 条触发溢出
    graph_extract_threshold: 15         # 新增 N 条语义记忆触发图谱提取
    extract_schedule: "end_of_day"      # 提取时机：end_of_day | overflow

    # 检索
    vector_top_k: 10                    # 向量检索返回前 K 条
    graph_max_hops: 2                   # 图谱检索最大跳数
    graph_hop_weights:                  # 每跳权重
      "0": 1.0
      "1": 0.5
      "2": 0.25
    final_top_n: 8                      # 最终返回给 LLM 的条数

    # 得分合并
    alpha: 0.6                          # 向量权重
    beta: 0.4                           # 图谱权重

    # 置信度
    confidence_min: 0.3                 # 低于此值不纳入检索

  # ── 工作记忆 ──
  working:
    today_events_count: 10              # 取今天最近 N 条事件
    conversation_max_turns: 6           # 对话上下文最多保留轮数
```

---

## 7. LLM 提取流程

### 7.1 触发时机

| 条件 | 执行 |
|------|------|
| `pending_episodic >= episodic_pending_threshold` | "情景→语义" 提取 |
| `semantic_entries >= semantic_overflow_threshold` | "语义→图谱" 提取 |
| 日终 | 检查以上两个条件 |

### 7.2 第一次提取：情景记忆 → 语义记忆

**输入：** 最近积累的情景记忆列表（10-20 条）

**LLM Prompt 核心指令：**

```
你是 NPC {name}，请根据以上经历，提炼你学到的认知。

要求：
1. 每条认知一句话（20字以内），用第一人称
2. 按类别分类：person / location / self / rule / item
3. 给每条认知一个 confidence（0-1）
4. 已有认知被新经历验证 → 提升 confidence
5. 已有认知被新经历推翻 → 降低 confidence
```

**输出格式：**

```json
[
  {
    "statement": "成为巫女意味着再也无法离开小镇",
    "confidence": 0.6,
    "category": "rule",
    "source_events": ["evt_witch_001"],
    "action": "create"
  }
]
```

### 7.3 第二次提取：语义记忆 → 知识图谱

**输入：** 最近新增的语义记忆（10-20 条）

**LLM Prompt 核心指令：**

```
请从以下陈述中提取实体和关系。

实体类型：person / location / concept / item
关系：用一个动词描述
每关系标注来源 statement
```

**输出格式：**

```json
[
  {
    "entities": [
      {"name": "慧圆", "type": "person"}
    ],
    "relations": [
      {
        "subject": "慧圆", "predicate": "推举", "object": "巫女",
        "source_statement": "慧圆对巫女的事非常认真"
      }
    ]
  }
]
```

---

## 8. 数据结构汇总

```python
# ══════════════════════════════════════════════
# 检索上下文（检索输入）
# ══════════════════════════════════════════════

class RetrievalContext(BaseModel):
    location: str
    emotion: str
    current_goal: str
    day: int
    slot: str
    context_entities: list[str]     # LLM 轻量提取或规则匹配

# ══════════════════════════════════════════════
# 检索结果（检索输出）
# ══════════════════════════════════════════════

class ScoredEntry(BaseModel):
    memory_id: str
    description: str
    vector_score: float             # 0~1
    graph_score: float              # 0~1（归一化后，仅语义记忆有）
    final_score: float
    source: str                     # "vector" | "graph" | "both"

class RetrievalResult(BaseModel):
    working_memory: dict
    episodic_entries: list[ScoredEntry]
    semantic_entries: list[ScoredEntry]

# ══════════════════════════════════════════════
# 情景记忆
# ══════════════════════════════════════════════

class MemoryEntry(BaseModel):
    """单条情景记忆。"""
    memory_id: str                  # 唯一标识
    day: int                        # 1~60
    slot: Slot
    event_id: str
    description: str                # 事件简述
    importance: int                 # 1~10
    emotion: Emotion
    participants: list[str]         # 参与者 NPC ID 列表
    location: str                   # 发生地点

class StructMemoryStore:            # 结构库
    entries: dict[str, MemoryEntry]

class VectorMemoryStore:            # 向量库
    entries: dict[str, list[float]] # memory_id → embedding

# ══════════════════════════════════════════════
# 语义记忆
# ══════════════════════════════════════════════

class SemanticEntry(BaseModel):
    statement: str
    confidence: float               # 0~1
    category: SemanticCategory
    source_events: list[str]
    created_day: int
    embedding: list[float]

class Entity(BaseModel):
    name: str
    type: str
    mentions: int

class Relation(BaseModel):
    subject: str
    predicate: str
    object: str
    source_statement: str
    frequency: int

class KnowledgeGraph(BaseModel):
    npc_id: str
    entities: dict[str, Entity]
    relations: list[Relation]
```

---

## 9. 与现有代码的对接

### 9.1 需要修改/新增的文件

| 文件 | 变更 |
|------|------|
| `models/npc.py` | `MemoryEntry` 新增 `memory_id`, `participants`, `location`; 新增 `SemanticEntry`, `SemanticCategory`, `KnowledgeGraph`, `Entity`, `Relation`, `RetrievalContext`, `ScoredEntry`, `RetrievalResult` |
| `memory.py` | `MemoryStore` → `StructMemoryStore` + `VectorMemoryStore`; 替换 `context_for_llm()` 为检索流水线 |
| **新增** `semantic.py` | `SemanticStore` — 语义记忆存储/检索/LM提取/图谱管理 |
| **新增** `retrieval.py` | `RetrievalPipeline` — 三层检索流水线 |
| `agent.py` | `NpcAgent.think()` / `respond()` 调用检索流水线 |
| `templates.py` | system_prompt 增加语义记忆段落 |
| **新增** `config/memory.yaml` | 可调参数配置文件 |
| `ai/npc_agent/README.md` | 更新文档 |

### 9.2 实现优先级

| 阶段 | 内容 | 依赖 |
|------|------|------|
| P0 | `MemoryEntry` 结构升级（加 `memory_id`/`participants`/`location`） | — |
| P0 | `StructMemoryStore` + `VectorMemoryStore` | P0 |
| P0 | 情景记忆检索公式实现 | P0 |
| P1 | `SemanticEntry` / `SemanticMemory` / `KnowledgeGraph` 数据结构 | P0 |
| P1 | `SemanticStore` — 存储/查询/序列化 | P1 |
| P2 | LLM 提取: 情景→语义 | P1 |
| P2 | LLM 提取: 语义→图谱 | P1 |
| P2 | 向量检索 + 图谱检索 + 合并排序 | P1 |
| P3 | `RetrievalPipeline` — 三层统一检索 | P0 + P2 |
| P3 | 配置文件加载 | P0 |
| P4 | `templates.py` / `agent.py` 对接新检索 | P3 |

---

*本文档为记忆系统的最终设计。实施时如有偏离，请更新对应章节。*
