"""Time state — pure timer module for game time.

Responsible for maintaining current day and slot, and providing advance/peek/serialize.
Does NOT handle event settlement, resource updates, or endgame judgment — those belong
to the orchestrator (future GameSession).

Core algorithm:
    MORNING → NOON → NIGHT → next day MORNING → ...
    3 slots per day, 60 days = 180 decision windows.
    week = ceil(day / 7), new_week detection = (day - 1) % 7 == 0.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict

from src.backend.models.npc import Slot
from src.backend.engine.time.week_phases import get_phase


# ── Main state ──

@dataclass
class TimeState:
    """Mutable game time state.

    Only stores two core fields: day and slot. Week and phase_name are derived.
    Mutable by design — advance() modifies self in place.
    """
    day: int = 1
    slot: Slot = Slot.MORNING

    # ── Derived properties ──

    @property
    def week(self) -> int:
        """Current week number, derived from day: ceil(day / 7)."""
        return math.ceil(self.day / 7)

    @property
    def phase_name(self) -> str:
        """Current week phase name, looked up from phase table."""
        return get_phase(self.week).name

    # ── Public methods ──

    def advance(self) -> "TimeAdvanceResult":
        """Advance by one time slot.

        Modifies self (day / slot) in place and returns a result describing
        what changed.

        Returns:
            TimeAdvanceResult with post-advance day, slot, week, cross-day/Week flags, phase name

        Raises:
            GameTimeExceededError: if day=60 and slot=NIGHT — game is already over
        """
        if not self.can_advance():
            raise GameTimeExceededError(self.day, self.slot)
        return self._do_advance()

    def can_advance(self) -> bool:
        """Check whether time can advance further.

        Returns False when day=60 and slot=NIGHT — orchestrator should
        run endgame judgment instead of calling advance().

        Returns:
            True if more slots remain in the game
        """
        return not (self.day >= 60 and self.slot == Slot.NIGHT)

    def peek(self) -> "TimeAdvanceResult":
        """Preview what advance() would return, without modifying state.

        Encapsulates new-week computation so external code doesn't need to
        duplicate the logic.

        Returns:
            TimeAdvanceResult — hypothetical result of advancing

        Raises:
            GameTimeExceededError: if day=60 and slot=NIGHT
        """
        if not self.can_advance():
            raise GameTimeExceededError(self.day, self.slot)
        return self._compute_result(*self._next_slot(self.day, self.slot))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dictionary.

        Only stores the two core fields (day, slot). Derived info (week, phase)
        is not stored to avoid data inconsistency.

        Returns:
            {"day": 15, "slot": "night"}
        """
        return {"day": self.day, "slot": self.slot.value}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimeState":
        """Deserialize from a dictionary.

        Validates day (1-60) and slot (valid enum value).

        Args:
            data: {"day": 15, "slot": "night"}

        Returns:
            TimeState instance

        Raises:
            ValueError: day not in 1-60 or slot not a valid Slot value
        """
        day = data.get("day", 1)
        slot_value = data.get("slot", "morning")

        try:
            slot = Slot(slot_value)
        except ValueError:
            raise ValueError(f"Invalid slot value: {slot_value}, expected: morning, noon, night")

        if not isinstance(day, int) or not (1 <= day <= 60):
            raise ValueError(f"Invalid day: {day}, expected integer in 1-60")

        return cls(day=day, slot=slot)

    # ── Internal ──

    def _do_advance(self) -> "TimeAdvanceResult":
        """Execute advance: compute next state, mutate self, build result."""
        new_day, new_slot = self._next_slot(self.day, self.slot)
        self.day = new_day
        self.slot = new_slot
        return self._compute_result(new_day, new_slot)

    @staticmethod
    def _next_slot(day: int, slot: Slot):
        """Pure function: compute the next slot and day.

        MORNING → NOON    (same day)
        NOON   → NIGHT    (same day)
        NIGHT  → MORNING  (day + 1)
        """
        if slot == Slot.MORNING:
            return day, Slot.NOON
        elif slot == Slot.NOON:
            return day, Slot.NIGHT
        else:  # NIGHT → next day MORNING
            return day + 1, Slot.MORNING

    @staticmethod
    def _compute_result(day: int, slot: Slot) -> "TimeAdvanceResult":
        """Pure function: build a TimeAdvanceResult from day and slot."""
        week = math.ceil(day / 7)
        is_new_day = (slot == Slot.MORNING)  # just crossed into morning → new day
        is_new_week = is_new_day and ((day - 1) % 7 == 0)  # only checked on new day
        phase = get_phase(week)
        return TimeAdvanceResult(
            slot=slot,
            day=day,
            week=week,
            is_new_day=is_new_day,
            is_new_week=is_new_week,
            phase_name=phase.name,
        )


# ── Result & exception ──

@dataclass
class TimeAdvanceResult:
    """Describes what changed after a time advance.

    Returned by advance() and peek(). The orchestrator uses these flags:
    - event engine: matches slot to trigger conditions
    - resource engine: checks is_new_day to deduct daily incense (-1)
    - orchestrator: checks is_new_week to trigger week settlement
    - frontend HUD: day + slot for display
    - LLM prompt: phase_name injected as current atmosphere
    """
    slot: Slot
    day: int
    week: int
    is_new_day: bool
    is_new_week: bool
    phase_name: str


class GameTimeExceededError(Exception):
    """Raised when trying to advance past day 60 NIGHT — the game has ended.

    The orchestrator should catch this and trigger endgame judgment (§5.2).
    """
    def __init__(self, day: int, slot: Slot):
        super().__init__(
            f"Game time exceeded: day {day} slot {slot.value} is the final slot. "
            f"Run endgame judgment instead."
        )
        self.day = day
        self.slot = slot
