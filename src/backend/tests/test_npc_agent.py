"""NPC Agent 模块测试。

覆盖：
- static: Demo NPC 构建
- dynamic: 状态变更、delta 追踪、钳制
- memory: 记忆记录、关键记忆、印象、溢出处理
- templates: Prompt 生成、性格描述
- agent: think/respond（LLM 兜底）、状态更新、快照、序列化
- manager: 创建、查询、批量操作、序列化往返
"""

import asyncio
import pytest

from src.backend.models.npc import (
    AgentTier,
    Emotion,
    Location,
    NpcSnapshot,
    Personality,
    Slot,
)
from src.backend.ai.npc_agent.static import (
    build_static,
    demo_lin_chaoyin,
    demo_chen_yuanzhou,
    demo_npcs,
)
from src.backend.ai.npc_agent.dynamic import (
    DynamicDelta,
    DynamicState,
    create_initial_dynamic,
)
from src.backend.ai.npc_agent.memory import (
    DEFAULT_CONFIG,
    MAX_EVENT_CHAIN,
    IMPORTANCE_THRESHOLD,
    BaseVectorStore,
    EmbeddingVectorStore,
    EpisodicHit,
    EpisodicRetrieval,
    MemoryStore,
    MemorySummary,
    StructMemoryStore,
    TfidfVectorStore,
    VectorMemoryStore,
    create_vector_store,
)
from src.backend.ai.npc_agent.templates import (
    build_system_prompt,
    build_decision_prompt,
    _describe_personality,
)
from src.backend.ai.npc_agent.agent import NpcAgent, LLMClient
from src.backend.ai.npc_agent.manager import AgentManager
from src.backend.ai.npc_agent.semantic import (
    SemanticRetriever,
    SemanticStore,
    graph_one_hop,
    graph_two_hop,
    graph_distance,
)
from src.backend.ai.npc_agent.retrieval import RetrievalPipeline, retrieval_result_to_context
from src.backend.models.npc import (
    Entity,
    KnowledgeGraph,
    Relation,
    RetrievalContext,
    RetrievalResult,
    ScoredEntry,
    SemanticCategory,
    SemanticEntry,
)


# ═══════════════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════════════

def _sync_think(agent, day, slot):
    """同步包装 async think()。"""
    return asyncio.run(agent.think(day, slot))


def _sync_respond(agent, context, speaker="某人"):
    """同步包装 async respond()。"""
    return asyncio.run(agent.respond(context, speaker))


# ═══════════════════════════════════════════════════════
# static
# ═══════════════════════════════════════════════════════

class TestStatic:
    def test_demo_lin_chaoyin_valid(self):
        c = demo_lin_chaoyin()
        assert c.id == "lin_chaoyin"
        assert c.name == "林潮音"
        assert c.age == 17
        assert c.tier == AgentTier.S
        assert c.attributes.mind == 8
        assert c.personality.kindness == 0.8

    def test_demo_chen_yuanzhou_valid(self):
        c = demo_chen_yuanzhou()
        assert c.id == "chen_yuanzhou"
        assert c.name == "陈远舟"
        assert c.age == 18
        assert c.tier == AgentTier.S
        assert c.core_wish.startswith("考上大学")

    def test_demo_npcs_returns_two(self):
        npcs = demo_npcs()
        assert len(npcs) == 2

    def test_build_static_from_dict(self):
        data = {
            "id": "test_npc",
            "name": "测试",
            "age": 25,
            "occupation": "测试职业",
            "tier": "A",
            "background": "测试背景",
            "attributes": {"mind": 5, "faith": 6, "physique": 7, "charm": 8},
            "personality": {"kindness": 0.6},
            "core_wish": "测试愿望",
        }
        s = build_static(data)
        assert s.id == "test_npc"
        assert s.attributes.physique == 7
        assert s.personality.kindness == 0.6

    def test_build_static_defaults(self):
        s = build_static({"id": "x", "name": "y", "age": 30, "occupation": "z"})
        assert s.tier == AgentTier.A       # default tier
        assert s.attributes.mind == 5       # default attr
        assert s.personality.kindness == 0.5


# ═══════════════════════════════════════════════════════
# dynamic
# ═══════════════════════════════════════════════════════

class TestDynamic:
    def test_default_state(self):
        d = DynamicState()
        assert d.current.location == Location.RESIDENCE
        assert d.current.happiness == 50
        assert d.current.energy == 100
        assert d.current.emotion == Emotion.NEUTRAL

    def test_set_happiness_clamps(self):
        d = DynamicState()
        d.set_happiness("test", 200, "test")    # 50+200→100
        assert d.current.happiness == 100
        d.set_happiness("test", -200, "test")   # 100-200→0
        assert d.current.happiness == 0

    def test_delta_tracking(self):
        d = DynamicState()
        d.set_happiness("a", -10, "evt_001")
        d.set_emotion("a", Emotion.SAD, "evt_001")
        d.set_location("a", Location.BEACH, "去海边")

        deltas = d.deltas
        assert len(deltas) == 3
        assert deltas[0].field == "happiness"
        assert deltas[0].new_value == 40
        # deltas 读取后清空
        assert len(d.deltas) == 0

    def test_set_karma_main_clamps_0_100(self):
        d = DynamicState()
        d.set_karma_main("test", 150)
        assert d.current.karma_main_progress == 100.0
        d.set_karma_main("test", -10)
        assert d.current.karma_main_progress == 0.0

    def test_serialize_roundtrip(self):
        d = DynamicState()
        d.set_happiness("a", 10, "happy")
        data = d.to_dict()
        restored = DynamicState.from_dict(data)
        assert restored.current.happiness == 60

    def test_create_initial_dynamic_with_location(self):
        d = create_initial_dynamic(Location.SCHOOL)
        assert d.current.location == Location.SCHOOL


# ═══════════════════════════════════════════════════════
# memory
# ═══════════════════════════════════════════════════════

class TestMemory:
    def test_remember_basic(self):
        m = MemoryStore("test_npc")
        entry = m.remember(day=1, slot=Slot.MORNING, description="醒来",
                           importance=5, emotion=Emotion.CALM)
        assert m.event_count == 1
        assert entry.day == 1
        assert entry.description == "醒来"

    def test_high_importance_becomes_key_memory(self):
        m = MemoryStore("test_npc")
        m.remember(day=1, slot=Slot.NOON, description="大事",
                   importance=9, emotion=Emotion.HAPPY)
        assert m.key_count == 1
        assert m.event_count == 1

    def test_low_importance_not_key(self):
        m = MemoryStore("test_npc")
        m.remember(day=1, slot=Slot.NOON, description="小事",
                   importance=3, emotion=Emotion.NEUTRAL)
        assert m.key_count == 0

    def test_recent_events_ordered(self):
        m = MemoryStore("test_npc")
        for i in range(5):
            m.remember(day=i + 1, slot=Slot.MORNING, description=f"事件{i}",
                       importance=4)
        recent = m.recent_events(3)
        assert len(recent) == 3
        # 按 day 降序排列：[5, 4, 3]
        assert recent[0].day == 5   # 最新
        assert recent[-1].day == 3  # 最久（3条中）

    def test_top_key_memories_sorted(self):
        m = MemoryStore("test_npc")
        for imp in [3, 9, 7, 8, 6]:
            m.remember(day=1, slot=Slot.NOON, description=f"imp{imp}",
                       importance=imp)
        top = m.top_key_memories(3)
        # importance >= 7: 9, 7, 8 → sorted desc → 9, 8, 7
        assert top[0].importance == 9
        assert top[1].importance == 8
        assert top[2].importance == 7

    def test_overflow_compaction(self):
        m = MemoryStore("test_npc")
        # 添加 200 条记忆，确保多次触发溢出
        for i in range(200):
            m.remember(day=1, slot=Slot.MORNING, description=f"事件{i}",
                       importance=5)
        # 200 条记忆被压缩到 50 以下（远小于 200）
        assert m.event_count < 50
        # 至少触发 3 次溢出
        assert m.overflow_count >= 3

    def test_impression_set_and_get(self):
        m = MemoryStore("test_npc")
        m.set_impression("other", affinity=70, trust=80, label="爱慕")
        imp = m.get_impression("other")
        assert imp is not None
        assert imp.affinity == 70
        assert imp.label == "爱慕"

    def test_impression_update_delta(self):
        m = MemoryStore("test_npc")
        m.update_impression("other", affinity_delta=10, trust_delta=-5)
        imp = m.get_impression("other")
        assert imp.affinity == 60   # 50 + 10
        assert imp.trust == 45      # 50 - 5

    def test_impression_first_encounter(self):
        """首次印象：不存在时自动创建，从 50 开始加减。"""
        m = MemoryStore("test_npc")
        m.update_impression("stranger", affinity_delta=-10)
        imp = m.get_impression("stranger")
        assert imp.affinity == 40  # 50 - 10

    def test_context_for_llm(self):
        m = MemoryStore("test_npc")
        m.remember(day=5, slot=Slot.NIGHT, description="陈远舟告白了",
                   importance=9, emotion=Emotion.EXCITED)
        m.set_impression("chen_yuanzhou", affinity=85, trust=70, label="爱慕")
        ctx = m.context_for_llm(current_day=5)
        assert "陈远舟" in ctx
        assert "爱慕" in ctx

    def test_serialize_roundtrip(self):
        m = MemoryStore("test_npc")
        m.remember(day=1, slot=Slot.MORNING, description="醒来",
                   importance=7, emotion=Emotion.CALM)
        m.set_impression("other", affinity=60, label="朋友")
        data = m.to_dict()
        restored = MemoryStore.from_dict(data)
        assert restored.event_count == 1
        imp = restored.get_impression("other")
        assert imp.label == "朋友"


# ═══════════════════════════════════════════════════════
# memory — 双库 + 检索公式 + TF-IDF
# ═══════════════════════════════════════════════════════

class TestStructMemoryStore:
    def test_put_and_get(self):
        s = StructMemoryStore()
        entry = MemoryStore("test").remember(day=1, slot=Slot.MORNING, description="test")
        s.put(entry)
        assert s.count() == 1
        assert s.get(entry.memory_id) is not None

    def test_by_day_range(self):
        s = StructMemoryStore()
        for d in [1, 3, 5, 7, 10]:
            entry = MemoryStore("test").remember(day=d, slot=Slot.MORNING, description=f"d{d}")
            s.put(entry)
        results = s.by_day_range(from_day=3, to_day=7)
        assert len(results) == 3  # 3, 5, 7

    def test_by_participant(self):
        s = StructMemoryStore()
        e1 = MemoryStore("test").remember(day=1, slot=Slot.MORNING, description="A",
                                          participants=["alice", "bob"])
        e2 = MemoryStore("test").remember(day=2, slot=Slot.MORNING, description="B",
                                          participants=["charlie"])
        s.put(e1); s.put(e2)
        assert len(s.by_participant("alice")) == 1
        assert len(s.by_participant("charlie")) == 1
        assert len(s.by_participant("nobody")) == 0

    def test_by_location(self):
        s = StructMemoryStore()
        e1 = MemoryStore("test").remember(day=1, slot=Slot.MORNING, description="A",
                                          location="temple")
        e2 = MemoryStore("test").remember(day=2, slot=Slot.MORNING, description="B",
                                          location="school")
        s.put(e1); s.put(e2)
        assert len(s.by_location("temple")) == 1
        assert len(s.by_location("beach")) == 0

    def test_today(self):
        s = StructMemoryStore()
        for d in [1, 1, 2, 3]:
            entry = MemoryStore("test").remember(day=d, slot=Slot.MORNING, description=f"d{d}")
            s.put(entry)
        assert len(s.today(day=1)) == 2
        assert len(s.today(day=5)) == 0

    def test_serialize_roundtrip(self):
        s = StructMemoryStore()
        entry = MemoryStore("test").remember(day=5, slot=Slot.NOON, description="test",
                                             importance=8, participants=["a", "b"])
        s.put(entry)
        data = s.to_list()
        restored = StructMemoryStore.from_list(data)
        assert restored.count() == 1
        r = restored.get(entry.memory_id)
        assert r.importance == 8
        assert r.participants == ["a", "b"]


class TestVectorMemoryStore:
    def test_put_and_get(self):
        v = VectorMemoryStore()
        v.put("mem_001", [0.1, 0.2, 0.3])
        assert v.get("mem_001") == [0.1, 0.2, 0.3]
        assert v.count() == 1

    def test_compute_similarity_stub(self):
        """无 embedding 时返回桩值 0.5。"""
        v = VectorMemoryStore()
        v.put("mem_001", [])
        score = v.compute_similarity("mem_001")
        assert score == 0.5

    def test_compute_cosine_similarity(self):
        v = VectorMemoryStore()
        v.put("mem_a", [1.0, 0.0])
        v.put("mem_b", [0.0, 1.0])
        v.put("mem_c", [1.0, 0.0])

        # identical → ~1.0
        a_vs_c = v.compute_similarity("mem_a", query_embedding=[1.0, 0.0])
        assert abs(a_vs_c - 1.0) < 0.01

        # orthogonal → ~0.0
        a_vs_b = v.compute_similarity("mem_a", query_embedding=[0.0, 1.0])
        assert abs(a_vs_b - 0.0) < 0.01

    def test_missing_memory_returns_stub(self):
        v = VectorMemoryStore()
        score = v.compute_similarity("nonexistent")
        assert score == 0.5

    def test_serialize_roundtrip(self):
        v = VectorMemoryStore()
        v.put("mem_001", [0.5, 0.5])
        v.put("mem_002", [0.1])
        data = v.to_dict()
        restored = VectorMemoryStore.from_dict(data)
        assert restored.count() == 2
        assert restored.get("mem_001") == [0.5, 0.5]


class TestTfidfVectorStore:
    def test_put_and_get(self):
        v = TfidfVectorStore()
        v.put("mem_001", description="巫女候选在寺庙被推举")
        assert v.count() == 1

    def test_same_topic_high_similarity(self):
        v = TfidfVectorStore()
        v.put("mem_001", description="慧圆在寺庙推举林潮音为巫女候选")
        v.put("mem_002", description="陈远舟在海边散步买了早餐")

        # 查询和 mem_001 同主题 → 高分
        score1 = v.compute_similarity("mem_001", query_text="巫女候选寺庙推举")
        # 查询和 mem_002 不同主题 → 低分
        score2 = v.compute_similarity("mem_002", query_text="巫女候选寺庙推举")

        assert score1 > score2  # 同主题得分更高

    def test_partial_match(self):
        v = TfidfVectorStore()
        v.put("mem_a", description="成为巫女意味着无法离开小镇")
        v.put("mem_b", description="江雪仪开的药会让人头晕")

        s_a = v.compute_similarity("mem_a", query_text="巫女小镇命运")
        s_b = v.compute_similarity("mem_b", query_text="巫女小镇命运")

        assert s_a > s_b

    def test_empty_query_returns_default(self):
        v = TfidfVectorStore()
        v.put("mem_001", description="测试记忆")
        score = v.compute_similarity("mem_001", query_text="")
        assert score == 0.5

    def test_remove(self):
        v = TfidfVectorStore()
        v.put("mem_001", description="测试")
        assert v.count() == 1
        assert v.remove("mem_001")
        assert v.count() == 0

    def test_serialize_roundtrip(self):
        v = TfidfVectorStore()
        v.put("mem_001", description="巫女候选")
        v.put("mem_002", description="离岛梦想")
        data = v.to_dict()
        restored = TfidfVectorStore.from_dict(data)
        assert restored.count() == 2
        # 验证检索功能仍正常
        score = restored.compute_similarity("mem_001", query_text="巫女候选")
        assert score > 0.5


class TestVectorStoreFactory:
    def test_default_is_tfidf(self):
        v = create_vector_store()
        assert isinstance(v, TfidfVectorStore)

    def test_tfidf_backend(self):
        v = create_vector_store(backend="tfidf")
        assert isinstance(v, TfidfVectorStore)

    def test_embedding_backend(self):
        v = create_vector_store(backend="embedding")
        assert isinstance(v, EmbeddingVectorStore)


class TestEpisodicRetrieval:
    def _make_entry(self, store: StructMemoryStore, day: int, description: str,
                    importance: int = 5):
        """Helper: create entry and put into struct store + vector store."""
        mem_store = MemoryStore("test")
        entry = mem_store.remember(day=day, slot=Slot.MORNING, description=description,
                                   importance=importance)
        store.put(entry)
        return entry

    def test_retrieve_returns_hits(self):
        struct = StructMemoryStore()
        vector = VectorMemoryStore()
        retrieval = EpisodicRetrieval()

        self._make_entry(struct, day=10, description="重要事件", importance=9)
        self._make_entry(struct, day=15, description="日常事件", importance=4)

        hits = retrieval.retrieve(struct, vector, current_day=15)
        assert len(hits) == 2
        # 重要性高的排前面
        assert hits[0].entry.importance >= hits[1].entry.importance

    def test_recency_decay(self):
        """同重要性下，越近的得分越高。"""
        struct = StructMemoryStore()
        vector = VectorMemoryStore()
        retrieval = EpisodicRetrieval()

        self._make_entry(struct, day=5, description="old", importance=5)
        self._make_entry(struct, day=14, description="recent", importance=5)

        hits = retrieval.retrieve(struct, vector, current_day=15)
        assert hits[0].entry.description == "recent"   # 最近排前

    def test_importance_overpowers_recency(self):
        """足够重要的事件，即使久远也排在前面。"""
        struct = StructMemoryStore()
        vector = VectorMemoryStore()
        retrieval = EpisodicRetrieval({"base_decay": 30.0})

        self._make_entry(struct, day=5, description="人生转折", importance=10)
        self._make_entry(struct, day=14, description="琐事", importance=3)

        hits = retrieval.retrieve(struct, vector, current_day=15)
        # imp=10 且 10天前 → 仍应排第一
        assert hits[0].entry.description == "人生转折"

    def test_threshold_filter(self):
        """得分低于阈值的被丢弃。"""
        struct = StructMemoryStore()
        vector = VectorMemoryStore()
        retrieval = EpisodicRetrieval({"threshold": 0.5})

        self._make_entry(struct, day=14, description="high", importance=10)
        self._make_entry(struct, day=1, description="low", importance=1)

        hits = retrieval.retrieve(struct, vector, current_day=60)
        # high: imp=10, 46天前 → 得分 ~0.53 > 0.5 → 保留
        # low: imp=1, 59天前 → 得分极低 → 被过滤
        assert len(hits) == 1
        assert hits[0].entry.description == "high"

    def test_location_filter(self):
        struct = StructMemoryStore()
        vector = VectorMemoryStore()
        retrieval = EpisodicRetrieval()

        m = MemoryStore("test")
        e1 = m.remember(day=10, slot=Slot.MORNING, description="temple event", location="temple")
        e2 = m.remember(day=10, slot=Slot.NOON, description="school event", location="school")
        struct.put(e1); struct.put(e2)
        vector.put(e1.memory_id); vector.put(e2.memory_id)

        hits = retrieval.retrieve(struct, vector, current_day=10, location_filter="temple")
        assert len(hits) == 1
        assert hits[0].entry.description == "temple event"

    def test_participant_filter(self):
        struct = StructMemoryStore()
        vector = VectorMemoryStore()
        retrieval = EpisodicRetrieval()

        m = MemoryStore("test")
        e1 = m.remember(day=10, slot=Slot.MORNING, description="with alice",
                        participants=["alice"])
        e2 = m.remember(day=10, slot=Slot.NOON, description="with bob",
                        participants=["bob"])
        struct.put(e1); struct.put(e2)
        vector.put(e1.memory_id); vector.put(e2.memory_id)

        hits = retrieval.retrieve(struct, vector, current_day=10, participant_filter="alice")
        assert len(hits) == 1
        assert hits[0].entry.description == "with alice"

    def test_top_k_limit(self):
        struct = StructMemoryStore()
        vector = VectorMemoryStore()
        retrieval = EpisodicRetrieval({"top_k": 3})

        for i in range(10):
            self._make_entry(struct, day=i + 1, description=f"event{i}", importance=5)

        hits = retrieval.retrieve(struct, vector, current_day=10)
        assert len(hits) == 3  # Top K 限制

    def test_new_memory_entry_has_memory_id(self):
        """新 MemoryEntry 自动生成 memory_id。"""
        entry = MemoryStore("test").remember(day=1, slot=Slot.MORNING, description="test")
        assert entry.memory_id is not None
        assert len(entry.memory_id) == 12  # hex[:12]


# ═══════════════════════════════════════════════════════
# semantic — 语义记忆 + 知识图谱 + 检索
# ═══════════════════════════════════════════════════════

class TestGraphTraversal:
    def _make_graph(self):
        """创建测试图谱：寺庙→慧圆→巫女→小镇。"""
        return KnowledgeGraph(
            npc_id="test",
            entities={
                "慧圆": Entity(name="慧圆", type="person", mentions=3),
                "寺庙": Entity(name="寺庙", type="location", mentions=5),
                "巫女": Entity(name="巫女", type="concept", mentions=4),
                "小镇": Entity(name="小镇", type="location", mentions=3),
                "林潮音": Entity(name="林潮音", type="person", mentions=2),
            },
            relations=[
                Relation(subject="慧圆", predicate="管理", object="寺庙", frequency=2),
                Relation(subject="慧圆", predicate="推举", object="巫女", frequency=1),
                Relation(subject="巫女", predicate="绑定", object="小镇", frequency=1),
                Relation(subject="林潮音", predicate="成为", object="巫女", frequency=1),
            ],
        )

    def test_one_hop(self):
        g = self._make_graph()
        hits = graph_one_hop("寺庙", g.relations)
        assert len(hits) == 1
        assert hits[0].predicate == "管理"

    def test_two_hop(self):
        g = self._make_graph()
        hits = graph_two_hop("寺庙", g.relations)
        # 寺庙→慧圆→巫女 via 推举, 巫女→...
        assert len(hits) >= 2

    def test_distance_direct(self):
        g = self._make_graph()
        assert graph_distance("慧圆", "寺庙", g.relations) == 1

    def test_distance_indirect(self):
        g = self._make_graph()
        # 寺庙→慧圆→巫女 = 2 跳
        assert graph_distance("寺庙", "巫女", g.relations) == 2

    def test_distance_self(self):
        g = self._make_graph()
        assert graph_distance("寺庙", "寺庙", g.relations) == 0

    def test_distance_unreachable(self):
        g = self._make_graph()
        d = graph_distance("寺庙", "火星", g.relations, max_hops=3)
        assert d > 3  # 不可达


class TestSemanticStore:
    def test_add_entry(self):
        s = SemanticStore("test")
        s.add("成为巫女意味着无法离开小镇", category=SemanticCategory.RULE, confidence=0.6)
        assert s.entry_count == 1
        assert s.entries[0].statement == "成为巫女意味着无法离开小镇"

    def test_add_with_entities_and_relations(self):
        s = SemanticStore("test")
        s.add(
            "慧圆在寺庙推举林潮音为巫女候选",
            category=SemanticCategory.PERSON,
            entities=[
                {"name": "慧圆", "type": "person"},
                {"name": "寺庙", "type": "location"},
                {"name": "巫女", "type": "concept"},
            ],
            relations=[
                {"subject": "慧圆", "predicate": "推举", "object": "巫女"},
                {"subject": "慧圆", "predicate": "管理", "object": "寺庙"},
            ],
        )
        assert s.entry_count == 1
        assert len(s.graph.entities) == 3
        assert len(s.graph.relations) == 2

    def test_update_confidence(self):
        s = SemanticStore("test")
        s.add("test", confidence=0.5)
        assert s.update_confidence("test", +0.2)
        assert s.entries[0].confidence == 0.7
        assert s.update_confidence("test", -0.5)
        assert abs(s.entries[0].confidence - 0.2) < 0.001

    def test_by_category(self):
        s = SemanticStore("test")
        s.add("关于人的认知", category=SemanticCategory.PERSON)
        s.add("关于地点的认知", category=SemanticCategory.LOCATION)
        assert len(s.by_category(SemanticCategory.PERSON)) == 1

    def test_serialize_roundtrip(self):
        s = SemanticStore("test_npc")
        s.add("成为巫女意味着无法离开小镇",
              category=SemanticCategory.RULE, confidence=0.7,
              entities=[{"name": "巫女", "type": "concept"}],
              relations=[{"subject": "巫女", "predicate": "绑定", "object": "小镇"}])
        data = s.to_dict()
        restored = SemanticStore.from_dict(data)
        assert restored.entry_count == 1
        assert restored.entries[0].statement == "成为巫女意味着无法离开小镇"
        assert "巫女" in restored.graph.entities

    def test_mark_episodic_processed(self):
        s = SemanticStore("test")
        s.mark_episodic_processed("evt_001")
        s.mark_episodic_processed("evt_002")
        assert len(s.pending_episodic) == 2

    def test_should_extract_threshold(self):
        s = SemanticStore("test", config={"episodic_pending_threshold": 5})
        for i in range(5):
            s.mark_episodic_processed(f"evt_{i}")
        assert s.should_extract_from_episodic()

    def test_should_extract_below_threshold(self):
        s = SemanticStore("test", config={"episodic_pending_threshold": 5})
        for i in range(3):
            s.mark_episodic_processed(f"evt_{i}")
        assert not s.should_extract_from_episodic()


class TestSemanticRetriever:
    def _make_entries_and_graph(self):
        entries = [
            SemanticEntry(statement="成为巫女意味着无法离开小镇",
                          category=SemanticCategory.RULE, confidence=0.7),
            SemanticEntry(statement="慧圆对巫女的事非常认真",
                          category=SemanticCategory.PERSON, confidence=0.6),
            SemanticEntry(statement="陈远舟一直想带她离开小镇",
                          category=SemanticCategory.PERSON, confidence=0.8),
            SemanticEntry(statement="江雪仪开的药会让人头晕",
                          category=SemanticCategory.ITEM, confidence=0.4),
        ]
        graph = KnowledgeGraph(
            npc_id="test",
            entities={
                "巫女": Entity(name="巫女", type="concept"),
                "慧圆": Entity(name="慧圆", type="person"),
                "陈远舟": Entity(name="陈远舟", type="person"),
                "小镇": Entity(name="小镇", type="location"),
            },
            relations=[
                Relation(subject="慧圆", predicate="推举", object="巫女"),
                Relation(subject="巫女", predicate="绑定", object="小镇"),
                Relation(subject="陈远舟", predicate="想离开", object="小镇"),
            ],
        )
        return entries, graph

    def test_vector_only_hits(self):
        """无图谱时，只靠文本相似度。"""
        entries, graph = self._make_entries_and_graph()
        retriever = SemanticRetriever({"alpha": 1.0, "beta": 0.0})
        ctx = RetrievalContext(query_text="巫女小镇命运")
        hits = retriever.retrieve(entries, graph, ctx)
        assert len(hits) > 0
        assert "巫女" in hits[0].description

    def test_graph_only_hits(self):
        """纯图谱检索。"""
        entries, graph = self._make_entries_and_graph()
        retriever = SemanticRetriever({"alpha": 0.0, "beta": 1.0})
        ctx = RetrievalContext(context_entities=["巫女"])
        hits = retriever.retrieve(entries, graph, ctx)
        assert len(hits) > 0

    def test_confidence_filter(self):
        entries, graph = self._make_entries_and_graph()
        retriever = SemanticRetriever({"confidence_min": 0.5})
        ctx = RetrievalContext(query_text="药头晕")
        hits = retriever.retrieve(entries, graph, ctx)
        # "江雪仪开的药让人头晕" confidence=0.4 < 0.5 → 被过滤
        statements = [h.description for h in hits]
        assert "江雪仪开的药会让人头晕" not in statements

    def test_top_n_limit(self):
        entries, graph = self._make_entries_and_graph()
        retriever = SemanticRetriever({"final_top_n": 2, "alpha": 1.0, "beta": 0.0})
        ctx = RetrievalContext(query_text="巫女小镇命运离开")
        hits = retriever.retrieve(entries, graph, ctx)
        assert len(hits) <= 2


class TestRetrievalPipeline:
    def test_pipeline_runs(self):
        """管道不崩溃，能返回三层结果。"""
        s = SemanticStore("test_npc")
        s.add("成为巫女意味着无法离开小镇", category=SemanticCategory.RULE)
        s.add("陈远舟值得信赖", category=SemanticCategory.PERSON)

        memory = MemoryStore("test_npc")
        memory.remember(day=10, slot=Slot.MORNING, description="慧圆推举巫女",
                        importance=9, participants=["慧圆", "林潮音"],
                        location="temple")

        from src.backend.models.npc import NpcDynamic
        dyn = NpcDynamic(location="temple", emotion="anxious",
                         current_goal="决定是否成为巫女", happiness=40, energy=60)

        pipeline = RetrievalPipeline()
        result = pipeline.retrieve(
            memory=memory, semantic=s, dynamic=dyn,
            day=15, slot=Slot.NOON,
        )

        assert isinstance(result, RetrievalResult)
        assert result.working_memory["location"] == "temple"
        assert len(result.episodic_entries) >= 0  # 阈值过滤可能为空
        assert len(result.semantic_entries) >= 1

    def test_retrieval_result_to_context(self):
        """结果转上下文文本不崩溃。"""
        result = RetrievalResult(
            working_memory={"location": "temple", "emotion": "anxious",
                           "current_goal": "test", "current_time": "Day 5 morning"},
            episodic_entries=[
                ScoredEntry(description="巫女被推举", final_score=0.9, source="vector"),
            ],
            semantic_entries=[
                ScoredEntry(description="成为巫女=无法离开", final_score=0.85, source="both"),
            ],
        )
        ctx = retrieval_result_to_context(result)
        assert "temple" in ctx
        assert "巫女被推举" in ctx
        assert "无法离开" in ctx

class TestTemplates:
    def test_personality_high_kindness(self):
        p = _describe_personality(Personality(kindness=0.8))
        assert "善良" in p

    def test_personality_high_aggression(self):
        p = _describe_personality(Personality(aggression=0.8))
        assert "激进" in p

    def test_build_system_prompt_contains_basics(self):
        static = demo_lin_chaoyin()
        prompt = build_system_prompt(static)
        assert "林潮音" in prompt
        assert "归潮镇" in prompt
        assert "高中生" in prompt
        assert "行为规则" in prompt

    def test_build_decision_prompt_ends_with_instruction(self):
        static = demo_lin_chaoyin()
        prompt = build_decision_prompt(
            static, "无记忆", "学校", "平静", 100, 50
        )
        assert "行动描述" in prompt
        assert "15字以内" in prompt

    def test_both_npcs_get_different_prompts(self):
        c = demo_lin_chaoyin()
        y = demo_chen_yuanzhou()
        pc = build_system_prompt(c)
        py_ = build_system_prompt(y)
        assert "林潮音" in pc
        assert "陈远舟" in py_
        assert pc != py_


# ═══════════════════════════════════════════════════════
# agent
# ═══════════════════════════════════════════════════════

class TestAgent:
    def test_create_with_defaults(self):
        static = demo_lin_chaoyin()
        agent = NpcAgent(static=static)
        assert agent.npc_id == "lin_chaoyin"
        assert agent.name == "林潮音"
        assert agent.tier == AgentTier.S
        assert agent.location == Location.RESIDENCE

    def test_create_with_custom_state(self):
        static = demo_lin_chaoyin()
        dyn = create_initial_dynamic(Location.SCHOOL)
        agent = NpcAgent(static=static, dynamic=dyn)
        assert agent.location == Location.SCHOOL

    def test_think_llm_fallback(self):
        """LLM 桩返回空 → 走规则兜底。"""
        static = demo_lin_chaoyin()
        agent = NpcAgent(static=static)
        agent.set_location(Location.SCHOOL)
        action = _sync_think(agent, day=1, slot=Slot.MORNING)
        assert "school" in action   # Location 枚举值为英文

    def test_respond_llm_fallback(self):
        """LLM 桩返回空 → 走规则兜底。"""
        static = demo_lin_chaoyin()
        agent = NpcAgent(static=static)
        reply = _sync_respond(agent, "你好吗", speaker="陈远舟")
        assert isinstance(reply, str)
        assert len(reply) > 0

    def test_remember_delegation(self):
        static = demo_lin_chaoyin()
        agent = NpcAgent(static=static)
        agent.remember(day=3, slot=Slot.NIGHT, description="做了一个梦",
                       importance=8, emotion=Emotion.ANXIOUS)
        assert agent.memory.event_count == 1
        assert agent.memory.key_count == 1

    def test_set_happiness_and_emotion(self):
        static = demo_lin_chaoyin()
        agent = NpcAgent(static=static)
        agent.set_happiness(-20, "bad day")
        agent.set_emotion(Emotion.SAD, "sad")
        assert agent.dynamic.current.happiness == 30
        assert agent.emotion == Emotion.SAD

    def test_snapshot_structure(self):
        static = demo_lin_chaoyin()
        agent = NpcAgent(static=static)
        snap = agent.snapshot()
        assert isinstance(snap, NpcSnapshot)
        assert snap.static.id == "lin_chaoyin"
        assert "event_count" in snap.memory_summary

    def test_serialize_roundtrip(self):
        static = demo_lin_chaoyin()
        agent = NpcAgent(static=static)
        agent.set_happiness(10, "happy")
        agent.remember(day=1, slot=Slot.MORNING, description="test",
                       importance=7)

        data = agent.to_dict()
        restored = NpcAgent.from_dict(data, static)
        assert restored.dynamic.current.happiness == 60
        assert restored.memory.event_count == 1

    def test_different_npcs_have_different_memories(self):
        c = NpcAgent(static=demo_lin_chaoyin())
        y = NpcAgent(static=demo_chen_yuanzhou())
        c.remember(day=1, slot=Slot.MORNING, description="林潮音的记忆",
                   importance=5)
        y.remember(day=1, slot=Slot.MORNING, description="陈远舟的记忆",
                   importance=5)
        assert c.memory.event_count == 1
        assert y.memory.event_count == 1
        assert "林潮音" in c.memory.recent_events(1)[0].description
        assert "陈远舟" in y.memory.recent_events(1)[0].description


# ═══════════════════════════════════════════════════════
# manager
# ═══════════════════════════════════════════════════════

class TestManager:
    def test_init_from_demo(self):
        m = AgentManager()
        m.init_from_demo()
        assert m.count == 2
        assert m.get("lin_chaoyin") is not None
        assert m.get("chen_yuanzhou") is not None

    def test_add_duplicate_raises(self):
        m = AgentManager()
        m.add_from_static(demo_lin_chaoyin())
        with pytest.raises(ValueError):
            m.add_from_static(demo_lin_chaoyin())

    def test_list_by_tier(self):
        m = AgentManager()
        m.init_from_demo()
        s_tier = m.list_by_tier(AgentTier.S)
        assert len(s_tier) == 2
        b_tier = m.list_by_tier(AgentTier.B)
        assert len(b_tier) == 0

    def test_list_at_location(self):
        m = AgentManager()
        m.init_from_demo()
        c = m.get("lin_chaoyin")
        c.set_location(Location.BEACH)
        at_beach = m.list_at_location(Location.BEACH)
        assert len(at_beach) == 1
        assert at_beach[0].npc_id == "lin_chaoyin"

    def test_snapshot_individual(self):
        m = AgentManager()
        m.init_from_demo()
        snap = m.snapshot("lin_chaoyin")
        assert snap is not None
        assert snap.static.name == "林潮音"

    def test_snapshot_missing_returns_none(self):
        m = AgentManager()
        assert m.snapshot("nonexistent") is None

    def test_all_snapshots(self):
        m = AgentManager()
        m.init_from_demo()
        resp = m.all_snapshots()
        assert resp.total == 2
        assert len(resp.npcs) == 2

    def test_all_think_concurrent(self):
        """测试并发 think 不崩溃。"""
        async def _run():
            m = AgentManager()
            m.init_from_demo()
            return await m.all_think(day=1, slot=Slot.MORNING)
        actions = asyncio.run(_run())
        assert len(actions) == 2
        assert isinstance(actions["lin_chaoyin"], str)
        assert isinstance(actions["chen_yuanzhou"], str)

    def test_all_remember_batch(self):
        m = AgentManager()
        m.init_from_demo()
        m.all_remember(day=2, slot=Slot.NOON, event_descriptions={
            "lin_chaoyin": "事件A",
            "chen_yuanzhou": "事件B",
        }, importance=8)
        assert m.get("lin_chaoyin").memory.event_count == 1
        assert m.get("chen_yuanzhou").memory.event_count == 1

    def test_serialize_roundtrip(self):
        m = AgentManager()
        m.init_from_demo()
        m.get("lin_chaoyin").remember(day=1, slot=Slot.MORNING,
                                       description="test", importance=7)
        data = m.to_dict()
        static_map = {
            "lin_chaoyin": demo_lin_chaoyin(),
            "chen_yuanzhou": demo_chen_yuanzhou(),
        }
        restored = AgentManager.from_dict(data, static_map)
        assert restored.count == 2
        assert restored.get("lin_chaoyin").memory.event_count == 1

    def test_init_from_statics_list(self):
        m = AgentManager()
        m.init_from_statics(demo_npcs())
        assert m.count == 2

    def test_npc_ids(self):
        m = AgentManager()
        m.init_from_demo()
        ids = m.npc_ids
        assert "lin_chaoyin" in ids
        assert "chen_yuanzhou" in ids
