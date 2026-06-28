"""Time system — pure timer module for game time.

Advancement algorithm:
    MORNING → NOON → NIGHT → next day MORNING → ...
    3 slots per day, 60 days = 180 decision windows.
    Week derived from day: ceil(day / 7).
    Week settlement triggered by orchestrator when is_new_week is detected.

Public API:
    state.advance()       → TimeAdvanceResult   # advance one slot
    state.can_advance()   → bool                 # endgame check
    state.peek()          → TimeAdvanceResult    # preview without modifying
    state.to_dict()       → dict                 # serialize
    TimeState.from_dict(d) → TimeState           # deserialize
    get_phase(week)       → WeekPhase            # lookup week phase table
"""

from src.backend.engine.time.time_state import TimeState, TimeAdvanceResult, GameTimeExceededError
from src.backend.engine.time.week_phases import WeekPhase, PHASES, get_phase

__all__ = [
    "TimeState",
    "TimeAdvanceResult",
    "GameTimeExceededError",
    "WeekPhase",
    "PHASES",
    "get_phase",
]
