"""Event executor — apply outcome deltas to game state.

For each triggered event:
    1. Find the matching outcome
    2. Apply ResourceDelta → ResourceState
    3. Apply NpcStateDelta → AgentManager (NpcDynamic)
    4. Record memory via agent.remember()
    5. Queue BondDelta, KarmaDelta, TownStateDelta for future modules
"""

from typing import Optional

from src.backend.engine.event.event_types import EventTemplate, Outcome, SettlementResult
from src.backend.engine.resource.resource_state import ResourceState
from src.backend.models.npc import Slot


def _apply_resource_delta(
    outcome: Outcome,
    resource: ResourceState,
) -> dict:
    """Apply resource delta to ResourceState. Returns applied changes."""
    changes: dict = {}
    for key, val in outcome.resource_delta.items():
        if key == "incense":
            resource.add_incense(val)
            changes[key] = val
        elif key == "divine_power":
            if val < 0:
                resource.spend_divine_power(abs(val))
                changes[key] = val
            else:
                # positive divine_power: just add (unusual but possible)
                resource.divine_power = min(
                    resource.divine_power + val, resource.divine_power_max
                )
                changes[key] = val
        elif key == "yin_de":
            resource.add_yin_de(val)
            changes[key] = val
        elif key == "yang_de":
            resource.add_yang_de(val)
            changes[key] = val
        else:
            # Unknown resource key → log and skip
            changes[key] = val
    return changes


def _apply_npc_state_delta(
    outcome: Outcome,
    agent_manager,
    day: int,
    slot: Slot,
) -> dict:
    """Apply NPC state delta to agents. Returns {npc_id: {attr: change}}."""
    changes: dict = {}
    for npc_id, attrs in outcome.npc_state_delta.items():
        agent = agent_manager.get(npc_id)
        if agent is None:
            continue
        changes[npc_id] = {}
        for attr, val in attrs.items():
            # Map attribute names to DynamicState methods
            if attr == "stress":
                # stress is represented as happiness decrease
                current = agent.dynamic.current.happiness
                agent.dynamic.set_happiness(npc_id, current + val)
                changes[npc_id][attr] = val
            elif attr == "happiness":
                current = agent.dynamic.current.happiness
                agent.dynamic.set_happiness(npc_id, current + val)
                changes[npc_id][attr] = val
            elif attr == "energy":
                agent.dynamic.current.energy = max(
                    0, min(100, agent.dynamic.current.energy + val)
                )
                changes[npc_id][attr] = val
            else:
                # Flag attributes (settled, nervous, etc.) or unknown
                changes[npc_id][attr] = val

    return changes


def execute_event(
    event: EventTemplate,
    outcome: Outcome,
    resource: ResourceState,
    agent_manager,
    day: int,
    slot: Slot,
) -> Optional[SettlementResult]:
    """Execute a single event outcome.

    Applies deltas to ResourceState and AgentManager.
    Bond/Karma/TownState deltas are queued in the result for future modules.

    Args:
        event: the matched event template
        outcome: the selected outcome to apply
        resource: ResourceState to modify
        agent_manager: AgentManager for NPC state and memories
        day: current game day
        slot: current time slot

    Returns:
        SettlementResult with all applied and queued changes
    """
    if outcome is None:
        return None

    # Apply resource changes
    resource_changes = _apply_resource_delta(outcome, resource)

    # Apply NPC state changes
    npc_changes = _apply_npc_state_delta(outcome, agent_manager, day, slot)

    # Record memories for participants
    memories_recorded = 0
    for npc_id in event.participants:
        agent = agent_manager.get(npc_id)
        if agent is None:
            continue
        # Build memory description from event + outcome
        description = f"{event.name}：{outcome.description or outcome.name}"
        import_rating = 9 if event.is_anchor else (7 if event.event_type == "Key" else 5)
        agent.remember(
            day=day,
            slot=slot,
            description=description,
            importance=min(import_rating, 10),
        )
        memories_recorded += 1

    result = SettlementResult(
        event_id=event.id,
        event_name=event.name,
        outcome_id=outcome.id,
        outcome_name=outcome.name,
        resource_changes=resource_changes,
        npc_changes=npc_changes,
        memories_recorded=memories_recorded,
        bond_changes=outcome.bond_delta,
        karma_changes=outcome.karma_delta,
        town_changes=outcome.town_state_delta,
    )

    return result


def execute_events(
    matched: list,
    resource: ResourceState,
    agent_manager,
    day: int,
    slot: Slot,
) -> list:
    """Execute a batch of matched events.

    Returns:
        list of SettlementResult for successfully executed events
    """
    results = []
    for event, outcome in matched:
        result = execute_event(event, outcome, resource, agent_manager, day, slot)
        if result:
            results.append(result)
    return results
