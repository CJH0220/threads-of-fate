"""Time system module tests.

Coverage:
- time_state: advance, can_advance, peek, to_dict, from_dict
- week_phases: get_phase, PHASES integrity
- edge cases: endgame boundary, serialization round-trip, full 60-day walk
"""

import pytest

from src.backend.models.npc import Slot
from src.backend.engine.time import (
    TimeState,
    TimeAdvanceResult,
    GameTimeExceededError,
    WeekPhase,
    PHASES,
    get_phase,
)


# ═══════════════════════════════════════════════════
# Week phases
# ═══════════════════════════════════════════════════

class TestWeekPhases:
    """Tests for PHASES table and get_phase()."""

    def test_phases_count(self):
        """9 phases total."""
        assert len(PHASES) == 9

    def test_phases_week_numbers_are_sequential(self):
        """Week numbers should be 1-9."""
        for i, phase in enumerate(PHASES, start=1):
            assert phase.week == i

    def test_get_phase_returns_correct_phase(self):
        """Each week maps to its correct phase name."""
        expected = [
            "旧神将熄", "外来者入潮", "异常初显",
            "命运交错", "潮声入梦", "信仰裂缝",
            "庙会争夺", "终局锁定", "潮落见神",
        ]
        for i, name in enumerate(expected, start=1):
            assert get_phase(i).name == name

    def test_get_phase_invalid_week(self):
        """Invalid week numbers raise ValueError."""
        with pytest.raises(ValueError, match="Invalid week number"):
            get_phase(0)
        with pytest.raises(ValueError, match="Invalid week number"):
            get_phase(10)

    def test_all_phases_have_all_fields(self):
        """Every phase must have non-empty name and theme."""
        for phase in PHASES:
            assert phase.name
            assert phase.theme
            assert phase.day_range
            assert 1 <= phase.week <= 9


# ═══════════════════════════════════════════════════
# Initial state
# ═══════════════════════════════════════════════════

class TestInitialState:
    """Tests for default TimeState."""

    def test_default_state(self):
        state = TimeState()
        assert state.day == 1
        assert state.slot == Slot.MORNING
        assert state.week == 1
        assert state.phase_name == "旧神将熄"

    def test_can_advance_at_start(self):
        state = TimeState()
        assert state.can_advance() is True


# ═══════════════════════════════════════════════════
# Normal advance
# ═══════════════════════════════════════════════════

class TestAdvance:
    """Tests for advance() normal operation."""

    def test_morning_to_noon(self):
        state = TimeState(day=3, slot=Slot.MORNING)
        result = state.advance()
        assert state.slot == Slot.NOON
        assert state.day == 3
        assert result.is_new_day is False
        assert result.is_new_week is False

    def test_noon_to_night(self):
        state = TimeState(day=3, slot=Slot.NOON)
        result = state.advance()
        assert state.slot == Slot.NIGHT
        assert state.day == 3
        assert result.is_new_day is False
        assert result.is_new_week is False

    def test_night_to_next_morning(self):
        """NIGHT advance crosses into next day MORNING."""
        state = TimeState(day=3, slot=Slot.NIGHT)
        result = state.advance()
        assert state.slot == Slot.MORNING
        assert state.day == 4
        assert result.is_new_day is True

    def test_day_increments_after_full_cycle(self):
        """3 advances = one full day."""
        state = TimeState(day=5, slot=Slot.MORNING)
        state.advance()  # → NOON
        state.advance()  # → NIGHT
        state.advance()  # → day 6 MORNING
        assert state.day == 6
        assert state.slot == Slot.MORNING

    def test_result_day_and_slot_match_state(self):
        """After advance(), result fields match the new state."""
        state = TimeState(day=10, slot=Slot.NOON)
        result = state.advance()
        assert result.day == state.day
        assert result.slot == state.slot
        assert result.week == state.week


# ═══════════════════════════════════════════════════
# Cross-week detection
# ═══════════════════════════════════════════════════

class TestCrossWeek:
    """Tests for is_new_week detection."""

    def test_cross_week_day7_to_day8(self):
        """Day 7 NIGHT → Day 8 MORNING triggers new week."""
        state = TimeState(day=7, slot=Slot.NIGHT)
        result = state.advance()
        assert state.day == 8
        assert result.is_new_day is True
        assert result.is_new_week is True
        assert result.week == 2
        assert result.phase_name == "外来者入潮"

    def test_cross_week_day14_to_day15(self):
        state = TimeState(day=14, slot=Slot.NIGHT)
        result = state.advance()
        assert result.is_new_week is True
        assert result.week == 3
        assert result.phase_name == "异常初显"

    def test_cross_week_day56_to_day57(self):
        """Last cross-week: week 8 → week 9."""
        state = TimeState(day=56, slot=Slot.NIGHT)
        result = state.advance()
        assert result.is_new_week is True
        assert result.week == 9
        assert result.phase_name == "潮落见神"

    def test_no_cross_week_mid_week(self):
        """Day 5 NIGHT → Day 6 MORNING: new day but not new week."""
        state = TimeState(day=5, slot=Slot.NIGHT)
        result = state.advance()
        assert result.is_new_day is True
        assert result.is_new_week is False

    def test_all_week_boundaries(self):
        """Verify all 8 cross-week boundaries."""
        boundaries = [7, 14, 21, 28, 35, 42, 49, 56]
        for day in boundaries:
            state = TimeState(day=day, slot=Slot.NIGHT)
            result = state.advance()
            assert result.is_new_week is True, f"Day {day} should cross week"
            assert result.day == day + 1


# ═══════════════════════════════════════════════════
# Endgame
# ═══════════════════════════════════════════════════

class TestEndgame:
    """Tests for game-end boundary."""

    def test_can_advance_day60_night_is_false(self):
        state = TimeState(day=60, slot=Slot.NIGHT)
        assert state.can_advance() is False

    def test_can_advance_day60_morning_is_true(self):
        state = TimeState(day=60, slot=Slot.MORNING)
        assert state.can_advance() is True

    def test_can_advance_day60_noon_is_true(self):
        state = TimeState(day=60, slot=Slot.NOON)
        assert state.can_advance() is True

    def test_advance_day60_night_raises(self):
        state = TimeState(day=60, slot=Slot.NIGHT)
        with pytest.raises(GameTimeExceededError):
            state.advance()

    def test_peek_day60_night_raises(self):
        state = TimeState(day=60, slot=Slot.NIGHT)
        with pytest.raises(GameTimeExceededError):
            state.peek()

    def test_exception_contains_day_and_slot(self):
        state = TimeState(day=60, slot=Slot.NIGHT)
        with pytest.raises(GameTimeExceededError) as exc_info:
            state.advance()
        assert exc_info.value.day == 60
        assert exc_info.value.slot == Slot.NIGHT

    def test_day60_noon_to_night_is_last_valid_advance(self):
        """Day 60 NOON → NIGHT: the final valid advance."""
        state = TimeState(day=60, slot=Slot.NOON)
        result = state.advance()
        assert state.slot == Slot.NIGHT
        assert result.is_new_day is False
        assert state.can_advance() is False  # now at terminal


# ═══════════════════════════════════════════════════
# Peek
# ═══════════════════════════════════════════════════

class TestPeek:
    """Tests for peek() — preview without mutation."""

    def test_peek_does_not_modify_state(self):
        state = TimeState(day=5, slot=Slot.MORNING)
        original_day = state.day
        original_slot = state.slot
        result = state.peek()
        assert state.day == original_day
        assert state.slot == original_slot
        # result should describe the NEXT state
        assert result.slot == Slot.NOON
        assert result.day == 5

    def test_peek_shows_cross_day(self):
        state = TimeState(day=7, slot=Slot.NIGHT)
        result = state.peek()
        assert result.is_new_day is True
        assert result.is_new_week is True
        assert result.day == 8
        # state unchanged
        assert state.day == 7
        assert state.slot == Slot.NIGHT

    def test_peek_then_advance_gives_same_result(self):
        """peek() result should match advance() result fields."""
        state = TimeState(day=10, slot=Slot.NIGHT)
        peek_result = state.peek()
        adv_result = state.advance()
        # compare the result objects
        assert peek_result.day == adv_result.day
        assert peek_result.slot == adv_result.slot
        assert peek_result.week == adv_result.week
        assert peek_result.is_new_day == adv_result.is_new_day
        assert peek_result.is_new_week == adv_result.is_new_week
        assert peek_result.phase_name == adv_result.phase_name


# ═══════════════════════════════════════════════════
# Serialization
# ═══════════════════════════════════════════════════

class TestSerialization:
    """Tests for to_dict() / from_dict() round-trip."""

    def test_to_dict_basic(self):
        state = TimeState(day=15, slot=Slot.NIGHT)
        d = state.to_dict()
        assert d == {"day": 15, "slot": "night"}

    def test_to_dict_default(self):
        state = TimeState()
        d = state.to_dict()
        assert d == {"day": 1, "slot": "morning"}

    def test_from_dict_basic(self):
        state = TimeState.from_dict({"day": 30, "slot": "noon"})
        assert state.day == 30
        assert state.slot == Slot.NOON

    def test_round_trip(self):
        """to_dict → from_dict should produce equivalent state."""
        original = TimeState(day=42, slot=Slot.NIGHT)
        data = original.to_dict()
        restored = TimeState.from_dict(data)
        assert restored.day == original.day
        assert restored.slot == original.slot
        assert restored.week == original.week
        assert restored.phase_name == original.phase_name

    def test_from_dict_missing_fields_use_defaults(self):
        state = TimeState.from_dict({})
        assert state.day == 1
        assert state.slot == Slot.MORNING

    def test_from_dict_invalid_day_low(self):
        with pytest.raises(ValueError, match="Invalid day"):
            TimeState.from_dict({"day": 0, "slot": "morning"})

    def test_from_dict_invalid_day_high(self):
        with pytest.raises(ValueError, match="Invalid day"):
            TimeState.from_dict({"day": 61, "slot": "morning"})

    def test_from_dict_invalid_day_type(self):
        with pytest.raises(ValueError, match="Invalid day"):
            TimeState.from_dict({"day": "abc", "slot": "morning"})

    def test_from_dict_invalid_slot(self):
        with pytest.raises(ValueError, match="Invalid slot value"):
            TimeState.from_dict({"day": 1, "slot": "midnight"})


# ═══════════════════════════════════════════════════
# Full 60-day walk
# ═══════════════════════════════════════════════════

class TestFullWalk:
    """Tests that walk through the entire 60-day game cycle."""

    def test_full_60_days(self):
        """Walk through all 180 slots and verify final state."""
        state = TimeState()
        advances = 0
        while state.can_advance():
            result = state.advance()
            advances += 1
            # invariants
            assert 1 <= state.day <= 60
            assert state.slot in (Slot.MORNING, Slot.NOON, Slot.NIGHT)
            assert 1 <= state.week <= 9
        # after loop: day=60, slot=NIGHT, 179 advances total
        assert state.day == 60
        assert state.slot == Slot.NIGHT
        assert advances == 179  # 180 slots - 1 initial = 179 advances

    def test_week_boundaries_in_full_walk(self):
        """Verify week numbers at each cross-week point during full walk."""
        state = TimeState()
        cross_weeks_seen = set()
        while state.can_advance():
            result = state.advance()
            if result.is_new_week:
                cross_weeks_seen.add(result.week)
        # Should have crossed into weeks 2-9 (week 1 is the start)
        assert cross_weeks_seen == {2, 3, 4, 5, 6, 7, 8, 9}

    def test_phase_changes_during_full_walk(self):
        """Verify phase names change correctly across all weeks."""
        state = TimeState()
        phases_seen = []
        current_phase = state.phase_name
        phases_seen.append(current_phase)
        while state.can_advance():
            result = state.advance()
            if result.is_new_week:
                phases_seen.append(result.phase_name)
        assert phases_seen == [
            "旧神将熄", "外来者入潮", "异常初显",
            "命运交错", "潮声入梦", "信仰裂缝",
            "庙会争夺", "终局锁定", "潮落见神",
        ]
