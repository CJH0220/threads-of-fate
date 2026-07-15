"""Story system data types.

StoryOutline: 静态剧情大纲，从 JSON 加载，不入存档。
StoryState:  运行时状态，随 GameSession 序列化/反序列化。

与旧 CSV 事件系统的关系：
    StoryBeat 可通过 event_id 引用 CSV 中的 EventTemplate，
    编剧 Agent 从 CSV 加载具体 participants/outcomes/delta 数值。
    只有大纲中新增的事件才在 beat 内 inline 定义 outcomes。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════
# 静态大纲（从 JSON 加载，不入存档）
# ═══════════════════════════════════════════════════

@dataclass
class OutcomeDef:
    """结果分支 —— JSON 版 Outcome。

    字段与 event_types.Outcome 对应但命名略有不同，
    通过 outcome_def_to_outcome() 转换。
    """
    id: str
    condition: str = "default"       # "default" | "divine_intervention" | "warning" | "insight"
    description: str = ""
    resource_delta: Dict[str, int] = field(default_factory=dict)
    bond_delta: Dict[str, int] = field(default_factory=dict)
    karma_delta: Dict[str, int] = field(default_factory=dict)
    npc_state_delta: Dict[str, Dict[str, int]] = field(default_factory=dict)
    town_state_delta: Dict[str, int] = field(default_factory=dict)
    follow_up_hint: str = ""


@dataclass
class OnMissedDef:
    """节拍超时未触发的兜底处理。"""
    action: str = "skip"             # "escalate" | "skip" | "transform"
    description: str = ""


@dataclass
class StoryBeat:
    """叙事节拍 —— 大纲的核心原子单元。

    表示"一段必须在某个时间窗口内发生的叙事事件"。
    可通过 event_id 引用已有 CSV 事件，也可 inline 定义新 outcomes。
    """
    id: str
    name: str
    type: str = "key"                # "anchor" | "key" | "opportunity"

    # 引用已有 CSV 事件（可选）
    event_id: str = ""               # 指向 事件配置表.csv 中的 EventId

    # 时间窗口
    earliest_day: int = 1
    latest_day: int = 60
    preferred_slot: str = ""         # "morning" | "noon" | "night" | "" (any)
    preferred_location_hint: str = ""

    # 参与者
    participants: List[str] = field(default_factory=list)
    required_participants: bool = True

    # 条件（自然语言，供 LLM 推理）
    prerequisites: List[str] = field(default_factory=list)
    block_if: List[str] = field(default_factory=list)

    # 叙事意图
    what_must_happen: str = ""
    narrative_goal: str = ""

    # 结果（仅当 event_id 为空时生效 —— 即大纲新增事件）
    outcomes: List[OutcomeDef] = field(default_factory=list)

    # 超时处理
    on_missed: Optional[OnMissedDef] = None

    @property
    def earliest_week(self) -> int:
        return (self.earliest_day - 1) // 7 + 1

    @property
    def latest_week(self) -> int:
        return (self.latest_day - 1) // 7 + 1

    @property
    def is_anchor(self) -> bool:
        return self.type == "anchor"

    def is_overdue(self, day: int) -> bool:
        """当前天数已超过 latest_day。"""
        return day > self.latest_day

    def is_urgent(self, day: int, window: int = 2) -> bool:
        """距离 latest_day 还剩 window 天以内。"""
        return 0 <= (self.latest_day - day) <= window

    def is_eligible(self, day: int) -> bool:
        """是否在可触发窗口内（已到 earliest 且未过期）。"""
        return self.earliest_day <= day <= self.latest_day


@dataclass
class StoryArc:
    """故事弧线 —— 跨越数周的叙事线。"""
    id: str
    name: str
    description: str = ""
    weeks: str = ""                  # "W1" | "W2-W7" 等
    priority: int = 1               # 0=anchor, 1=main, 2=side
    key_npcs: List[str] = field(default_factory=list)
    ending_condition: str = ""
    beats: List[StoryBeat] = field(default_factory=list)


@dataclass
class ToneRule:
    """调性约束 —— 全局叙事规则。"""
    id: str
    description: str                 # 自然语言，注入编剧 Agent 的 system prompt
    applies_to: str = "always"       # "slot" | "day" | "weekly" | "always"
    min_occurrence: int = 0
    max_occurrence: int = 0
    weight_modifier: float = 1.0
    tracked_npc: str = ""
    tracked_karma: str = ""
    risk_cap: str = ""


@dataclass
class GlobalConstraints:
    """硬限制 —— 防止一个时段塞太多事件。"""
    max_events_per_slot: int = 3
    max_events_per_npc_per_day: int = 2
    anchor_priority_over_npc_intent: bool = True


@dataclass
class StoryOutline:
    """静态剧情大纲 —— 从 design/data/story_outline.json 加载。

    不入存档。策划可独立迭代此文件，不影响玩家存档。
    """
    version: str = "1.0"
    game_days: int = 60
    weeks: int = 9
    arcs: List[StoryArc] = field(default_factory=list)
    standalone_beats: List[StoryBeat] = field(default_factory=list)
    tone_rules: List[ToneRule] = field(default_factory=list)
    global_constraints: GlobalConstraints = field(default_factory=GlobalConstraints)

    def all_beats(self) -> List[StoryBeat]:
        """获取全部节拍，按弧线优先级排序。"""
        beats: List[StoryBeat] = list(self.standalone_beats)
        for arc in sorted(self.arcs, key=lambda a: a.priority):
            beats.extend(arc.beats)
        return beats


# ═══════════════════════════════════════════════════
# 运行时状态（随 GameSession 序列化入存档）
# ═══════════════════════════════════════════════════

@dataclass
class TriggeredBeat:
    """一条已触发的节拍记录。"""
    beat_id: str
    triggered_day: int
    triggered_slot: str
    selected_outcome_id: str
    participants_present: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "triggered_day": self.triggered_day,
            "triggered_slot": self.triggered_slot,
            "selected_outcome_id": self.selected_outcome_id,
            "participants_present": list(self.participants_present),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggeredBeat":
        return cls(**data)


@dataclass
class Intervention:
    """一次编剧干预记录（供调试/回滚，暂不实现回滚）。"""
    npc_id: str
    type: str                        # "soft_guidance" | "hard_orchestration"
    description: str = ""
    importance: int = 5
    force_location: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "npc_id": self.npc_id,
            "type": self.type,
            "description": self.description,
            "importance": self.importance,
            "force_location": self.force_location,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Intervention":
        return cls(**data)


@dataclass
class StoryState:
    """编剧 Agent 运行时状态。

    随 GameSession 序列化/反序列化。
    不包含 StoryOutline —— 大纲是静态数据，从 JSON 重新加载。
    """
    triggered_beats: Dict[str, TriggeredBeat] = field(default_factory=dict)
    active_interventions: List[Intervention] = field(default_factory=list)
    arc_progress: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triggered_beats": {
                k: v.to_dict() for k, v in self.triggered_beats.items()
            },
            "active_interventions": [i.to_dict() for i in self.active_interventions],
            "arc_progress": dict(self.arc_progress),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StoryState":
        if not data:
            return cls()
        return cls(
            triggered_beats={
                k: TriggeredBeat.from_dict(v)
                for k, v in data.get("triggered_beats", {}).items()
            },
            active_interventions=[
                Intervention.from_dict(i)
                for i in data.get("active_interventions", [])
            ],
            arc_progress=dict(data.get("arc_progress", {})),
        )

    def is_beat_triggered(self, beat_id: str) -> bool:
        return beat_id in self.triggered_beats

    def mark_beat_triggered(self, beat_id: str, day: int, slot: str,
                            outcome_id: str, participants: List[str]) -> None:
        self.triggered_beats[beat_id] = TriggeredBeat(
            beat_id=beat_id,
            triggered_day=day,
            triggered_slot=slot,
            selected_outcome_id=outcome_id,
            participants_present=list(participants),
        )
