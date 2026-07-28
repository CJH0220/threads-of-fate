"""v2 架构测试 — 事件生成与玩家干预架构 v2。

Coverage:
- MemoryEntry: source / dream_incense_snapshot / dream_text 字段
- EventTemplate: dramatic_score 默认值与存取
- ScreenwriterResult: 数据类属性、事件分级过滤
- NPC Agent: receive_dream / _build_dream_context (香水分段语义)
- NPC Agent: fill_scene with player_context (赐福感知)
- MemoryStore: by_source() 按来源检索
- ws_game helpers: _build_blessing_slots
- screenwriter_think: Mock LLM 完整流程 (冲突分解析 + 时段摘要)
- Prompts: v2 字段存在性校验
"""

import asyncio
import json

import pytest

from src.backend.engine.event.event_types import EventTemplate, Outcome, SettlementResult
from src.backend.engine.story.story_types import (
    GlobalConstraints,
    OutcomeDef,
    StoryBeat,
    StoryOutline,
    StoryState,
)
from src.backend.models.npc import (
    Emotion,
    Location,
    MemoryEntry,
    NpcStatic,
    Personality,
    Slot,
)


# ═══════════════════════════════════════════════════
# 1. MemoryEntry v2 字段
# ═══════════════════════════════════════════════════

class TestMemoryEntryV2:
    """v2 MemoryEntry 新增字段测试。"""

    def test_source_default(self):
        m = MemoryEntry(day=1, slot=Slot.MORNING, description="test")
        assert m.source == "event"
        assert m.dream_incense_snapshot == 0
        assert m.dream_text == ""

    def test_source_explicit(self):
        for s in ["event", "dream", "blessing_felt", "ambient"]:
            m = MemoryEntry(day=1, slot=Slot.MORNING, description="test", source=s)
            assert m.source == s

    def test_dream_fields_set(self):
        m = MemoryEntry(
            day=5, slot=Slot.NIGHT, description="托梦记忆",
            source="dream", dream_incense_snapshot=72, dream_text="今晚别去港口",
        )
        assert m.source == "dream"
        assert m.dream_incense_snapshot == 72
        assert m.dream_text == "今晚别去港口"
        assert m.importance == 5  # default

    def test_dream_fields_default_to_zero_and_empty(self):
        m = MemoryEntry(day=1, slot=Slot.MORNING, description="普通事件", source="event")
        assert m.dream_incense_snapshot == 0
        assert m.dream_text == ""

    def test_memory_entry_serialization_roundtrip(self):
        m = MemoryEntry(
            day=7, slot=Slot.NIGHT, description="梦到神谕",
            importance=8, source="dream",
            dream_incense_snapshot=120, dream_text="去寺庙",
        )
        data = m.model_dump()
        restored = MemoryEntry(**data)
        assert restored.source == "dream"
        assert restored.dream_incense_snapshot == 120
        assert restored.dream_text == "去寺庙"
        assert restored.day == 7
        assert restored.importance == 8


# ═══════════════════════════════════════════════════
# 2. EventTemplate dramatic_score
# ═══════════════════════════════════════════════════

class TestEventTemplateV2:
    """v2 EventTemplate dramatic_score 测试。"""

    def _make_event(self, **kwargs):
        defaults = {
            "id": "test_evt", "name": "测试事件", "event_type": "Daily",
            "week_range": "", "day_range": "", "time_slot": "Morning",
            "location": "", "participants": [], "weight": 1,
        }
        defaults.update(kwargs)
        return EventTemplate(**defaults)

    def test_dramatic_score_default(self):
        e = self._make_event()
        assert e.dramatic_score == 5

    def test_dramatic_score_set_explicit(self):
        for score in [0, 3, 6, 9, 10]:
            e = self._make_event(dramatic_score=score)
            assert e.dramatic_score == score

    def test_dramatic_score_ambient(self):
        e = self._make_event(dramatic_score=0)
        assert e.dramatic_score <= 2

    def test_dramatic_score_high_drama(self):
        e = self._make_event(dramatic_score=7)
        assert e.dramatic_score >= 6


# ═══════════════════════════════════════════════════
# 3. SettlementResult player_impact_flags
# ═══════════════════════════════════════════════════

class TestSettlementResultV2:
    """v2 SettlementResult player_impact_flags 测试。"""

    def test_default_empty(self):
        r = SettlementResult(event_id="e1", event_name="测试", outcome_id="o1", outcome_name="结果")
        assert r.player_impact_flags == {}

    def test_set_impact_flags(self):
        r = SettlementResult(
            event_id="e1", event_name="测试", outcome_id="o1", outcome_name="结果",
            player_impact_flags={"blessed": True, "coin_success": True, "extra_investment": False},
        )
        assert r.player_impact_flags["blessed"]
        assert r.player_impact_flags["coin_success"]
        assert not r.player_impact_flags["extra_investment"]


# ═══════════════════════════════════════════════════
# 4. ScreenwriterResult 数据类测试
# ═══════════════════════════════════════════════════

class TestScreenwriterResult:
    """v2 ScreenwriterResult 数据类 + 事件过滤方法测试。"""

    def _make_event(self, eid, score, participants=None):
        return (
            EventTemplate(
                id=eid, name=eid, event_type="Daily",
                week_range="", day_range="", time_slot="Morning",
                location="", participants=participants or [], weight=1,
                dramatic_score=score,
            ),
            Outcome(id=f"out_{eid}", event_id=eid, name="结果", trigger_condition="default"),
        )

    def test_constructor_defaults(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        r = ScreenwriterResult()
        assert not r.ok
        assert r.events == []
        assert r.slot_summary == ""
        assert r.dramatic_scores == {}

    def test_constructor_with_events(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        events = [self._make_event("e1", 7), self._make_event("e2", 3)]
        r = ScreenwriterResult(ok=True, events=events, slot_summary="测试摘要")
        assert r.ok
        assert len(r.events) == 2
        assert r.slot_summary == "测试摘要"

    def test_high_drama_events(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        events = [
            self._make_event("e_high_1", 8),
            self._make_event("e_mid", 4),
            self._make_event("e_high_2", 10),
            self._make_event("e_low", 1),
        ]
        r = ScreenwriterResult(ok=True, events=events)
        high = r.high_drama_events
        assert len(high) == 2
        scores = {e[0].dramatic_score for e in high}
        assert scores == {8, 10}

    def test_medium_drama_events(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        events = [
            self._make_event("e_high", 9),
            self._make_event("e_mid_1", 3),
            self._make_event("e_mid_2", 5),
            self._make_event("e_low", 0),
        ]
        r = ScreenwriterResult(ok=True, events=events)
        mid = r.medium_drama_events
        assert len(mid) == 2
        scores = {e[0].dramatic_score for e in mid}
        assert scores == {3, 5}

    def test_ambient_events(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        events = [
            self._make_event("e_a1", 0),
            self._make_event("e_a2", 2),
            self._make_event("e_mid", 4),
            self._make_event("e_high", 8),
        ]
        r = ScreenwriterResult(ok=True, events=events)
        ambient = r.ambient_events
        assert len(ambient) == 2
        scores = {e[0].dramatic_score for e in ambient}
        assert scores == {0, 2}

    def test_blessing_events(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        events = [
            self._make_event("e_b1", 6),
            self._make_event("e_b2", 9),
            self._make_event("e_nb", 4),
        ]
        r = ScreenwriterResult(ok=True, events=events)
        blessing = r.blessing_events
        assert len(blessing) == 2
        assert all(e[0].dramatic_score >= 6 for e in blessing)

    def test_dramatic_scores_map(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        events = [
            self._make_event("e1", 8),
            self._make_event("e2", 2),
        ]
        r = ScreenwriterResult(ok=True, events=events,
                               dramatic_scores={"e1": 8, "e2": 2})
        assert r.dramatic_scores == {"e1": 8, "e2": 2}

    def test_empty_events_all_properties(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        r = ScreenwriterResult(ok=True)
        assert r.high_drama_events == []
        assert r.medium_drama_events == []
        assert r.ambient_events == []
        assert r.blessing_events == []


# ═══════════════════════════════════════════════════
# 5. NPC Agent v2: receive_dream + _build_dream_context
# ═══════════════════════════════════════════════════

class TestNpcAgentV2:
    """NPC Agent v2 托梦系统测试。"""

    @staticmethod
    def _make_npc_static(npc_id="lin_chaoyin", **kwargs):
        defaults = {
            "id": npc_id, "name": "林潮音", "age": 20, "occupation": "神社巫女",
            "background": "归潮镇的神社巫女", "core_wish": "找到归属",
            "personality": Personality(kindness=0.7, aggression=0.2, sensibility=0.8,
                                       rationality=0.5, curiosity=0.6),
            "tier": "S", "initial_locations": {},
        }
        defaults.update(kwargs)
        return NpcStatic(**defaults)

    @pytest.fixture
    def npc_agent(self):
        from src.backend.ai.npc_agent.agent import NpcAgent
        static = self._make_npc_static()
        return NpcAgent(static)

    def test_receive_dream_writes_source_dream(self, npc_agent):
        npc_agent.receive_dream(
            dream_text="今晚别去港口",
            incense_snapshot=72,
            day=3, slot=Slot.NIGHT,
        )
        dreams = npc_agent.memory.by_source("dream")
        assert len(dreams) == 1
        d = dreams[0]
        assert d.source == "dream"
        assert d.dream_incense_snapshot == 72
        assert d.dream_text == "今晚别去港口"
        assert d.importance == 5  # 默认重要度
        assert d.day == 3

    def test_receive_dream_stores_in_description(self, npc_agent):
        npc_agent.receive_dream(
            dream_text="去寺庙看看",
            incense_snapshot=50,
            day=5, slot=Slot.NIGHT,
        )
        dreams = npc_agent.memory.by_source("dream")
        assert "梦中" in dreams[0].description
        assert "去寺庙看看" in dreams[0].description

    def test_multiple_dreams_preserved(self, npc_agent):
        npc_agent.receive_dream("第一夜", 50, 1, Slot.NIGHT)
        npc_agent.receive_dream("第二夜", 80, 3, Slot.NIGHT)
        npc_agent.receive_dream("第三夜", 110, 5, Slot.NIGHT)
        dreams = npc_agent.memory.by_source("dream")
        assert len(dreams) == 3
        assert dreams[0].day == 1
        assert dreams[2].day == 5

    def test_build_dream_context_low_incense(self, npc_agent):
        npc_agent.receive_dream("有人叫你", 20, 3, Slot.NIGHT)
        ctx = npc_agent._build_dream_context()
        assert "有人叫你" in ctx
        assert "杂念" in ctx or "20" in ctx

    def test_build_dream_context_mid_incense(self, npc_agent):
        npc_agent.receive_dream("去寺庙", 70, 3, Slot.NIGHT)
        ctx = npc_agent._build_dream_context()
        assert "去寺庙" in ctx
        assert "暗示" in ctx

    def test_build_dream_context_high_incense(self, npc_agent):
        npc_agent.receive_dream("今晚别出海", 130, 3, Slot.NIGHT)
        ctx = npc_agent._build_dream_context()
        assert "今晚别出海" in ctx
        assert "低语" in ctx

    def test_build_dream_context_divine_incense(self, npc_agent):
        npc_agent.receive_dream("拯救村庄", 160, 3, Slot.NIGHT)
        ctx = npc_agent._build_dream_context()
        assert "拯救村庄" in ctx
        assert "神谕" in ctx

    def test_build_dream_context_no_dreams(self, npc_agent):
        ctx = npc_agent._build_dream_context()
        assert ctx == ""

    def test_build_dream_context_uses_latest_dream(self, npc_agent):
        npc_agent.receive_dream("旧梦", 30, 1, Slot.NIGHT)
        npc_agent.receive_dream("新梦", 100, 5, Slot.NIGHT)
        ctx = npc_agent._build_dream_context()
        assert "新梦" in ctx
        assert "100" in ctx


# ═══════════════════════════════════════════════════
# 6. fill_scene with player_context
# ═══════════════════════════════════════════════════

class TestFillSceneV2:
    """fill_scene 玩家介入感知测试。"""

    @staticmethod
    def _make_static(npc_id="lin_chaoyin"):
        return NpcStatic(
            id=npc_id, name="林潮音", age=20, occupation="巫女",
            background="归潮镇巫女", core_wish="找到归属",
            personality=Personality(kindness=0.7, aggression=0.2, sensibility=0.8,
                                     rationality=0.5, curiosity=0.6),
            tier="S", initial_locations={},
        )

    @pytest.fixture
    def agent(self):
        from src.backend.ai.npc_agent.agent import NpcAgent
        return NpcAgent(self._make_static())

    def test_fill_scene_without_player_context(self, agent):
        """无 player_context 时不应报错。"""
        skeleton = {"goal": "日常", "tone": "轻松", "line_steps": []}
        result = asyncio.run(agent.fill_scene(skeleton, 1, Slot.MORNING))
        assert "actor" in result
        assert "lines" in result

    def test_fill_scene_with_empty_player_context(self, agent):
        skeleton = {"goal": "日常", "tone": "轻松", "line_steps": []}
        result = asyncio.run(agent.fill_scene(skeleton, 1, Slot.MORNING, player_context={}))
        assert "actor" in result
        assert "lines" in result

    def test_fill_scene_with_blessing_target(self, agent):
        skeleton = {"goal": "日常", "tone": "轻松", "line_steps": []}
        pc = {"blessed_targets": ["lin_chaoyin"], "blessed_event_ids": []}
        result = asyncio.run(agent.fill_scene(skeleton, 1, Slot.MORNING, player_context=pc))
        assert result.get("perceived_blessing") is True

    def test_fill_scene_with_blessed_event_participant(self, agent):
        skeleton = {"goal": "日常", "tone": "轻松", "line_steps": []}
        pc = {
            "blessed_targets": [],
            "blessed_event_ids": ["evt_1"],
            "participants_map": {"evt_1": ["lin_chaoyin", "huiyuan"]},
        }
        result = asyncio.run(agent.fill_scene(skeleton, 1, Slot.MORNING, player_context=pc))
        assert result.get("perceived_blessing") is True

    def test_fill_scene_not_blessed(self, agent):
        skeleton = {"goal": "日常", "tone": "轻松", "line_steps": []}
        pc = {"blessed_targets": ["huiyuan"], "blessed_event_ids": []}
        result = asyncio.run(agent.fill_scene(skeleton, 1, Slot.MORNING, player_context=pc))
        assert "perceived_blessing" not in result or result.get("perceived_blessing") is not True


# ═══════════════════════════════════════════════════
# 7. MemoryStore by_source()
# ═══════════════════════════════════════════════════

class TestMemoryStoreBySource:
    """MemoryStore.by_source() 检索方法测试。"""

    @pytest.fixture
    def store(self):
        from src.backend.ai.npc_agent.memory import MemoryStore
        return MemoryStore("lin_chaoyin")

    def test_by_source_event(self, store):
        store.remember(1, Slot.MORNING, "普通事件", source="event")
        store.remember(2, Slot.NIGHT, "托梦", source="dream")
        results = store.by_source("event")
        assert len(results) == 1
        assert results[0].description == "普通事件"

    def test_by_source_dream(self, store):
        store.remember(1, Slot.NIGHT, "梦1", source="dream", dream_incense_snapshot=50, dream_text="测试")
        store.remember(3, Slot.NIGHT, "梦2", source="dream", dream_incense_snapshot=80, dream_text="测试2")
        results = store.by_source("dream")
        assert len(results) == 2
        assert results[0].day == 1
        assert results[1].day == 3

    def test_by_source_empty(self, store):
        store.remember(1, Slot.MORNING, "事件", source="event")
        results = store.by_source("dream")
        assert results == []

    def test_by_source_mixed(self, store):
        store.remember(1, Slot.MORNING, "e1", source="event")
        store.remember(1, Slot.NOON, "e2", source="blessing_felt")
        store.remember(1, Slot.NIGHT, "d1", source="dream")
        store.remember(2, Slot.MORNING, "a1", source="ambient")

        assert len(store.by_source("event")) == 1
        assert len(store.by_source("blessing_felt")) == 1
        assert len(store.by_source("dream")) == 1
        assert len(store.by_source("ambient")) == 1

    def test_by_source_sorted_by_time(self, store):
        store.remember(5, Slot.NIGHT, "latest", source="dream")
        store.remember(1, Slot.NIGHT, "earliest", source="dream")
        store.remember(3, Slot.NIGHT, "middle", source="dream")
        results = store.by_source("dream")
        assert results[0].day == 1
        assert results[1].day == 3
        assert results[2].day == 5


# ═══════════════════════════════════════════════════
# 8. _build_blessing_slots
# ═══════════════════════════════════════════════════

class TestBlessingSlots:
    """_build_blessing_slots 辅助函数测试。"""

    @staticmethod
    def _make_session():
        class MockSession:
            class MockAgents:
                npc_ids = ["lin_chaoyin", "chen_yuanzhou"]
                def get(self, nid):
                    mapping = {
                        "lin_chaoyin": type("A", (), {"name": "林潮音"})(),
                        "chen_yuanzhou": type("A", (), {"name": "陈远舟"})(),
                    }
                    return mapping.get(nid)
            agents = MockAgents()
        return MockSession()

    def test_build_empty_for_no_blessing_events(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        from src.backend.server.routes.ws_game import _build_blessing_slots

        r = ScreenwriterResult(ok=True, events=[])
        slots = _build_blessing_slots(r, self._make_session())
        assert slots == []

    def test_build_for_high_drama_events_only(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        from src.backend.server.routes.ws_game import _build_blessing_slots

        e1 = EventTemplate(
            id="e1", name="高冲突事件", event_type="Key",
            week_range="", day_range="", time_slot="Morning",
            location="port", participants=["lin_chaoyin", "chen_yuanzhou"],
            weight=5, dramatic_score=8,
        )
        e2 = EventTemplate(
            id="e2", name="低冲突事件", event_type="Daily",
            week_range="", day_range="", time_slot="Morning",
            location="", participants=["lin_chaoyin"],
            weight=1, dramatic_score=3,
        )
        outcome = Outcome(id="o1", event_id="e1", name="结果", trigger_condition="default")

        r = ScreenwriterResult(ok=True, events=[(e1, outcome), (e2, outcome)])
        slots = _build_blessing_slots(r, self._make_session())

        assert len(slots) == 1
        assert slots[0]["event_id"] == "e1"
        assert slots[0]["dramatic_score"] == 8
        assert slots[0]["base_cost"] == 3

    def test_blessing_slot_structure(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        from src.backend.server.routes.ws_game import _build_blessing_slots

        e = EventTemplate(
            id="evt_critical", name="命运时刻", event_type="Anchor",
            week_range="", day_range="", time_slot="Night",
            location="temple", participants=["lin_chaoyin", "chen_yuanzhou"],
            weight=1000, dramatic_score=10,
        )
        outcome = Outcome(id="o_critical", event_id="evt_critical", name="转折", trigger_condition="default")

        r = ScreenwriterResult(ok=True, events=[(e, outcome)])
        slots = _build_blessing_slots(r, self._make_session())

        assert len(slots) == 1
        s = slots[0]
        assert s["event_id"] == "evt_critical"
        assert s["event_name"] == "命运时刻"
        assert s["location_id"] == "temple"
        assert s["participants"] == ["lin_chaoyin", "chen_yuanzhou"]
        assert len(s["participant_names"]) == 2
        assert s["difficulty_hint"] == "困难"  # score >= 9
        assert s["base_cost"] == 3
        assert s["dramatic_score"] == 10

    def test_medium_drama_difficulty_hint(self):
        from src.backend.ai.screenwriter.screenwriter import ScreenwriterResult
        from src.backend.server.routes.ws_game import _build_blessing_slots

        e = EventTemplate(
            id="e_mid", name="中等冲突", event_type="Key",
            week_range="", day_range="", time_slot="Noon",
            location="cafe", participants=["lin_chaoyin"],
            weight=3, dramatic_score=7,
        )
        outcome = Outcome(id="o1", event_id="e_mid", name="结果", trigger_condition="default")

        r = ScreenwriterResult(ok=True, events=[(e, outcome)])
        slots = _build_blessing_slots(r, self._make_session())

        assert len(slots) == 1
        assert slots[0]["difficulty_hint"] == "中等"


# ═══════════════════════════════════════════════════
# 9. screenwriter_think 集成测试 (Mock LLM)
# ═══════════════════════════════════════════════════

class TestScreenwriterThinkV2:
    """screenwriter_think 完整流程 v2 测试（Mock LLM）。"""

    @pytest.fixture
    def mock_llm(self):
        class MockLLM:
            def __init__(self, response):
                self._response = response
            async def chat(self, messages, **kwargs):
                return self._response
            async def is_available(self):
                return True
        return MockLLM

    @pytest.fixture
    def mock_session_with_agents(self):
        from src.backend.engine.resource import ResourceState

        class MockBondManager:
            def bonds_from(self, npc_id):
                return []
            def bonds_to(self, npc_id):
                return []

        class MockAgent:
            def __init__(self, nid, name):
                self.npc_id = nid
                self.name = name
                self.static = NpcStatic(
                    id=nid, name=name, age=25, occupation="居民",
                    background="", core_wish="平静生活",
                    personality=Personality(kindness=0.5, aggression=0.3,
                                            sensibility=0.5, rationality=0.5, curiosity=0.5),
                    tier="S", initial_locations={},
                )
                self.llm = None

                class _Mem:
                    def recent_events(self_ignored, n=5):
                        return []
                self.memory = _Mem()
                self.dynamic = type("D", (), {
                    "current": type("C", (), {
                        "location": type("L", (), {"value": "temple"})(),
                        "emotion": type("E", (), {"value": "neutral"})(),
                        "energy": 80, "happiness": 60,
                    })(),
                })()

        class MockAgents:
            def __init__(self):
                self._agents = {
                    "lin_chaoyin": MockAgent("lin_chaoyin", "林潮音"),
                    "chen_yuanzhou": MockAgent("chen_yuanzhou", "陈远舟"),
                }
            def get(self, npc_id):
                return self._agents.get(npc_id)
            @property
            def npc_ids(self):
                return list(self._agents.keys())

        class MockSession:
            def __init__(self):
                self.resource = ResourceState()
                self.agents = MockAgents()
                self.story = StoryState()
                self.bonds = MockBondManager()
        return MockSession()

    def test_screenwriter_returns_slot_summary(self, mock_session_with_agents, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        response = json.dumps({
            "narrator_insight": "平静的上午",
            "slot_summary": "今晨的港口比往日更沉。陈远舟独自站在码头，似乎心事重重。",
            "interventions": [],
            "triggered_beats": [],
            "spontaneous_events": [],
        }, ensure_ascii=False)
        llm = mock_llm(response)
        outline = StoryOutline(global_constraints=GlobalConstraints(max_events_per_slot=3))

        async def _run():
            return await screenwriter_think(
                session=mock_session_with_agents, story_outline=outline,
                day=3, slot=Slot.MORNING, week=1, phase_name="旧神将熄",
                npc_intentions=[("lin_chaoyin", "林潮音", "散步", "temple")],
                llm=llm, templates={"templates": [], "composition_rules": {}},
            )
        result = asyncio.run(_run())
        assert result.ok
        assert result.slot_summary == "今晨的港口比往日更沉。陈远舟独自站在码头，似乎心事重重。"

    def test_screenwriter_fallback_when_slot_summary_missing(self, mock_session_with_agents, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        response = json.dumps({
            "narrator_insight": "平静",
            "interventions": [],
            "triggered_beats": [],
            "spontaneous_events": [],
        }, ensure_ascii=False)
        llm = mock_llm(response)
        outline = StoryOutline(global_constraints=GlobalConstraints(max_events_per_slot=3))

        async def _run():
            return await screenwriter_think(
                session=mock_session_with_agents, story_outline=outline,
                day=3, slot=Slot.MORNING, week=1, phase_name="旧神将熄",
                npc_intentions=[], llm=llm, templates={"templates": [], "composition_rules": {}},
            )
        result = asyncio.run(_run())
        assert result.ok
        assert len(result.slot_summary) > 0  # fallback kicks in

    def test_screenwriter_parses_dramatic_score(self, mock_session_with_agents, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        response = json.dumps({
            "narrator_insight": "关键时刻",
            "slot_summary": "午后咖啡店里气氛微妙。",
            "interventions": [],
            "triggered_beats": [{
                "beat_id": "test_beat",
                "outcome_id": "out_1",
                "dramatic_score": 8,
                "reasoning": "关系临界点",
            }],
            "spontaneous_events": [],
        }, ensure_ascii=False)
        llm = mock_llm(response)

        beat = StoryBeat(
            id="test_beat", name="关键事件", type="key",
            earliest_day=1, latest_day=10,
            participants=["lin_chaoyin", "chen_yuanzhou"],
            what_must_happen="关键转折",
            outcomes=[OutcomeDef(id="out_1", description="好结局", resource_delta={"yang_de": 2})],
        )
        outline = StoryOutline(
            standalone_beats=[beat],
            global_constraints=GlobalConstraints(max_events_per_slot=3),
        )

        async def _run():
            return await screenwriter_think(
                session=mock_session_with_agents, story_outline=outline,
                day=5, slot=Slot.NOON, week=1, phase_name="织线初启",
                npc_intentions=[
                    ("lin_chaoyin", "林潮音", "去咖啡馆", "cafe"),
                    ("chen_yuanzhou", "陈远舟", "买咖啡", "cafe"),
                ],
                llm=llm, templates={"templates": [], "composition_rules": {}},
            )
        result = asyncio.run(_run())
        assert result.ok
        assert len(result.events) == 1
        event_template = result.events[0][0]
        assert event_template.dramatic_score == 8
        assert result.dramatic_scores.get("test_beat") == 8

    def test_screenwriter_dramatic_score_default_on_missing(self, mock_session_with_agents, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        response = json.dumps({
            "narrator_insight": "测试",
            "slot_summary": "日常",
            "interventions": [],
            "triggered_beats": [{
                "beat_id": "test_beat",
                "outcome_id": "out_1",
            }],
            "spontaneous_events": [],
        }, ensure_ascii=False)
        llm = mock_llm(response)

        beat = StoryBeat(
            id="test_beat", name="测试", type="key",
            earliest_day=1, latest_day=10,
            participants=["lin_chaoyin"],
            outcomes=[OutcomeDef(id="out_1", description="结果")],
        )
        outline = StoryOutline(
            standalone_beats=[beat],
            global_constraints=GlobalConstraints(max_events_per_slot=3),
        )

        async def _run():
            return await screenwriter_think(
                session=mock_session_with_agents, story_outline=outline,
                day=5, slot=Slot.NOON, week=1, phase_name="测试",
                npc_intentions=[("lin_chaoyin", "林潮音", "测试", "temple")],
                llm=llm, templates={},
            )
        result = asyncio.run(_run())
        assert result.ok
        assert result.events[0][0].dramatic_score == 5  # default

    def test_screenwriter_spontaneous_gets_dramatic_score(self, mock_session_with_agents, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        response = json.dumps({
            "narrator_insight": "日常",
            "slot_summary": "安静的午后。",
            "interventions": [{"npc_id": "lin_chaoyin", "decision": "pass", "reasoning": "无事"}],
            "triggered_beats": [],
            "spontaneous_events": [{
                "template_id": "chance_encounter",
                "participants": ["lin_chaoyin", "chen_yuanzhou"],
                "location": "cafe",
                "detail": "两人偶遇，聊了几句",
                "dramatic_score": 4,
                "outcome": {},
                "reasoning": "日常偶遇，给4分",
            }],
        }, ensure_ascii=False)
        llm = mock_llm(response)
        outline = StoryOutline(global_constraints=GlobalConstraints(max_events_per_slot=3))

        templates = {
            "templates": [{
                "id": "chance_encounter", "name": "偶遇", "tone": "轻松",
                "min_participants": 2, "max_participants": 4,
                "delta_budget": {"bond": {"min": 0, "max": 3}, "happiness": {"min": -1, "max": 2}},
            }],
            "composition_rules": {
                "max_spontaneous_per_slot": 2,
                "no_same_template_consecutive": True,
                "night_allowed_only": [],
            },
        }

        async def _run():
            return await screenwriter_think(
                session=mock_session_with_agents, story_outline=outline,
                day=3, slot=Slot.NOON, week=1, phase_name="测试",
                npc_intentions=[
                    ("lin_chaoyin", "林潮音", "在咖啡馆", "cafe"),
                    ("chen_yuanzhou", "陈远舟", "来买咖啡", "cafe"),
                ],
                llm=llm, templates=templates,
            )
        result = asyncio.run(_run())
        assert result.ok
        assert len(result.events) == 1
        assert result.events[0][0].dramatic_score == 4

    def test_screenwriter_result_ok_false_on_no_llm(self, mock_session_with_agents):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        outline = StoryOutline(global_constraints=GlobalConstraints(max_events_per_slot=3))

        async def _run():
            return await screenwriter_think(
                session=mock_session_with_agents, story_outline=outline,
                day=1, slot=Slot.MORNING, week=1, phase_name="测试",
                npc_intentions=[], llm=None,
            )
        result = asyncio.run(_run())
        assert not result.ok
        assert result.events == []
        assert result.slot_summary == ""

    def test_screenwriter_result_events_properties(self, mock_session_with_agents, mock_llm):
        """Verify ScreenwriterResult.high_drama_events etc work from real flow."""
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        response = json.dumps({
            "narrator_insight": "测试",
            "slot_summary": "测试摘要",
            "interventions": [],
            "triggered_beats": [{
                "beat_id": "test_beat",
                "outcome_id": "out_1",
                "dramatic_score": 9,
            }],
            "spontaneous_events": [],
        }, ensure_ascii=False)
        llm = mock_llm(response)

        beat = StoryBeat(
            id="test_beat", name="高冲突", type="anchor",
            earliest_day=1, latest_day=10,
            participants=["lin_chaoyin"],
            outcomes=[OutcomeDef(id="out_1", description="结果")],
        )
        outline = StoryOutline(
            standalone_beats=[beat],
            global_constraints=GlobalConstraints(max_events_per_slot=3),
        )

        async def _run():
            return await screenwriter_think(
                session=mock_session_with_agents, story_outline=outline,
                day=5, slot=Slot.NOON, week=1, phase_name="测试",
                npc_intentions=[("lin_chaoyin", "林潮音", "思考", "temple")],
                llm=llm, templates={},
            )
        result = asyncio.run(_run())
        assert result.ok
        assert len(result.high_drama_events) == 1
        assert len(result.blessing_events) == 1
        assert len(result.medium_drama_events) == 0
        assert len(result.ambient_events) == 0


# ═══════════════════════════════════════════════════
# 10. Prompt 内容验证
# ═══════════════════════════════════════════════════

class TestPromptsV2:
    """v2 Prompt 字段存在性测试。"""

    def test_screenwriter_prompt_has_dramatic_section(self):
        from src.backend.ai.screenwriter.prompts import SYSTEM_PROMPT
        assert "戏剧冲突性评分" in SYSTEM_PROMPT
        assert "dramatic_score" in SYSTEM_PROMPT
        assert "0-2" in SYSTEM_PROMPT
        assert "3-5" in SYSTEM_PROMPT
        assert "6-8" in SYSTEM_PROMPT
        assert "9-10" in SYSTEM_PROMPT

    def test_screenwriter_prompt_has_slot_summary_section(self):
        from src.backend.ai.screenwriter.prompts import SYSTEM_PROMPT
        assert "时段预告" in SYSTEM_PROMPT
        assert "slot_summary" in SYSTEM_PROMPT
        assert "土地公视角" in SYSTEM_PROMPT
        assert "不剧透任何结果" in SYSTEM_PROMPT

    def test_screenwriter_prompt_has_scoring_dimensions(self):
        from src.backend.ai.screenwriter.prompts import SYSTEM_PROMPT
        assert "关系逆转" in SYSTEM_PROMPT or "秘密揭示" in SYSTEM_PROMPT
        assert "参与者情绪" in SYSTEM_PROMPT

    def test_fill_scene_prompt_has_blessing_placeholder(self):
        from src.backend.ai.npc_agent.templates import FILL_SCENE_PROMPT
        assert "{blessing_context}" in FILL_SCENE_PROMPT
        assert "{dream_context}" in FILL_SCENE_PROMPT

    def test_system_prompt_has_dream_placeholder(self):
        from src.backend.ai.npc_agent.templates import SYSTEM_PROMPT_TEMPLATE
        assert "{dream_context}" in SYSTEM_PROMPT_TEMPLATE

    def test_system_prompt_has_incense_explanation(self):
        from src.backend.ai.npc_agent.templates import SYSTEM_PROMPT_TEMPLATE
        assert "托梦" in SYSTEM_PROMPT_TEMPLATE or "香火" in SYSTEM_PROMPT_TEMPLATE
        assert "神迹的分量" in SYSTEM_PROMPT_TEMPLATE

    def test_decision_prompt_accepts_dream_context(self):
        from src.backend.ai.npc_agent.templates import build_decision_prompt
        static = NpcStatic(
            id="test", name="测试", age=20, occupation="测试",
            background="", core_wish="",
            personality=Personality(kindness=0.5, aggression=0.3,
                                    sensibility=0.5, rationality=0.5, curiosity=0.5),
            tier="S", initial_locations={},
        )
        prompt = build_decision_prompt(
            static=static, memory_context="", location="home",
            emotion="neutral", energy=80, happiness=50,
            dream_context="我有神谕",
        )
        assert "我有神谕" in prompt

    def test_build_fill_scene_prompt_accepts_new_params(self):
        from src.backend.ai.npc_agent.templates import build_fill_scene_prompt
        static = NpcStatic(
            id="test", name="测试", age=20, occupation="测试",
            background="", core_wish="",
            personality=Personality(kindness=0.5, aggression=0.3,
                                    sensibility=0.5, rationality=0.5, curiosity=0.5),
            tier="S", initial_locations={},
        )
        skeleton = {"goal": "测试场景", "tone": "日常", "line_steps": []}
        prompt = build_fill_scene_prompt(
            static=static, skeleton=skeleton,
            location="cafe", emotion="neutral", energy=80, happiness=50,
            dream_context="神明托梦内容", perceives_blessing=True,
        )
        assert "神明托梦内容" in prompt
        assert "眷顾" in prompt or "赐福" in prompt

    def test_dialogue_pipeline_accepts_player_context(self):
        """Verify run_dialogue_pipeline signature accepts player_context."""
        import inspect
        from src.backend.ai.dialogue_designer.pipeline import run_dialogue_pipeline
        sig = inspect.signature(run_dialogue_pipeline)
        params = list(sig.parameters.keys())
        assert "player_context" in params


# ═══════════════════════════════════════════════════
# 11. WebSocket helpers
# ═══════════════════════════════════════════════════

class TestWSHelpers:
    """WebSocket v2 辅助函数测试。"""

    def test_build_location_map(self):
        from src.backend.server.routes.ws_game import _build_location_map

        class MockAgent:
            def __init__(self, loc):
                self.dynamic = type("D", (), {
                    "current": type("C", (), {"location": type("L", (), {"value": loc})()})(),
                })()
        class MockSession:
            class MockAgents:
                npc_ids = ["a", "b"]
                def get(self, nid):
                    mapping = {"a": MockAgent("temple"), "b": MockAgent("port")}
                    return mapping.get(nid)
            agents = MockAgents()

        locs = _build_location_map(MockSession())
        assert locs["a"] == "temple"
        assert locs["b"] == "port"
        assert locs.get("heaven_messenger") == "temple"
        assert locs.get("tudi_gong") == "temple"

    def test_get_llm_returns_s_tier(self):
        from src.backend.server.routes.ws_game import _get_llm

        mock_llm = object()
        class MockAgent:
            def __init__(self, tier):
                self.static = type("S", (), {"tier": type("T", (), {"value": tier})()})()
                self.llm = mock_llm if tier == "S" else None
        class MockSession:
            class MockAgents:
                npc_ids = ["a", "b", "c"]
                def get(self, nid):
                    return {"a": MockAgent("B"), "b": MockAgent("S"), "c": MockAgent("A")}.get(nid)
            agents = MockAgents()

        llm = _get_llm(MockSession())
        assert llm is mock_llm

    def test_get_llm_fallback_to_a(self):
        from src.backend.server.routes.ws_game import _get_llm

        mock_llm = object()
        class MockAgent:
            def __init__(self, tier):
                self.static = type("S", (), {"tier": type("T", (), {"value": tier})()})()
                self.llm = mock_llm if tier == "A" else None
        class MockSession:
            class MockAgents:
                npc_ids = ["a", "b"]
                def get(self, nid):
                    return {"a": MockAgent("B"), "b": MockAgent("A")}.get(nid)
            agents = MockAgents()

        llm = _get_llm(MockSession())
        assert llm is mock_llm

    def test_get_llm_returns_none_when_no_s_or_a(self):
        from src.backend.server.routes.ws_game import _get_llm

        class MockAgent:
            def __init__(self):
                self.static = type("S", (), {"tier": type("T", (), {"value": "B"})()})()
                self.llm = None
        class MockSession:
            class MockAgents:
                npc_ids = ["a"]
                def get(self, nid):
                    return MockAgent()
            agents = MockAgents()

        llm = _get_llm(MockSession())
        assert llm is None


# ═══════════════════════════════════════════════════
# 12. 数据流完整链路测试
# ═══════════════════════════════════════════════════

class TestFullDataflowV2:
    """v2 数据流从编剧输出到记忆写入的完整链路。"""

    def _make_static(self, nid, name, tier="S"):
        return NpcStatic(
            id=nid, name=name, age=25, occupation="居民",
            background="", core_wish="平静生活",
            personality=Personality(kindness=0.5, aggression=0.3,
                                    sensibility=0.5, rationality=0.5, curiosity=0.5),
            tier=tier, initial_locations={},
        )

    def test_dream_to_memory_to_context_chain(self):
        """托梦 → 记忆 → _build_dream_context 完整链路。"""
        from src.backend.ai.npc_agent.agent import NpcAgent
        agent = NpcAgent(self._make_static("npc1", "测试"))

        # Step 1: 玩家托梦
        agent.receive_dream("今晚别去港口", 72, 3, Slot.NIGHT)

        # Step 2: 验证记忆写入
        dreams = agent.memory.by_source("dream")
        assert len(dreams) == 1
        assert dreams[0].dream_text == "今晚别去港口"
        assert dreams[0].dream_incense_snapshot == 72

        # Step 3: 验证上下文生成
        ctx = agent._build_dream_context()
        assert "今晚别去港口" in ctx
        assert "72" in ctx
        assert "暗示" in ctx  # 40-100 range

    def test_fill_scene_perceives_blessing_chain(self):
        """编剧产出 + 赐福 → fill_scene 感知 完整链路。"""
        from src.backend.ai.npc_agent.agent import NpcAgent
        agent = NpcAgent(self._make_static("npc1", "测试"))

        skeleton = {"goal": "关键对话", "tone": "紧张", "line_steps": []}
        player_context = {
            "blessed_targets": ["npc1"],
            "blessed_event_ids": [],
        }

        result = asyncio.run(agent.fill_scene(skeleton, 5, Slot.NOON, player_context=player_context))
        assert result.get("perceived_blessing") is True

    def test_screenwriter_to_slot_summary_chain(self):
        """编剧 LLM 输出 → ScreenwriterResult → slot_summary 提取 完整链路。"""
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot
        from src.backend.engine.resource import ResourceState

        class MockLLM:
            def __init__(self):
                pass
            async def chat(self, messages, **kwargs):
                return json.dumps({
                    "narrator_insight": "平静",
                    "slot_summary": "午后的归潮镇安静得出奇。林潮音独自坐在神社石阶上，似乎在等待什么。你若留心，或许能在她的沉思中找到介入的契机。",
                    "interventions": [],
                    "triggered_beats": [],
                    "spontaneous_events": [],
                }, ensure_ascii=False)

        class MockAgent:
            def __init__(self, nid, name):
                self.npc_id = nid
                self.name = name
                self.static = NpcStatic(
                    id=nid, name=name, age=25, occupation="居民",
                    background="", core_wish="",
                    personality=Personality(kindness=0.5, aggression=0.3,
                                            sensibility=0.5, rationality=0.5, curiosity=0.5),
                    tier="S", initial_locations={},
                )
                self.llm = MockLLM()

                class _Mem:
                    def recent_events(self_ignored, n=5):
                        return []
                self.memory = _Mem()
                self.dynamic = type("D", (), {
                    "current": type("C", (), {
                        "location": type("L", (), {"value": "temple"})(),
                        "emotion": type("E", (), {"value": "neutral"})(),
                        "energy": 80, "happiness": 60,
                    })(),
                })()

        class MockSession:
            def __init__(self):
                self.resource = ResourceState()
                self.agents = type("A", (), {
                    "npc_ids": ["npc1"],
                    "get": lambda self, nid: MockAgent("npc1", "林潮音"),
                    "_agents": {"npc1": MockAgent("npc1", "林潮音")},
                })()
                self.story = StoryState()

        outline = StoryOutline(global_constraints=GlobalConstraints(max_events_per_slot=3))

        async def _run():
            return await screenwriter_think(
                session=MockSession(), story_outline=outline,
                day=3, slot=Slot.NOON, week=1, phase_name="旧神将熄",
                npc_intentions=[("npc1", "林潮音", "发呆", "temple")],
                llm=MockLLM(), templates={"templates": [], "composition_rules": {}},
            )

        result = asyncio.run(_run())
        assert result.ok
        assert "归潮镇" in result.slot_summary
        assert "林潮音" in result.slot_summary
        assert len(result.slot_summary) >= 40  # 含 fallback 情况偏短
