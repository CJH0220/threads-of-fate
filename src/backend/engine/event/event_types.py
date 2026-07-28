"""Event system data types.

EventTemplate: a predefined event with trigger conditions and possible outcomes.
Outcome: a single result branch with delta instructions.
SettlementResult: what happened after executing an event outcome.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Outcome:
    """A single result branch for an event.

    All delta fields are parsed from CSV semicolon-delimited strings into dicts.
    """
    id: str                          # e.g. "out_w1_chaoyin_study_good"
    event_id: str                    # parent event id
    name: str                        # Chinese outcome name
    trigger_condition: str           # e.g. "default", "fire_risk>=90"
    resource_delta: Dict[str, int] = field(default_factory=dict)   # {"incense": -1}
    bond_delta: Dict[str, int] = field(default_factory=dict)       # {"bond_a_b": +3}
    karma_delta: Dict[str, int] = field(default_factory=dict)      # {"chaoyin_witch_line": 10}
    npc_state_delta: Dict[str, Dict[str, int]] = field(default_factory=dict)
        # {"lin_chaoyin": {"stress": 3, "happiness": -2}}
    town_state_delta: Dict[str, int] = field(default_factory=dict) # {"cult_influence": 8}
    follow_up_event_ids: List[str] = field(default_factory=list)
    history_key: str = ""            # localization key for history log
    description: str = ""


@dataclass
class EventTemplate:
    """A predefined event with trigger conditions."""
    id: str                          # e.g. "w1_chaoyin_study"
    name: str                        # Chinese event name
    event_type: str                  # "Anchor" | "Key" | "Daily"
    week_range: str                  # "W1" | "W2-W4" | "Final"
    day_range: str                   # "Day1" | "Day3-5" | "" (any)
    time_slot: str                   # "Morning" | "Night" | "Daytime" | "Any"
    location: str                    # "" (any) or specific location
    participants: List[str]          # NPC IDs involved
    weight: int                      # 1-1000, higher = more likely to trigger
    risk_level: str = "Low"          # "Low" | "Medium" | "High" | "Fatal"
    ai_text_policy: str = ""          # "None" | "DialogueAllowed"
    outcomes: List[Outcome] = field(default_factory=list)
    description: str = ""
    dialogue_skeleton: Optional[Dict] = None  # 编剧产出的对话骨架 {goal, tone, line_steps}
    dramatic_score: int = 5          # 0-10 戏剧冲突性评分（v2 新增）

    @property
    def is_anchor(self) -> bool:
        return self.event_type == "Anchor" or self.weight >= 1000


@dataclass
class SettlementResult:
    """Result of executing a single event outcome."""
    event_id: str
    event_name: str
    outcome_id: str
    outcome_name: str

    # Applied deltas
    resource_changes: Dict[str, int] = field(default_factory=dict)
    npc_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    memories_recorded: int = 0

    # Queued for future modules
    bond_changes: Dict[str, int] = field(default_factory=dict)
    karma_changes: Dict[str, int] = field(default_factory=dict)
    town_changes: Dict[str, int] = field(default_factory=dict)

    # v2: player intervention flags for frontend rendering
    player_impact_flags: Dict[str, bool] = field(default_factory=dict)
