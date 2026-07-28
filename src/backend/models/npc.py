"""NPC 数据模型 —— 前后端数据合同。

本模块定义 NPC 的完整数据结构，分为三层：
- 静态层（不可变）
- 动态层（每时段更新）
- 记忆层（事件链 + 印象）

所有模型使用 Pydantic，自动生成 JSON Schema，前端可直接参照。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════

class AgentTier(str, Enum):
    """NPC Agent 级别。"""
    S = "S"    # 完整 Agent：独立记忆 + LLM
    A = "A"    # 半完整 Agent：关键记忆 + 事件触发 LLM
    B = "B"    # 规则驱动：固定状态机
    C = "C"    # 轻量剧情：固定反应


class Slot(str, Enum):
    """一天中的时段。"""
    MORNING = "morning"
    NOON = "noon"
    NIGHT = "night"


class Emotion(str, Enum):
    """NPC 当前情绪。"""
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    CALM = "calm"
    EXCITED = "excited"
    ANXIOUS = "anxious"
    NEUTRAL = "neutral"


class Location(str, Enum):
    """归潮镇 12 个地点。"""
    MOUNTAIN_FOREST = "mountain_forest"   # 山林
    BEACH = "beach"                       # 沙滩
    SCHOOL = "school"                     # 学校
    CLINIC = "clinic"                     # 诊所
    SHOPPING_STREET = "shopping_street"   # 商业街
    BOOKSTORE = "bookstore"               # 书店
    PLAZA = "plaza"                       # 广场
    CAFE = "cafe"                         # 咖啡厅
    POLICE_STATION = "police_station"     # 警局
    TEMPLE = "temple"                     # 寺庙与钟塔
    RESIDENCE = "residence"               # 住所
    PORT = "port"                         # 港口


# ═══════════════════════════════════════════════════
# 静态层
# ═══════════════════════════════════════════════════

class Personality(BaseModel):
    """五维性格模型（0.0 ~ 1.0）。"""
    kindness: float = Field(default=0.5, ge=0.0, le=1.0, description="善良")
    aggression: float = Field(default=0.3, ge=0.0, le=1.0, description="激进")
    sensibility: float = Field(default=0.5, ge=0.0, le=1.0, description="感性")
    rationality: float = Field(default=0.5, ge=0.0, le=1.0, description="理性")
    curiosity: float = Field(default=0.5, ge=0.0, le=1.0, description="好奇心")

    @field_validator("*")
    @classmethod
    def clamp_range(cls, v: float) -> float:
        return max(0.0, min(1.0, round(v, 2)))


class FixedAttributes(BaseModel):
    """四围固定属性（1 ~ 10）。"""
    mind: int = Field(default=5, ge=1, le=10, description="心智")
    faith: int = Field(default=5, ge=1, le=10, description="信仰")
    physique: int = Field(default=5, ge=1, le=10, description="体魄")
    charm: int = Field(default=5, ge=1, le=10, description="魅力")


class NpcStatic(BaseModel):
    """NPC 静态层 —— 创建后不可变。"""
    id: str = Field(..., description="唯一标识，如 lin_chaoyin")
    name: str = Field(..., description="中文名，如 林潮音")
    age: int = Field(..., ge=10, le=100, description="年龄")
    occupation: str = Field(..., description="职业")
    tier: AgentTier = Field(..., description="Agent 级别")
    background: str = Field(default="", description="故事背景摘要")
    attributes: FixedAttributes = Field(default_factory=FixedAttributes)
    personality: Personality = Field(default_factory=Personality)
    core_wish: str = Field(default="", description="核心愿望")


# ═══════════════════════════════════════════════════
# 动态层
# ═══════════════════════════════════════════════════

class NpcDynamic(BaseModel):
    """NPC 动态层 —— 每时段结算后更新。"""
    location: Location = Field(default=Location.RESIDENCE, description="当前位置")
    happiness: int = Field(default=50, ge=0, le=100, description="幸福度")
    energy: int = Field(default=100, ge=0, le=100, description="精力")
    emotion: Emotion = Field(default=Emotion.NEUTRAL, description="当前情绪")
    current_goal: str = Field(default="", description="当前短中期目标")
    karma_main_progress: float = Field(default=0.0, ge=0.0, le=100.0, description="主业线进度")
    karma_side_progress: Dict[str, float] = Field(
        default_factory=dict, description="支线进度 {side_name: progress}"
    )


# ═══════════════════════════════════════════════════
# 记忆层
# ═══════════════════════════════════════════════════

class MemoryEntry(BaseModel):
    """单条情景记忆 —— 结构库存储单元。"""
    memory_id: str = Field(
        default_factory=lambda: uuid4().hex[:12],
        description="唯一标识"
    )
    day: int = Field(..., ge=1, le=60)
    slot: Slot = Field(...)
    event_id: str = Field(default="", description="关联事件 ID")
    description: str = Field(..., description="事件简述")
    importance: int = Field(default=5, ge=1, le=10, description="重要性 1-10")
    emotion: Emotion = Field(default=Emotion.NEUTRAL)
    participants: List[str] = Field(
        default_factory=list, description="参与者 NPC ID 列表"
    )
    location: str = Field(default="", description="发生地点")
    source: str = Field(default="event", description="来源: event | dream | blessing_felt | ambient")
    dream_incense_snapshot: int = Field(default=0, description="若 source=dream，写入时的香火值快照")
    dream_text: str = Field(default="", description="若 source=dream，玩家托梦原文")


class Impression(BaseModel):
    """对另一个角色的情感印象。"""
    npc_id: str = Field(..., description="对象 NPC ID")
    affinity: int = Field(default=50, ge=0, le=100, description="好感度")
    trust: int = Field(default=50, ge=0, le=100, description="信任度")
    label: str = Field(default="", description="印象标签，如 爱慕 / 敬畏 / 嫉妒")


class AgentMemory(BaseModel):
    """NPC 的记忆层。"""
    npc_id: str = Field(..., description="所属 NPC ID")
    event_chain: List[MemoryEntry] = Field(
        default_factory=list, max_length=50, description="完整事件链"
    )
    key_memories: List[MemoryEntry] = Field(
        default_factory=list, max_length=30, description="关键记忆（重要性排序）"
    )
    impressions: Dict[str, Impression] = Field(
        default_factory=dict, description="对其他 NPC 的印象 {npc_id: Impression}"
    )
    memory_overflow_count: int = Field(
        default=0, description="记忆溢出次数（用于调试）"
    )


# ═══════════════════════════════════════════════════
# 语义记忆层
# ═══════════════════════════════════════════════════

class SemanticCategory(str, Enum):
    """语义记忆分类。"""
    PERSON = "person"
    LOCATION = "location"
    SELF = "self"
    RULE = "rule"
    ITEM = "item"


class SemanticEntry(BaseModel):
    """单条语义记忆 —— 从情景记忆中提炼的抽象认知。"""
    statement: str = Field(..., description="自然语言陈述")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="信念强度")
    category: SemanticCategory = Field(default=SemanticCategory.RULE)
    source_events: List[str] = Field(
        default_factory=list, description="来源事件 ID"
    )
    created_day: int = Field(default=1, ge=1, le=60)
    embedding: List[float] = Field(
        default_factory=list, description="向量（128 或 256 维）"
    )


class SemanticMemory(BaseModel):
    """NPC 的语义记忆存储。"""
    npc_id: str
    entries: List[SemanticEntry] = Field(default_factory=list)
    pending_episodic: List[str] = Field(
        default_factory=list, description="待处理的情景记忆 ID"
    )
    last_extraction_day: int = Field(default=0)
    last_graph_extraction_day: int = Field(default=0)


# ═══════════════════════════════════════════════════
# 知识图谱
# ═══════════════════════════════════════════════════

class Entity(BaseModel):
    """知识图谱的节点。"""
    name: str
    type: str          # "person" | "location" | "concept" | "item"
    mentions: int = Field(default=0, description="被语义记忆提到的次数")


class Relation(BaseModel):
    """知识图谱的边（三元组）。"""
    subject: str
    predicate: str     # 动词描述
    object: str
    source_statement: str = ""   # 来源语义记忆
    frequency: int = Field(default=1, ge=1)


class KnowledgeGraph(BaseModel):
    """单个 NPC 的知识图谱。"""
    npc_id: str
    entities: Dict[str, Entity] = Field(default_factory=dict)
    relations: List[Relation] = Field(default_factory=list)


# ═══════════════════════════════════════════════════
# 检索上下文与结果
# ═══════════════════════════════════════════════════

class RetrievalContext(BaseModel):
    """检索输入 —— 当前情境。"""
    location: str = ""
    emotion: str = ""
    current_goal: str = ""
    day: int = 1
    slot: str = "morning"
    context_entities: List[str] = Field(
        default_factory=list,
        description="从情境中提取的实体列表（LLM 或规则提取）"
    )
    query_text: str = ""
    query_embedding: Optional[List[float]] = None


class ScoredEntry(BaseModel):
    """检索命中项。"""
    memory_id: str = ""
    description: str = ""
    vector_score: float = 0.0
    graph_score: float = 0.0
    final_score: float = 0.0
    source: str = ""    # "vector" | "graph" | "both"


class RetrievalResult(BaseModel):
    """三层检索输出。"""
    working_memory: Dict = Field(default_factory=dict)
    episodic_entries: List[ScoredEntry] = Field(default_factory=list)
    semantic_entries: List[ScoredEntry] = Field(default_factory=list)


# ═══════════════════════════════════════════════════
# NPC 完整视图（聚合三层）
# ═══════════════════════════════════════════════════

class NpcSnapshot(BaseModel):
    """NPC 完整快照 —— 供前端一次性获取。"""
    static: NpcStatic
    dynamic: NpcDynamic
    memory_summary: Dict = Field(
        default_factory=dict,
        description="记忆摘要，不传全量 event_chain",
    )


class NpcListResponse(BaseModel):
    """所有 NPC 快照列表响应。"""
    npcs: List[NpcSnapshot]
    total: int
