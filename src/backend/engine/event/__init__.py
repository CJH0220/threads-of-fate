"""Event system — trigger matching + fate coin settlement + consequence execution.

Core loop within the event engine:
    1. Load event templates and outcomes from CSV
    2. Match: filter by time/location/participants, apply weight-based probability
    3. Select outcome: match TriggerCondition against world state
    4. Execute: apply ResourceDelta, NpcStateDelta, and record memories
       (BondDelta, KarmaDelta, TownStateDelta are queued for future modules)

Public API:
    loader.load_events() → list[EventTemplate]
    matcher.match(state, events) → list[tuple[EventTemplate, Outcome]]
    executor.execute(event, outcome, resource_state, agent_manager) → SettlementResult
"""

from src.backend.engine.event.event_types import EventTemplate, Outcome, SettlementResult
from src.backend.engine.event.event_loader import load_events
from src.backend.engine.event.event_matcher import match_events
from src.backend.engine.event.event_executor import execute_event, execute_events

__all__ = [
    "EventTemplate",
    "Outcome",
    "SettlementResult",
    "load_events",
    "match_events",
    "execute_event",
    "execute_events",
]
