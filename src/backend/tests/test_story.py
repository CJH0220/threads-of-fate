"""Story system & screenwriter tests.

Coverage:
- story_types: dataclass construction, StoryBeat properties, StoryState serialization
- story_loader: JSON loading, caching, missing file handling
- screenwriter parsing: JSON output parsing with 3-tier fallback
- screenwriter beats: eligible beat filtering, missed beat handling, event building
- screenwriter integration: full flow with mock LLM
"""

import json
import os
import tempfile

import pytest

from src.backend.engine.story.story_types import (
    GlobalConstraints,
    Intervention,
    OnMissedDef,
    OutcomeDef,
    StoryArc,
    StoryBeat,
    StoryOutline,
    StoryState,
    ToneRule,
    TriggeredBeat,
)
from src.backend.engine.story.story_loader import (
    _parse_beat,
    _parse_outline,
    clear_cache,
    load_story_outline,
)
from src.backend.ai.screenwriter.screenwriter import (
    _apply_missed_beat,
    _build_events_from_beats,
    _get_eligible_beats,
    _parse_llm_output,
)


# ═══════════════════════════════════════════════════
# Story types
# ═══════════════════════════════════════════════════

class TestStoryTypes:
    """Dataclass construction and property tests."""

    def test_story_beat_properties(self):
        beat = StoryBeat(
            id="test", name="测试", type="anchor",
            earliest_day=8, latest_day=10,
        )
        assert beat.is_anchor
        assert beat.earliest_week == 2
        assert beat.latest_week == 2
        assert beat.is_eligible(day=9)
        assert not beat.is_eligible(day=7)
        assert not beat.is_eligible(day=11)
        assert beat.is_overdue(day=11)
        assert not beat.is_overdue(day=10)
        assert beat.is_urgent(day=9, window=2)
        assert not beat.is_urgent(day=7, window=2)  # earliest_day=8, day=7 is too early

    def test_story_beat_not_anchor(self):
        beat = StoryBeat(id="test", name="测试", type="key")
        assert not beat.is_anchor

    def test_outline_all_beats_sorted(self):
        arc1 = StoryArc(id="a2", name="", priority=2, beats=[
            StoryBeat(id="b3", name=""), StoryBeat(id="b4", name=""),
        ])
        arc2 = StoryArc(id="a1", name="", priority=0, beats=[
            StoryBeat(id="b1", name=""), StoryBeat(id="b2", name=""),
        ])
        standalone = StoryBeat(id="b0", name="")
        outline = StoryOutline(arcs=[arc1, arc2], standalone_beats=[standalone])
        all_beats = outline.all_beats()
        # standalone first, then by arc priority
        assert all_beats[0].id == "b0"
        # arc2 (priority 0) before arc1 (priority 2)
        assert all_beats[1].id == "b1"
        assert all_beats[4].id == "b4"

    def test_story_state_roundtrip(self):
        state = StoryState()
        state.mark_beat_triggered("b1", 5, "morning", "out_1", ["npc_a"])
        state.arc_progress["arc1"] = 0.5
        state.active_interventions.append(
            Intervention(npc_id="npc_a", type="soft_guidance", description="test")
        )

        data = state.to_dict()
        restored = StoryState.from_dict(data)

        assert restored.is_beat_triggered("b1")
        assert restored.arc_progress["arc1"] == 0.5
        assert len(restored.active_interventions) == 1
        assert restored.active_interventions[0].npc_id == "npc_a"

    def test_story_state_empty_from_dict(self):
        state = StoryState.from_dict({})
        assert state.triggered_beats == {}
        assert state.arc_progress == {}

    def test_triggered_beat_roundtrip(self):
        tb = TriggeredBeat(
            beat_id="b1", triggered_day=5, triggered_slot="morning",
            selected_outcome_id="out_1", participants_present=["a", "b"],
        )
        data = tb.to_dict()
        restored = TriggeredBeat.from_dict(data)
        assert restored.beat_id == "b1"
        assert restored.triggered_day == 5

    def test_intervention_roundtrip(self):
        inv = Intervention(
            npc_id="npc_a", type="hard_orchestration",
            description="move to port", importance=8, force_location="port",
        )
        data = inv.to_dict()
        restored = Intervention.from_dict(data)
        assert restored.npc_id == "npc_a"
        assert restored.type == "hard_orchestration"
        assert restored.force_location == "port"


# ═══════════════════════════════════════════════════
# Story loader
# ═══════════════════════════════════════════════════

class TestStoryLoader:
    """JSON loading and caching tests."""

    def test_load_from_real_file(self):
        clear_cache()
        outline = load_story_outline()
        assert outline is not None
        assert len(outline.arcs) >= 2
        assert len(outline.all_beats()) >= 10
        # Verify anchor beats exist
        anchors = [b for b in outline.all_beats() if b.is_anchor]
        assert len(anchors) >= 5  # at least intro anchors + w2 anchors

    def test_caching(self):
        clear_cache()
        o1 = load_story_outline()
        o2 = load_story_outline()
        assert o1 is o2  # Same object due to module-level cache

    def test_missing_file_returns_none(self):
        clear_cache()
        result = load_story_outline(path="/nonexistent/path.json")
        assert result is None

    def test_beat_parsing_inline_outcomes(self):
        raw = {
            "id": "test_beat", "name": "测试节拍", "type": "opportunity",
            "event_id": "",
            "earliest_day": 5, "latest_day": 10,
            "participants": ["npc_a", "npc_b"],
            "what_must_happen": "something happens",
            "outcomes": [
                {"id": "out_good", "condition": "default",
                 "description": "good ending",
                 "resource_delta": {"yang_de": 2}, "bond_delta": {"bond_a_b": 3}}
            ],
            "on_missed": {"action": "escalate", "description": "things got worse"},
        }
        beat = _parse_beat(raw)
        assert beat.id == "test_beat"
        assert beat.type == "opportunity"
        assert beat.event_id == ""  # inline, not CSV ref
        assert len(beat.outcomes) == 1
        assert beat.outcomes[0].resource_delta == {"yang_de": 2}
        assert beat.outcomes[0].bond_delta == {"bond_a_b": 3}
        assert beat.on_missed is not None
        assert beat.on_missed.action == "escalate"

    def test_beat_parsing_csv_ref(self):
        raw = {
            "id": "test_beat", "name": "测试", "type": "anchor",
            "event_id": "w1_some_event",
            "earliest_day": 1, "latest_day": 1,
            "participants": ["npc_a"],
            "what_must_happen": "thing",
            "outcomes": [],
        }
        beat = _parse_beat(raw)
        assert beat.event_id == "w1_some_event"
        assert len(beat.outcomes) == 0  # No inline, references CSV

    def test_outline_parsing_tone_rules(self):
        raw = {
            "tone_rules": [
                {"id": "r1", "description": "test rule", "applies_to": "weekly",
                 "min_occurrence": 2}
            ],
            "global_constraints": {"max_events_per_slot": 5},
        }
        outline = _parse_outline(raw)
        assert len(outline.tone_rules) == 1
        assert outline.tone_rules[0].min_occurrence == 2
        assert outline.global_constraints.max_events_per_slot == 5


# ═══════════════════════════════════════════════════
# JSON parsing (screenwriter output)
# ═══════════════════════════════════════════════════

class TestScreenwriterParsing:
    """LLM JSON output parsing with 3-tier fallback."""

    def test_parse_valid_json(self):
        text = '{"narrator_insight": "ok", "interventions": [], "triggered_beats": []}'
        result = _parse_llm_output(text)
        assert result is not None
        assert result["narrator_insight"] == "ok"

    def test_parse_json_with_surrounding_text(self):
        text = 'blah blah preamble\n{"interventions": [], "triggered_beats": [], "narrator_insight": "hmm"}\nsome trailing text'
        result = _parse_llm_output(text)
        assert result is not None
        assert result["narrator_insight"] == "hmm"

    def test_parse_json_in_code_block(self):
        text = 'Here is the output:\n```json\n{"narrator_insight": "test", "interventions": [], "triggered_beats": []}\n```\nEnd.'
        result = _parse_llm_output(text)
        assert result is not None
        assert result["narrator_insight"] == "test"

    def test_parse_empty_string(self):
        assert _parse_llm_output("") is None

    def test_parse_garbage(self):
        assert _parse_llm_output("not json at all just random text") is None

    def test_parse_with_interventions(self):
        text = json.dumps({
            "narrator_insight": "tense moment",
            "interventions": [
                {"npc_id": "chen_yuanzhou", "decision": "soft_guidance",
                 "reasoning": "should go to cafe", "memory_to_inject": "港口风大...",
                 "importance": 6},
                {"npc_id": "lin_chaoyin", "decision": "pass", "reasoning": "ok"},
            ],
            "triggered_beats": [
                {"beat_id": "chaoyin_yuanzhou_cafe", "outcome_id": "default",
                 "reasoning": "both at cafe now"},
            ],
        }, ensure_ascii=False)
        result = _parse_llm_output(text)
        assert len(result["interventions"]) == 2
        assert result["interventions"][0]["decision"] == "soft_guidance"
        assert len(result["triggered_beats"]) == 1


# ═══════════════════════════════════════════════════
# Eligible beats & missed handling
# ═══════════════════════════════════════════════════

class TestEligibleBeats:
    """Pre-filtering beats for screenwriter consideration."""

    def test_excludes_already_triggered(self):
        state = StoryState()
        state.mark_beat_triggered("b1", 3, "morning", "o1", [])
        outline = StoryOutline(standalone_beats=[
            StoryBeat(id="b1", name="", earliest_day=1, latest_day=7),
        ])
        eligible = _get_eligible_beats(outline, state, day=4)
        assert len(eligible) == 0

    def test_excludes_too_early(self):
        state = StoryState()
        outline = StoryOutline(standalone_beats=[
            StoryBeat(id="b1", name="", earliest_day=10, latest_day=14),
        ])
        eligible = _get_eligible_beats(outline, state, day=5)
        assert len(eligible) == 0

    def test_includes_within_window(self):
        state = StoryState()
        outline = StoryOutline(standalone_beats=[
            StoryBeat(id="b1", name="", earliest_day=10, latest_day=14),
        ])
        eligible = _get_eligible_beats(outline, state, day=12)
        assert len(eligible) == 1
        assert eligible[0].id == "b1"

    def test_marks_overdue_as_missed(self):
        state = StoryState()
        beat = StoryBeat(
            id="b1", name="", earliest_day=5, latest_day=7,
            on_missed=OnMissedDef(action="escalate", description="things got bad"),
        )
        outline = StoryOutline(standalone_beats=[beat])
        eligible = _get_eligible_beats(outline, state, day=10)
        assert len(eligible) == 0  # Excluded from eligible
        assert state.is_beat_triggered("b1")  # Marked as missed
        tb = state.triggered_beats["b1"]
        assert tb.triggered_slot == "missed"
        assert "__escalate__" in tb.selected_outcome_id

    def test_missed_no_on_missed_config(self):
        state = StoryState()
        beat = StoryBeat(id="b1", name="", earliest_day=5, latest_day=7)
        outline = StoryOutline(standalone_beats=[beat])
        _get_eligible_beats(outline, state, day=10)
        assert state.is_beat_triggered("b1")
        assert "__skip__" in state.triggered_beats["b1"].selected_outcome_id


# ═══════════════════════════════════════════════════
# Event building
# ═══════════════════════════════════════════════════

class TestEventBuilding:
    """Building EventTemplate + Outcome from beat triggers."""

    def _make_session(self):
        """Stub session for tests that don't need real agents."""
        class StubSession:
            class Agents:
                def get(self, npc_id):
                    return None
            agents = Agents()
        return StubSession()

    def test_build_from_beat_with_inline_outcomes(self):
        beat = StoryBeat(
            id="test_beat", name="测试事件", type="key",
            earliest_day=5, latest_day=10,
            participants=["npc_a"],
            what_must_happen="something dramatic",
            outcomes=[
                OutcomeDef(id="out_1", condition="default",
                           description="good", resource_delta={"yang_de": 3})
            ],
        )
        outline = StoryOutline(standalone_beats=[beat])
        session = self._make_session()
        triggers = [{"beat_id": "test_beat", "outcome_id": "out_1"}]
        events = _build_events_from_beats(triggers, outline, session)
        assert len(events) == 1
        template, outcome = events[0]
        assert template.id == "test_beat"
        assert template.event_type == "Key"
        assert template.participants == ["npc_a"]
        assert outcome.resource_delta == {"yang_de": 3}

    def test_build_from_beat_csv_ref_skipped(self):
        """Beats referencing CSV events produce no output here
        (caller handles via CSV match_events)."""
        beat = StoryBeat(
            id="csv_beat", name="CSV事件", type="key",
            event_id="w1_chaoyin_study",
            earliest_day=1, latest_day=7,
            participants=["lin_chaoyin"],
            what_must_happen="study",
            outcomes=[],  # No inline outcomes
        )
        outline = StoryOutline(standalone_beats=[beat])
        session = self._make_session()
        triggers = [{"beat_id": "csv_beat", "outcome_id": ""}]
        events = _build_events_from_beats(triggers, outline, session)
        # No inline outcomes → empty list (CSV handles this beat)
        assert len(events) == 0

    def test_unknown_beat_id_skipped(self):
        outline = StoryOutline()
        session = self._make_session()
        triggers = [{"beat_id": "nonexistent", "outcome_id": "x"}]
        events = _build_events_from_beats(triggers, outline, session)
        assert len(events) == 0

    def test_fallback_to_first_outcome(self):
        beat = StoryBeat(
            id="test_beat", name="测试", type="key",
            earliest_day=1, latest_day=5,
            participants=["npc_a"],
            what_must_happen="thing",
            outcomes=[OutcomeDef(id="o1", description="first", resource_delta={"incense": -1})],
        )
        outline = StoryOutline(standalone_beats=[beat])
        session = self._make_session()
        # Request a non-existent outcome_id → falls back to first
        triggers = [{"beat_id": "test_beat", "outcome_id": "nonexistent"}]
        events = _build_events_from_beats(triggers, outline, session)
        assert len(events) == 1
        assert events[0][1].id == "o1"


# ═══════════════════════════════════════════════════
# Integration (with mock LLM)
# ═══════════════════════════════════════════════════

class TestScreenwriterIntegration:
    """Full screenwriter_think flow with controlled LLM responses."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM client that returns a configurable JSON response."""

        class MockLLM:
            def __init__(self, response):
                self._response = response

            async def chat(self, messages, **kwargs):
                return self._response

            async def is_available(self):
                return True

        return MockLLM

    @pytest.fixture
    def mock_session(self):
        """Minimal session stub for integration tests."""
        from src.backend.engine.resource import ResourceState

        class MockAgents:
            def __init__(self):
                self._agents = {}

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

        return MockSession()

    def test_screenwriter_returns_false_when_llm_none(self, mock_session):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        async def _run():
            return await screenwriter_think(
                session=mock_session,
                story_outline=StoryOutline(),
                day=1, slot=Slot.MORNING, week=1, phase_name="测试",
                npc_intentions=[], llm=None,
            )
        ok, events = asyncio.run(_run())
        assert not ok
        assert events == []

    def test_screenwriter_returns_false_when_outline_none(self, mock_session):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        async def _run():
            return await screenwriter_think(
                session=mock_session,
                story_outline=None,
                day=1, slot=Slot.MORNING, week=1, phase_name="测试",
                npc_intentions=[], llm=None,
            )
        ok, events = asyncio.run(_run())
        assert not ok

    def test_screenwriter_passes_through_valid_json(self, mock_session, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        response = json.dumps({
            "narrator_insight": "all is well",
            "interventions": [],
            "triggered_beats": [],
        }, ensure_ascii=False)
        llm = mock_llm(response)

        async def _run():
            return await screenwriter_think(
                session=mock_session,
                story_outline=StoryOutline(global_constraints=GlobalConstraints(max_events_per_slot=3)),
                day=5, slot=Slot.NOON, week=1, phase_name="织线初启",
                npc_intentions=[
                    ("lin_chaoyin", "林潮音", "去咖啡馆复习", "coffee_shop"),
                ],
                llm=llm,
            )
        ok, events = asyncio.run(_run())
        assert ok
        assert events == []

    def test_screenwriter_triggers_beat(self, mock_session, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        beat = StoryBeat(
            id="test_beat", name="测试事件", type="key",
            earliest_day=1, latest_day=10,
            participants=["lin_chaoyin"],
            what_must_happen="林潮音在咖啡馆遇到什么事",
            outcomes=[OutcomeDef(id="out_1", description="good", resource_delta={"yang_de": 1})],
        )
        outline = StoryOutline(
            standalone_beats=[beat],
            global_constraints=GlobalConstraints(max_events_per_slot=3),
        )
        response = json.dumps({
            "narrator_insight": "good timing",
            "interventions": [],
            "triggered_beats": [
                {"beat_id": "test_beat", "outcome_id": "out_1", "reasoning": "she is at cafe"}
            ],
        }, ensure_ascii=False)
        llm = mock_llm(response)

        async def _run():
            return await screenwriter_think(
                session=mock_session,
                story_outline=outline,
                day=5, slot=Slot.NOON, week=1, phase_name="织线初启",
                npc_intentions=[
                    ("lin_chaoyin", "林潮音", "去咖啡馆复习", "coffee_shop"),
                ],
                llm=llm,
            )
        ok, events = asyncio.run(_run())
        assert ok
        assert len(events) == 1
        template, outcome = events[0]
        assert template.id == "test_beat"
        assert outcome.resource_delta == {"yang_de": 1}
        assert mock_session.story.is_beat_triggered("test_beat")

    def test_screenwriter_applies_soft_guidance(self, mock_session, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot, Location
        from src.backend.ai.npc_agent.agent import NpcAgent
        from src.backend.ai.npc_agent.static import demo_lin_chaoyin

        static = demo_lin_chaoyin()
        agent = NpcAgent(static)
        agent.dynamic.set_location("lin_chaoyin", Location.CAFE)
        mock_session.agents._agents["lin_chaoyin"] = agent

        beat = StoryBeat(
            id="chaoyin_cafe", name="咖啡馆事件", type="opportunity",
            earliest_day=1, latest_day=7,
            participants=["lin_chaoyin"],
            what_must_happen="林潮音在咖啡馆有社交互动",
        )
        outline = StoryOutline(
            standalone_beats=[beat],
            global_constraints=GlobalConstraints(max_events_per_slot=3),
        )
        response = json.dumps({
            "narrator_insight": "",
            "interventions": [
                {"npc_id": "lin_chaoyin", "decision": "soft_guidance",
                 "reasoning": "warm up social scene",
                 "memory_to_inject": "今天咖啡馆里格外热闹，叶可可正在讲一个有趣的八卦。",
                 "importance": 6}
            ],
            "triggered_beats": [],
        }, ensure_ascii=False)
        llm = mock_llm(response)

        async def _run():
            return await screenwriter_think(
                session=mock_session,
                story_outline=outline,
                day=3, slot=Slot.NOON, week=1, phase_name="织线初启",
                npc_intentions=[
                    ("lin_chaoyin", "林潮音", "去咖啡馆复习", "coffee_shop"),
                ],
                llm=llm,
            )
        ok, events = asyncio.run(_run())
        assert ok
        assert events == []
        assert agent.memory.event_count >= 1

    def test_screenwriter_falls_back_on_garbage_json(self, mock_session, mock_llm):
        import asyncio
        from src.backend.ai.screenwriter import screenwriter_think
        from src.backend.models.npc import Slot

        llm = mock_llm("this is not json at all, just some random text from the LLM")

        async def _run():
            return await screenwriter_think(
                session=mock_session,
                story_outline=StoryOutline(),
                day=1, slot=Slot.MORNING, week=1, phase_name="测试",
                npc_intentions=[], llm=llm,
            )
        ok, events = asyncio.run(_run())
        assert not ok
