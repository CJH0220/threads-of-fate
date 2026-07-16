"""Story outline JSON loader.

Reads design/data/story_outline.json into typed StoryOutline objects.
Cached after first load — static data does not change mid-game.
"""

import json
import os
from typing import Dict, List, Optional

from src.backend.engine.story.story_types import (
    GlobalConstraints,
    OnMissedDef,
    OutcomeDef,
    StoryArc,
    StoryBeat,
    StoryOutline,
    ToneRule,
)


# ── Path resolution ──

def _design_data_dir() -> str:
    backend = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return os.path.join(backend, os.pardir, "design", "data")


_STORY_JSON = os.path.join(_design_data_dir(), "story_outline.json")
_CACHED_OUTLINE: Optional[StoryOutline] = None


# ── Parsers ──

def _parse_outcome(raw: dict) -> OutcomeDef:
    return OutcomeDef(
        id=raw.get("id", ""),
        condition=raw.get("condition", "default"),
        description=raw.get("description", ""),
        resource_delta=_parse_dict_int(raw.get("resource_delta", {})),
        bond_delta=_parse_dict_int(raw.get("bond_delta", {})),
        karma_delta=_parse_dict_int(raw.get("karma_delta", {})),
        npc_state_delta=_parse_nested_dict(raw.get("npc_state_delta", {})),
        town_state_delta=_parse_dict_int(raw.get("town_state_delta", {})),
        follow_up_hint=raw.get("follow_up_hint", ""),
    )


def _parse_on_missed(raw: Optional[dict]) -> Optional[OnMissedDef]:
    if not raw:
        return None
    return OnMissedDef(
        action=raw.get("action", "skip"),
        description=raw.get("description", ""),
    )


def _parse_beat(raw: dict) -> StoryBeat:
    outcomes = [_parse_outcome(o) for o in raw.get("outcomes", [])]
    return StoryBeat(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        type=raw.get("type", "key"),
        event_id=raw.get("event_id", ""),
        earliest_day=int(raw.get("earliest_day", 1)),
        latest_day=int(raw.get("latest_day", 60)),
        preferred_slot=raw.get("preferred_slot", ""),
        preferred_location_hint=raw.get("preferred_location_hint", ""),
        participants=_parse_str_list(raw.get("participants", [])),
        required_participants=raw.get("required_participants", True),
        prerequisites=_parse_str_list(raw.get("prerequisites", [])),
        block_if=_parse_str_list(raw.get("block_if", [])),
        what_must_happen=raw.get("what_must_happen", ""),
        narrative_goal=raw.get("narrative_goal", ""),
        outcomes=outcomes,
        on_missed=_parse_on_missed(raw.get("on_missed")),
    )


def _parse_arc(raw: dict) -> StoryArc:
    beats = [_parse_beat(b) for b in raw.get("beats", [])]
    return StoryArc(
        id=raw.get("id", ""),
        name=raw.get("name", ""),
        description=raw.get("description", ""),
        weeks=raw.get("weeks", ""),
        priority=int(raw.get("priority", 1)),
        key_npcs=_parse_str_list(raw.get("key_npcs", [])),
        ending_condition=raw.get("ending_condition", ""),
        beats=beats,
    )


def _parse_tone_rule(raw: dict) -> ToneRule:
    return ToneRule(
        id=raw.get("id", ""),
        description=raw.get("description", ""),
        applies_to=raw.get("applies_to", "always"),
        min_occurrence=int(raw.get("min_occurrence", 0)),
        max_occurrence=int(raw.get("max_occurrence", 0)),
        weight_modifier=float(raw.get("weight_modifier", 1.0)),
        tracked_npc=raw.get("tracked_npc", ""),
        tracked_karma=raw.get("tracked_karma", ""),
        risk_cap=raw.get("risk_cap", ""),
    )


def _parse_global_constraints(raw: dict) -> GlobalConstraints:
    if not raw:
        return GlobalConstraints()
    return GlobalConstraints(
        max_events_per_slot=int(raw.get("max_events_per_slot", 3)),
        max_events_per_npc_per_day=int(raw.get("max_events_per_npc_per_day", 2)),
        anchor_priority_over_npc_intent=raw.get("anchor_priority_over_npc_intent", True),
    )


def _parse_outline(data: dict) -> StoryOutline:
    arcs = [_parse_arc(a) for a in data.get("arcs", [])]
    standalone = [_parse_beat(b) for b in data.get("standalone_beats", [])]
    tone_rules = [_parse_tone_rule(t) for t in data.get("tone_rules", [])]
    constraints = _parse_global_constraints(data.get("global_constraints", {}))

    return StoryOutline(
        version=data.get("version", "1.0"),
        game_days=int(data.get("game_days", 60)),
        weeks=int(data.get("weeks", 9)),
        arcs=arcs,
        standalone_beats=standalone,
        tone_rules=tone_rules,
        global_constraints=constraints,
    )


# ── Helpers ──

def _parse_dict_int(raw) -> Dict[str, int]:
    if not raw or not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items()}


def _parse_nested_dict(raw) -> Dict[str, Dict[str, int]]:
    if not raw or not isinstance(raw, dict):
        return {}
    result: Dict[str, Dict[str, int]] = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            result[str(k)] = {str(ik): int(iv) for ik, iv in v.items()}
    return result


def _parse_str_list(raw) -> List[str]:
    if not raw:
        return []
    return [str(item).strip() for item in raw if item]


# ── Public API ──

def load_story_outline(path: Optional[str] = None) -> Optional[StoryOutline]:
    """Load StoryOutline from JSON. Returns None if file missing or parse fails.

    Cached after first load — static data does not change mid-game.
    """
    global _CACHED_OUTLINE
    if _CACHED_OUTLINE is not None:
        return _CACHED_OUTLINE

    path = path or _STORY_JSON
    if not os.path.exists(path):
        print(f"[story_loader] StoryOutline not found: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[story_loader] Failed to read {path}: {e}")
        return None

    try:
        outline = _parse_outline(data)
    except Exception as e:
        print(f"[story_loader] Failed to parse outline: {e}")
        return None

    _CACHED_OUTLINE = outline
    beat_count = len(outline.all_beats())
    print(f"[story_loader] Loaded StoryOutline v{outline.version}: "
          f"{len(outline.arcs)} arcs, {beat_count} beats, {len(outline.tone_rules)} tone rules")
    return outline


def clear_cache() -> None:
    """Clear cached outline (for testing)."""
    global _CACHED_OUTLINE
    _CACHED_OUTLINE = None


# ── Event templates (即兴日常事件) ──

_TEMPLATES_JSON = os.path.join(_design_data_dir(), "event_templates.json")
_CACHED_TEMPLATES: Optional[dict] = None


def load_event_templates(path: Optional[str] = None) -> dict:
    """Load event templates for spontaneous daily events.

    Returns a dict with keys: "templates" (list), "composition_rules" (dict).
    Returns empty dict on failure.
    """
    global _CACHED_TEMPLATES
    if _CACHED_TEMPLATES is not None:
        return _CACHED_TEMPLATES

    path = path or _TEMPLATES_JSON
    if not os.path.exists(path):
        print(f"[story_loader] Event templates not found: {path}")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[story_loader] Failed to read templates: {e}")
        return {}

    _CACHED_TEMPLATES = data
    print(f"[story_loader] Loaded {len(data.get('templates', []))} event templates")
    return data


def clear_template_cache() -> None:
    global _CACHED_TEMPLATES
    _CACHED_TEMPLATES = None
