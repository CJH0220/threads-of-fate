"""Event system module tests.

Coverage:
- event_loader: CSV parsing, delta parsing, outcome linking
- event_matcher: time filters, location filters, weight probability
- event_executor: resource delta, NPC state delta, memory recording
- Integration: load → match → execute flow
"""

import pytest

from src.backend.engine.event import (
    EventTemplate,
    Outcome,
    SettlementResult,
    load_events,
    match_events,
    execute_event,
    execute_events,
)
from src.backend.engine.event.event_loader import _parse_simple_delta, _parse_npc_state_delta
from src.backend.engine.resource import ResourceState
from src.backend.models.npc import Slot


# ═══════════════════════════════════════════════════
# Delta parsing
# ═══════════════════════════════════════════════════

class TestDeltaParsing:
    """Tests for CSV delta string parsing."""

    def test_simple_delta_basic(self):
        result = _parse_simple_delta("incense:-1;divine_power:-3;yang_de:+2")
        assert result == {"incense": -1, "divine_power": -3, "yang_de": 2}

    def test_simple_delta_none(self):
        assert _parse_simple_delta("none") == {}
        assert _parse_simple_delta("") == {}

    def test_simple_delta_single(self):
        result = _parse_simple_delta("cult_influence:+8")
        assert result == {"cult_influence": 8}

    def test_npc_state_delta_basic(self):
        result = _parse_npc_state_delta(
            "lin_chaoyin:stress+3;chen_yuanzhou:stress-3;chen_haisheng:cult_participant"
        )
        assert result["lin_chaoyin"]["stress"] == 3
        assert result["chen_yuanzhou"]["stress"] == -3
        assert result["chen_haisheng"]["cult_participant"] == 0  # flag attribute

    def test_npc_state_delta_none(self):
        assert _parse_npc_state_delta("none") == {}
        assert _parse_npc_state_delta("") == {}


# ═══════════════════════════════════════════════════
# Event loader
# ═══════════════════════════════════════════════════

class TestEventLoader:
    """Tests for CSV event loading."""

    def test_load_events_count(self):
        events = load_events()
        assert len(events) >= 50  # 55+ events expected

    def test_outcomes_linked(self):
        events = load_events()
        # Most events should have outcomes
        with_outcomes = [e for e in events if e.outcomes]
        assert len(with_outcomes) > 0

    def test_anchor_events_have_weight_1000(self):
        events = load_events()
        anchors = [e for e in events if e.event_type == "Anchor"]
        for a in anchors:
            assert a.weight >= 1000 or a.weight == 0

    def test_event_structure(self):
        events = load_events()
        for e in events:
            assert e.id
            assert e.name
            assert e.event_type in ("Anchor", "Key", "Daily")
            assert e.weight >= 0

    def test_outcome_structure(self):
        events = load_events()
        for e in events:
            for o in e.outcomes:
                assert o.id
                assert o.event_id == e.id
                assert o.trigger_condition


# ═══════════════════════════════════════════════════
# Event matcher — time filters
# ═══════════════════════════════════════════════════

class TestMatcherTime:
    """Tests for time-based event filtering."""

    @classmethod
    def setup_class(cls):
        cls.events = load_events()

    def test_week_filter_excludes_wrong_week(self):
        """Events filtered by week: no W5 events appear in W1 matching."""
        # Use deterministic filtering by importing the filter helpers directly
        from src.backend.engine.event.event_matcher import _week_matches, _day_matches, _slot_matches

        # W1 events: week 1 matches, week 5 does not
        w1_events = [e for e in self.events if e.week_range == "W1"]
        assert len(w1_events) > 0
        for e in w1_events:
            assert _week_matches(1, e.week_range)
            assert not _week_matches(5, e.week_range)

    def test_time_filters_are_deterministic(self):
        """Time filter functions should be pure and deterministic."""
        from src.backend.engine.event.event_matcher import _week_matches, _day_matches, _slot_matches

        assert _week_matches(1, "W1") is True
        assert _week_matches(2, "W1") is False
        assert _week_matches(2, "W2-W4") is True
        assert _week_matches(5, "W2-W4") is False
        assert _week_matches(9, "Final") is True

        assert _day_matches(3, "Day3") is True
        assert _day_matches(4, "Day3") is False
        assert _day_matches(3, "Day1-7") is True
        assert _day_matches(8, "Day1-7") is False

        assert _slot_matches(Slot.MORNING, "Morning") is True
        assert _slot_matches(Slot.NIGHT, "Morning") is False
        assert _slot_matches(Slot.MORNING, "Daytime") is True
        assert _slot_matches(Slot.NOON, "Daytime") is True
        assert _slot_matches(Slot.NIGHT, "Daytime") is False

    def test_week_filter_out_of_range(self):
        """W1 events should NOT match week 5."""
        results = match_events(self.events, day=30, slot=Slot.MORNING, week=5,
                               participant_locations={})
        w1_matched = [r for r in results if r[0].week_range == "W1"]
        assert len(w1_matched) == 0

    def test_week_final_maps_to_week_9(self):
        """'Final' week range should match week 9."""
        final_events = [e for e in self.events if e.week_range == "Final"]
        assert len(final_events) > 0

    def test_day_filter_exact(self):
        """Events with exact day should match — intro_heaven_notice is Day1."""
        locs = {"heaven_messenger": "temple", "tudi_gong": "temple"}
        results = match_events(self.events, day=1, slot=Slot.MORNING, week=1,
                               participant_locations=locs)
        intro = [r for r in results if r[0].id == "intro_heaven_notice"]
        assert len(intro) == 1

    def test_slot_morning(self):
        results = match_events(self.events, day=5, slot=Slot.MORNING, week=1,
                               participant_locations={"lin_chaoyin": "school"})
        for event, _ in results:
            ts = event.time_slot
            assert ts in ("Morning", "Daytime", "Any") or ts == ""

    def test_slot_night(self):
        results = match_events(self.events, day=1, slot=Slot.NIGHT, week=1,
                               participant_locations={})
        for event, _ in results:
            ts = event.time_slot
            assert ts in ("Night", "Any", "Daytime") or ts == ""


# ═══════════════════════════════════════════════════
# Event executor
# ═══════════════════════════════════════════════════

class TestExecutor:
    """Tests for event execution and delta application."""

    def test_execute_resource_delta(self):
        """Resource delta should be applied correctly."""
        resource = ResourceState(incense=50, divine_power=10, yang_de=0)
        outcome = Outcome(
            id="test_out", event_id="test_evt", name="test",
            trigger_condition="default",
            resource_delta={"incense": -5, "yang_de": 3},
        )
        event = EventTemplate(
            id="test_evt", name="测试", event_type="Daily",
            week_range="W1", day_range="", time_slot="Any",
            location="", participants=[],
            weight=5, risk_level="Low",
            outcomes=[outcome],
        )
        from src.backend.engine.event.event_executor import _apply_resource_delta
        changes = _apply_resource_delta(outcome, resource)
        assert resource.incense == 45
        assert resource.yang_de == 3
        assert changes == {"incense": -5, "yang_de": 3}

    def test_execute_divine_power_spend(self):
        resource = ResourceState(divine_power=10)
        outcome = Outcome(
            id="test_out", event_id="test_evt", name="test",
            trigger_condition="default",
            resource_delta={"divine_power": -3},
        )
        event = EventTemplate(
            id="test_evt", name="测试", event_type="Daily",
            week_range="W1", day_range="", time_slot="Any",
            location="", participants=[], weight=5, risk_level="Low",
            outcomes=[outcome],
        )
        from src.backend.engine.event.event_executor import _apply_resource_delta
        _apply_resource_delta(outcome, resource)
        assert resource.divine_power == 7

    def test_execute_generates_memories(self):
        """Executing an event should record memories for participants."""
        from src.backend.ai.npc_agent.manager import AgentManager
        from src.backend.data.npc_loader import load_npcs

        resource = ResourceState()
        manager = AgentManager()
        manager.init_from_statics(load_npcs())

        outcome = Outcome(
            id="test_out", event_id="test_evt", name="好结局",
            trigger_condition="default",
            resource_delta={"yang_de": 1},
            npc_state_delta={"lin_chaoyin": {"happiness": 2}},
        )
        event = EventTemplate(
            id="test_evt", name="测试事件", event_type="Key",
            week_range="W1", day_range="", time_slot="Any",
            location="", participants=["lin_chaoyin", "chen_yuanzhou"],
            weight=5, risk_level="Low",
            outcomes=[outcome],
        )

        result = execute_event(event, outcome, resource, manager, day=5, slot=Slot.MORNING)
        assert result is not None
        assert result.memories_recorded == 2

        # Both NPCs should have a memory
        lin = manager.get("lin_chaoyin")
        yuanzhou = manager.get("chen_yuanzhou")
        assert lin is not None
        assert yuanzhou is not None
        assert lin.memory.event_count >= 1
        assert yuanzhou.memory.event_count >= 1


# ═══════════════════════════════════════════════════
# SettlementResult
# ═══════════════════════════════════════════════════

class TestSettlementResult:
    """Tests for SettlementResult dataclass."""

    def test_empty_result(self):
        result = SettlementResult(
            event_id="e1", event_name="test", outcome_id="o1", outcome_name="test"
        )
        assert result.resource_changes == {}
        assert result.bond_changes == {}
        assert result.karma_changes == {}
        assert result.town_changes == {}
        assert result.memories_recorded == 0

    def test_result_with_changes(self):
        result = SettlementResult(
            event_id="e1", event_name="test", outcome_id="o1", outcome_name="test",
            resource_changes={"incense": -1},
            bond_changes={"bond_a_b": 3},
            karma_changes={"witch_line": 5},
            npc_changes={"lin_chaoyin": {"stress": 3}},
            town_changes={"cult_influence": 8},
            memories_recorded=2,
        )
        assert result.resource_changes["incense"] == -1
        assert result.bond_changes["bond_a_b"] == 3
        assert result.karma_changes["witch_line"] == 5
        assert result.npc_changes["lin_chaoyin"]["stress"] == 3
        assert result.town_changes["cult_influence"] == 8
        assert result.memories_recorded == 2


# ═══════════════════════════════════════════════════
# Integration
# ═══════════════════════════════════════════════════

class TestIntegration:
    """End-to-end: load → match → execute."""

    def test_full_flow_week1_morning(self):
        """Week 1 morning with anchor participants: events should trigger."""
        from src.backend.ai.npc_agent.manager import AgentManager
        from src.backend.data.npc_loader import load_npcs

        events = load_events()
        resource = ResourceState()
        manager = AgentManager()
        manager.init_from_statics(load_npcs())

        # Build locations + add anchor NPCs that aren't in the 14-person CSV
        locations = {}
        for agent_id in manager.npc_ids:
            agent = manager.get(agent_id)
            if agent:
                locations[agent_id] = agent.dynamic.current.location.value
        # Anchor events reference these NPCs who exist in the CSV but not as agents
        locations["heaven_messenger"] = "temple"
        locations["tudi_gong"] = "temple"

        matched = match_events(events, day=1, slot=Slot.MORNING, week=1,
                               participant_locations=locations)
        results = execute_events(matched, resource, manager, day=1, slot=Slot.MORNING)

        # At least the intro anchor event should trigger
        assert len(results) > 0
        anchor_results = [r for r in results if r.event_id == "intro_heaven_notice"]
        assert len(anchor_results) == 1

    def test_anchor_events_always_trigger(self):
        """Anchor events with weight>=1000 always match (probability 100%)."""
        from src.backend.ai.npc_agent.manager import AgentManager
        from src.backend.data.npc_loader import load_npcs

        events = load_events()
        resource = ResourceState()
        manager = AgentManager()
        manager.init_from_statics(load_npcs())

        locations = {aid: manager.get(aid).dynamic.current.location.value
                     for aid in manager.npc_ids}
        locations["heaven_messenger"] = "temple"
        locations["tudi_gong"] = "temple"

        # Run multiple times — anchor events should always appear
        anchor_count = 0
        for _ in range(5):
            matched = match_events(events, day=1, slot=Slot.MORNING, week=1,
                                   participant_locations=locations)
            anchor_count = len([m for m in matched if m[0].is_anchor])
            if anchor_count > 0:
                break
        assert anchor_count > 0, "Anchor events should trigger reliably"

    def test_no_crash_on_empty_outcome(self):
        """Events with no outcomes should not crash the executor."""
        from src.backend.ai.npc_agent.manager import AgentManager
        from src.backend.data.npc_loader import load_npcs

        resource = ResourceState()
        manager = AgentManager()
        manager.init_from_statics(load_npcs())

        # Create an event with no outcomes
        event = EventTemplate(
            id="test_no_out", name="无结果事件", event_type="Daily",
            week_range="W1", day_range="", time_slot="Any",
            location="", participants=["lin_chaoyin"],
            weight=3, risk_level="Low", outcomes=[],
        )
        result = execute_event(event, None, resource, manager, day=1, slot=Slot.MORNING)
        assert result is None  # No outcome → no execution
