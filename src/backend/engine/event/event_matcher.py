"""Event matcher — filter events by time/location and apply weight-based probability."""

import math
import random
import re
from typing import Dict, List, Optional, Tuple

from src.backend.engine.event.event_types import EventTemplate, Outcome
from src.backend.models.npc import Slot


# ── Time helpers ──

def _week_matches(week: int, week_range: str) -> bool:
    """Check if a week number matches a week range string.

    "W1" → week 1, "W2-W4" → weeks 2-4, "Final" → week 9, "" → any
    """
    if not week_range:
        return True

    week_range = week_range.strip()

    # "Final" = week 9
    if week_range.lower() == "final":
        return week == 9

    # "W2-W4"
    range_match = re.match(r"W(\d+)-W(\d+)$", week_range)
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        return lo <= week <= hi

    # "W3"
    single_match = re.match(r"W(\d+)$", week_range)
    if single_match:
        return week == int(single_match.group(1))

    return True  # unknown format → always match


def _day_matches(day: int, day_range: str) -> bool:
    """Check if a day number matches a day range string.

    "Day1" → day 1, "Day3-5" → days 3-5, "" → any
    """
    if not day_range:
        return True

    day_range = day_range.strip()

    # "Day3-5"
    range_match = re.match(r"Day(\d+)-(\d+)$", day_range)
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        return lo <= day <= hi

    # "Day1"
    single_match = re.match(r"Day(\d+)$", day_range)
    if single_match:
        return day == int(single_match.group(1))

    return True


def _slot_matches(slot: Slot, time_slot: str) -> bool:
    """Check if a Slot enum matches a time slot string.

    "Morning" → MORNING, "Night" → NIGHT, "Daytime" → MORNING or NOON,
    "Any" → always, "Afternoon" → NOON, "Noon" → NOON
    """
    if not time_slot or time_slot.strip().lower() == "any":
        return True

    ts = time_slot.strip().lower()

    if ts == "morning":
        return slot == Slot.MORNING
    if ts == "noon" or ts == "afternoon":
        return slot == Slot.NOON
    if ts == "night":
        return slot == Slot.NIGHT
    if ts == "daytime":
        return slot in (Slot.MORNING, Slot.NOON)

    return True


def _location_matches(
    event_location: str,
    participant_locations: Dict[str, str],
) -> bool:
    """Check if NPC locations match the event's required location.

    If event has no location requirement, always match.
    If event requires a location, at least one participant must be there.
    """
    if not event_location:
        return True

    for loc in participant_locations.values():
        if loc == event_location:
            return True
    return False


# ── Probability ──

def _weight_probability(weight: int) -> float:
    """Convert event weight to trigger probability.

    Anchor (weight >= 1000) → 100%
    weight 1 → 10%, 2 → 20%, 3 → 30%, 4 → 40%, 5+ → 50%
    """
    if weight >= 1000:
        return 1.0
    return min(weight / 10.0, 0.5)


# ── Outcome selection ──

def _select_outcome(event: EventTemplate) -> Optional[Outcome]:
    """Select an outcome for a matched event.

    For now: pick "default" outcome if available, otherwise the first one.
    Future: evaluate TriggerCondition against world state.
    """
    if not event.outcomes:
        return None

    # Prefer "default" outcome
    for outcome in event.outcomes:
        if outcome.trigger_condition.lower() == "default":
            return outcome
        if outcome.trigger_condition.lower() == "always":
            return outcome

    # Fallback: first outcome
    return event.outcomes[0]


# ── Main API ──

def match_events(
    events: List[EventTemplate],
    day: int,
    slot: Slot,
    week: int,
    participant_locations: Dict[str, str],
) -> List[Tuple[EventTemplate, Outcome]]:
    """Match events for the current time slice.

    Pipeline:
        1. Filter by time (week range, day range, time slot)
        2. Filter by location
        3. Apply weight-based probability
        4. Select outcome for each matched event

    Args:
        events: all loaded event templates
        day: current day (1-60)
        slot: current time slot
        week: current week (1-9)
        participant_locations: {npc_id: location_string}

    Returns:
        list of (EventTemplate, Outcome) for triggered events
    """
    matched: List[Tuple[EventTemplate, Outcome]] = []

    for event in events:
        # Time filters
        if not _week_matches(week, event.week_range):
            continue
        if not _day_matches(day, event.day_range):
            continue
        if not _slot_matches(slot, event.time_slot):
            continue

        # Location filter
        if not _location_matches(event.location, participant_locations):
            continue

        # Weight-based probability
        prob = _weight_probability(event.weight)
        if prob < 1.0 and random.random() > prob:
            continue

        # Select outcome
        outcome = _select_outcome(event)
        if outcome:
            matched.append((event, outcome))

    # Sort by weight descending (anchor events first)
    matched.sort(key=lambda x: x[0].weight, reverse=True)

    return matched
