"""Screenwriter Agent — 每时段的叙事编排。

Substitutes the old CSV match_events() with LLM-driven orchestration:
    1. Read StoryOutline + NPC intentions
    2. Filter eligible beats (programmatic)
    3. Call LLM with prompts → JSON decision
    4. Apply interventions (pass / soft_guidance / hard_orchestration)
    5. Build (EventTemplate, Outcome) pairs for execute_events()
    6. Update session.story (StoryState)

Fallback:
    Returns (False, []) if LLM unavailable / outline missing / JSON unparseable.
    Caller (ws_game.py) falls back to old CSV match_events().
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from src.backend.engine.event.event_types import EventTemplate, Outcome
from src.backend.engine.story.story_types import (
    OutcomeDef,
    StoryBeat,
    StoryOutline,
    StoryState,
    TriggeredBeat,
)
from src.backend.ai.screenwriter.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
    format_beats_for_system_prompt,
    format_tone_rules_for_system_prompt,
)
from src.backend.models.npc import Slot

if TYPE_CHECKING:
    from src.backend.ai.llm_client.interface import BaseLLMClient
    from src.backend.engine.game_session import GameSession


# ═══════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════

async def screenwriter_think(
    session: "GameSession",
    story_outline: Optional[StoryOutline],
    day: int,
    slot: Slot,
    week: int,
    phase_name: str,
    npc_intentions: List[Tuple[str, str, str, str]],
    llm: Optional["BaseLLMClient"] = None,
) -> Tuple[bool, List[Tuple[EventTemplate, Outcome]]]:
    """Run the Screenwriter Agent for one time slot.

    Args:
        session: current GameSession
        story_outline: loaded StoryOutline (None → fallback)
        day: current day (1-60)
        slot: current time slot
        week: current week
        phase_name: week phase name for atmosphere
        npc_intentions: [(npc_id, name, action_text, location), ...]
        llm: LLM client (None → fallback)

    Returns:
        (ok, events): ok=False means caller should fall back to CSV matching.
        events list may be empty even when ok=True (no beats triggered this slot).
    """
    # Guard: no outline or no LLM → fallback
    if story_outline is None or llm is None:
        return False, []

    # 1. Pre-filter eligible beats
    eligible_beats = _get_eligible_beats(story_outline, session.story, day)

    # 2. Collect recent memories per NPC for context
    recent_memories = _collect_recent_memories(session, npc_intentions)

    # 3. Build prompts
    beat_descriptions = format_beats_for_system_prompt(
        eligible_beats, set(session.story.triggered_beats.keys()), day=day
    )
    tone_text = format_tone_rules_for_system_prompt(story_outline.tone_rules)
    resource_summary = _summarize_resource(session)
    max_events = story_outline.global_constraints.max_events_per_slot

    system_prompt = SYSTEM_PROMPT.format(
        beat_descriptions=beat_descriptions,
        tone_rules_text=tone_text,
        max_events=max_events,
    )

    user_prompt = build_user_prompt(
        day=day,
        slot=slot.value,
        week=week,
        phase_name=phase_name,
        npc_intentions=npc_intentions,
        eligible_beats=eligible_beats,
        triggered_beat_ids=set(session.story.triggered_beats.keys()),
        arc_progress=session.story.arc_progress,
        resource_summary=resource_summary,
        recent_memories=recent_memories,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # 4. Call LLM
    try:
        reply = await llm.chat(messages, max_tokens=1024, temperature=0.7)
    except Exception as e:
        print(f"[screenwriter] LLM call failed: {type(e).__name__}: {e}")
        return False, []

    if not reply:
        return False, []

    # 5. Parse JSON
    decisions = _parse_llm_output(reply)
    if decisions is None:
        print("[screenwriter] Failed to parse LLM output, falling back to CSV")
        return False, []

    # 6. Apply NPC interventions
    interventions = decisions.get("interventions", [])
    _apply_interventions(session, interventions, day, slot)

    # 7. Build events from triggered beats
    triggered = decisions.get("triggered_beats", [])
    beat_events = _build_events_from_beats(triggered, story_outline, session)

    # 8. Update StoryState
    _update_story_state(session.story, triggered, story_outline, day, slot)
    _recalculate_arc_progress(session.story, story_outline)

    if beat_events:
        print(f"[screenwriter] day={day} slot={slot.value}: "
              f"{len(interventions)} interventions, {len(beat_events)} events triggered")

    return True, beat_events


# ═══════════════════════════════════════════════════
# Eligible beats filter
# ═══════════════════════════════════════════════════

def _get_eligible_beats(
    outline: StoryOutline,
    state: StoryState,
    day: int,
) -> List[StoryBeat]:
    """Pre-filter beats: remove already-triggered and overdue ones.

    Overdue beats get their on_missed escalation recorded.
    """
    eligible: List[StoryBeat] = []
    triggered_ids = set(state.triggered_beats.keys())

    for beat in outline.all_beats():
        if beat.id in triggered_ids:
            continue

        if day < beat.earliest_day:
            continue  # Too early

        if beat.is_overdue(day):
            # Beat expired — record on_missed
            _apply_missed_beat(beat, state)
            continue

        eligible.append(beat)

    return eligible


def _apply_missed_beat(beat: StoryBeat, state: StoryState) -> None:
    """Record a missed beat in state."""
    if beat.id in state.triggered_beats:
        return

    action = beat.on_missed.action if beat.on_missed else "skip"
    desc = beat.on_missed.description if beat.on_missed else ""

    state.triggered_beats[beat.id] = TriggeredBeat(
        beat_id=beat.id,
        triggered_day=0,
        triggered_slot="missed",
        selected_outcome_id=f"__{action}__",
        participants_present=[],
    )
    print(f"[screenwriter] Beat '{beat.id}' missed (latest_day={beat.latest_day}): "
          f"action={action} {desc[:60]}")


# ═══════════════════════════════════════════════════
# JSON parsing
# ═══════════════════════════════════════════════════

def _parse_llm_output(text: str) -> Optional[Dict[str, Any]]:
    """Parse LLM JSON output with 3-tier fallback.

    1. Direct json.loads
    2. Regex extract first {...} block
    3. Regex extract ```json ... ``` code block
    """
    text = text.strip()

    # Tier 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Tier 2: extract {...} block (greedy, finds outermost)
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Tier 3: ```json ... ``` code block
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None


# ═══════════════════════════════════════════════════
# Interventions
# ═══════════════════════════════════════════════════

def _safe_str(val, default: str = "") -> str:
    """Get a string from a JSON value, handling None/null gracefully."""
    return str(val).strip() if val else default


def _apply_interventions(
    session: "GameSession",
    interventions: List[Dict[str, Any]],
    day: int,
    slot: Slot,
) -> None:
    """Apply the screenwriter's NPC interventions."""
    for inv in interventions:
        npc_id = _safe_str(inv.get("npc_id"))
        decision = _safe_str(inv.get("decision"), "pass")
        if not npc_id:
            continue
        agent = session.agents.get(npc_id)
        if agent is None:
            continue

        if decision == "pass":
            continue

        memory_text = _safe_str(inv.get("memory_to_inject"))
        importance = int(inv.get("importance") or 5)

        if decision == "soft_guidance":
            if memory_text:
                agent.remember(
                    day=day,
                    slot=slot,
                    description=memory_text,
                    importance=min(max(importance, 1), 10),
                )
                print(f"[screenwriter] soft_guidance → {npc_id}: {memory_text[:60]}...")

        elif decision == "hard_orchestration":
            force_loc = _safe_str(inv.get("force_location"))
            if force_loc:
                try:
                    from src.backend.models.npc import Location
                    target = Location(force_loc)
                    agent.dynamic.set_location(npc_id, target, reason="screenwriter_hard_orch")
                    print(f"[screenwriter] hard_orch → {npc_id}: moved to {force_loc}")
                except ValueError:
                    print(f"[screenwriter] WARNING: unknown location '{force_loc}' for {npc_id}")
            if memory_text:
                agent.remember(
                    day=day,
                    slot=slot,
                    description=memory_text,
                    importance=min(max(importance, 1), 10),
                )


# ═══════════════════════════════════════════════════
# Event building
# ═══════════════════════════════════════════════════

def _build_events_from_beats(
    triggers: List[Dict[str, str]],
    outline: StoryOutline,
    session: "GameSession",
) -> List[Tuple[EventTemplate, Outcome]]:
    """Convert triggered beat decisions into executable event tuples."""
    result: List[Tuple[EventTemplate, Outcome]] = []

    for trigger in triggers:
        beat_id = _safe_str(trigger.get("beat_id"))
        outcome_id = _safe_str(trigger.get("outcome_id"))

        beat = _find_beat(outline, beat_id)
        if beat is None:
            print(f"[screenwriter] WARNING: unknown beat_id '{beat_id}'")
            continue

        # If beat references a CSV event, we don't convert here —
        # the caller (ws_game.py) will match it via CSV match_events.
        # This function only handles beats WITH inline outcomes.
        if beat.event_id:
            # Beat references CSV → build a minimal EventTemplate for matching
            template = _build_template_from_beat(beat)
            # Pick the first inline outcome (if any) or create a stub
            outcome_def = _find_outcome(beat, outcome_id)
            if outcome_def is not None:
                outcome = _outcome_def_to_outcome(outcome_def, beat.id)
                result.append((template, outcome))
            else:
                # No inline outcomes → the caller adds this to CSV supplement
                print(f"[screenwriter] Beat '{beat_id}' refs CSV event '{beat.event_id}' "
                      f"— deferring to CSV match_events")
        else:
            # Beat has inline outcomes → build directly
            template = _build_template_from_beat(beat)
            outcome_def = _find_outcome(beat, outcome_id)
            if outcome_def is None and beat.outcomes:
                outcome_def = beat.outcomes[0]  # Fallback to first outcome
            if outcome_def is not None:
                outcome = _outcome_def_to_outcome(outcome_def, beat.id)
                result.append((template, outcome))

    return result


def _build_template_from_beat(beat: StoryBeat) -> EventTemplate:
    """Build an EventTemplate from a StoryBeat."""
    return EventTemplate(
        id=beat.id,
        name=beat.name,
        event_type="Anchor" if beat.is_anchor else "Key",
        week_range=f"W{beat.earliest_week}",
        day_range=f"Day{beat.earliest_day}",
        time_slot=beat.preferred_slot or "Any",
        location=beat.preferred_location_hint or "",
        participants=list(beat.participants),
        weight=1000 if beat.is_anchor else 500,
        risk_level="Medium",
        ai_text_policy="DialogueAllowed",
        description=beat.what_must_happen[:200],
    )


def _outcome_def_to_outcome(odef: OutcomeDef, event_id: str) -> Outcome:
    """Convert OutcomeDef (JSON-style) to Outcome (CSV-style)."""
    return Outcome(
        id=odef.id or f"out_{event_id}",
        event_id=event_id,
        name=odef.description[:20] if odef.description else event_id,
        trigger_condition=odef.condition or "default",
        resource_delta=dict(odef.resource_delta),
        bond_delta=dict(odef.bond_delta),
        karma_delta=dict(odef.karma_delta),
        npc_state_delta={k: dict(v) for k, v in odef.npc_state_delta.items()},
        town_state_delta=dict(odef.town_state_delta),
        description=odef.description,
    )


def _find_beat(outline: StoryOutline, beat_id: str) -> Optional[StoryBeat]:
    """Find a beat by id across all arcs and standalone beats."""
    for beat in outline.all_beats():
        if beat.id == beat_id:
            return beat
    return None


def _find_outcome(beat: StoryBeat, outcome_id: str) -> Optional[OutcomeDef]:
    """Find an outcome by id within a beat."""
    for o in beat.outcomes:
        if o.id == outcome_id:
            return o
    # Fallback: first outcome
    if beat.outcomes:
        return beat.outcomes[0]
    return None


# ═══════════════════════════════════════════════════
# State update
# ═══════════════════════════════════════════════════

def _update_story_state(
    state: StoryState,
    triggered: List[Dict[str, str]],
    outline: StoryOutline,
    day: int,
    slot: Slot,
) -> None:
    """Mark triggered beats in StoryState."""
    for trigger in triggered:
        beat_id = _safe_str(trigger.get("beat_id"))
        outcome_id = _safe_str(trigger.get("outcome_id"))
        beat = _find_beat(outline, beat_id)
        if beat is None:
            continue
        # Find participants who are actually alive/available
        present = [p for p in beat.participants]
        state.mark_beat_triggered(
            beat_id=beat_id,
            day=day,
            slot=slot.value,
            outcome_id=outcome_id,
            participants=present,
        )


def _recalculate_arc_progress(state: StoryState, outline: StoryOutline) -> None:
    """Update arc completion percentages."""
    for arc in outline.arcs:
        if not arc.beats:
            continue
        triggered = sum(
            1 for b in arc.beats if b.id in state.triggered_beats
        )
        state.arc_progress[arc.id] = triggered / len(arc.beats)


# ═══════════════════════════════════════════════════
# Context helpers
# ═══════════════════════════════════════════════════

def _summarize_resource(session: "GameSession") -> str:
    """Summarize resource state for prompt context."""
    r = session.resource
    return (
        f"香火 {r.incense}，神力 {r.divine_power}/{r.divine_power_max}，"
        f"阴德 {getattr(r, 'yin_de', 0)}，阳德 {getattr(r, 'yang_de', 0)}"
    )


def _collect_recent_memories(
    session: "GameSession",
    npc_intentions: List[Tuple[str, str, str, str]],
) -> Dict[str, List[str]]:
    """Collect last 5 recent event descriptions for each active NPC."""
    result: Dict[str, List[str]] = {}
    for npc_id, _, _, _ in npc_intentions:
        agent = session.agents.get(npc_id)
        if agent is None:
            continue
        entries = agent.memory.recent_events(n=5)
        result[npc_id] = [e.description[:80] for e in entries if e.description]
    return result
