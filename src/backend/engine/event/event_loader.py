"""Event CSV loader — reads event config and outcome CSVs into typed objects."""

import csv
import os
import re
from typing import Dict, List, Optional, Tuple

from src.backend.engine.event.event_types import EventTemplate, Outcome


# ── Default CSV paths ──

def _design_data_dir() -> str:
    backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return os.path.join(backend, os.pardir, "design", "data")


_EVENT_CSV = os.path.join(_design_data_dir(), "事件配置表.csv")
_OUTCOME_CSV = os.path.join(_design_data_dir(), "事件结果表.csv")


# ── Delta parsers ──

def _parse_simple_delta(raw: str) -> Dict[str, int]:
    """Parse "incense:-1;divine_power:-3;yang_de:+2" → {"incense": -1, ...}"""
    result: Dict[str, int] = {}
    if not raw or raw.strip().lower() in ("none", ""):
        return result
    for part in raw.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, val = part.split(":", 1)
        result[key.strip()] = int(val.strip())
    return result


def _parse_npc_state_delta(raw: str) -> Dict[str, Dict[str, int]]:
    """Parse "lin_chaoyin:stress+3;chen_yuanzhou:happiness-2" → nested dict."""
    result: Dict[str, Dict[str, int]] = {}
    if not raw or raw.strip().lower() in ("none", ""):
        return result
    for part in raw.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        npc_id, rest = part.split(":", 1)
        npc_id = npc_id.strip()
        if npc_id not in result:
            result[npc_id] = {}
        # rest can be "stress+3" or "settled" (flag, no value)
        attr_match = re.match(r"(\w+)([+-]\d+)", rest.strip())
        if attr_match:
            attr = attr_match.group(1)
            val = int(attr_match.group(2))
            result[npc_id][attr] = val
        else:
            result[npc_id][rest.strip()] = 0  # flag attribute
    return result


def _parse_participants(raw: str) -> List[str]:
    """Parse "lin_chaoyin;chen_yuanzhou" → ["lin_chaoyin", "chen_yuanzhou"]"""
    if not raw or raw.strip().lower() in ("none", "", "all_npc"):
        return []
    return [p.strip() for p in raw.split(";") if p.strip()]


# ── Loaders ──

def load_outcomes(path: Optional[str] = None) -> Dict[str, List[Outcome]]:
    """Load outcomes from CSV, keyed by EventId.

    Returns:
        {event_id: [Outcome, ...]}
    """
    path = path or _OUTCOME_CSV
    outcomes: Dict[str, List[Outcome]] = {}

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            oid = row.get("OutcomeId", "").strip()
            eid = row.get("EventId", "").strip()
            if not oid or not eid:
                continue

            outcome = Outcome(
                id=oid,
                event_id=eid,
                name=row.get("OutcomeName", "").strip(),
                trigger_condition=row.get("TriggerCondition", "default").strip(),
                resource_delta=_parse_simple_delta(row.get("ResourceDelta", "")),
                bond_delta=_parse_simple_delta(row.get("BondDelta", "")),
                karma_delta=_parse_simple_delta(row.get("KarmaDelta", "")),
                npc_state_delta=_parse_npc_state_delta(row.get("NpcStateDelta", "")),
                town_state_delta=_parse_simple_delta(row.get("TownStateDelta", "")),
                follow_up_event_ids=_parse_participants(row.get("FollowUpEventIds", "")),
                history_key=row.get("HistorySummaryKey", "").strip(),
                description=row.get("Description", "").strip(),
            )
            if eid not in outcomes:
                outcomes[eid] = []
            outcomes[eid].append(outcome)

    return outcomes


def load_events(
    event_path: Optional[str] = None,
    outcome_path: Optional[str] = None,
) -> List[EventTemplate]:
    """Load all event templates with their outcomes attached.

    Args:
        event_path: path to 事件配置表.csv
        outcome_path: path to 事件结果表.csv

    Returns:
        list of EventTemplate, each with outcomes populated
    """
    event_path = event_path or _EVENT_CSV
    outcome_path = outcome_path or _OUTCOME_CSV

    outcomes_by_event = load_outcomes(outcome_path)

    events: List[EventTemplate] = []
    with open(event_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            eid = row.get("EventId", "").strip()
            if not eid:
                continue

            template = EventTemplate(
                id=eid,
                name=row.get("EventName", "").strip(),
                event_type=row.get("EventType", "").strip(),
                week_range=row.get("WeekRange", "").strip(),
                day_range=row.get("DayRange", "").strip(),
                time_slot=row.get("TimeSlot", "").strip(),
                location=row.get("LocationId", "").strip(),
                participants=_parse_participants(row.get("ParticipantNpcIds", "")),
                weight=int(row.get("TriggerWeight", 1)),
                risk_level=row.get("RiskLevel", "Low").strip(),
                ai_text_policy=row.get("AiTextPolicy", "None").strip(),
                outcomes=outcomes_by_event.get(eid, []),
                description=row.get("Description", "").strip(),
            )
            events.append(template)

    return events
