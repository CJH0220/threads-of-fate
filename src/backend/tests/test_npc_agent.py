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
    MAX_EVENT_CHAIN,
    IMPORTANCE_THRESHOLD,
    MemoryStore,
    MemorySummary,
)
from src.backend.ai.npc_agent.templates import (
    build_system_prompt,
    build_decision_prompt,
    _describe_personality,
)
from src.backend.ai.npc_agent.agent import NpcAgent, LLMClient
from src.backend.ai.npc_agent.manager import AgentManager


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
        assert recent[-1].day == 5

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
        ctx = m.context_for_llm()
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
# templates
# ═══════════════════════════════════════════════════════

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
