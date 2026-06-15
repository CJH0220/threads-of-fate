"""NPC 动态状态 —— 每时段可变层。

提供：
- 默认动态状态创建
- 状态变更记录（delta tracking）
- 游戏内时段推进时的批量更新

动态层在每时段结算后更新，存档时序列化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from src.backend.models.npc import Emotion, Location, NpcDynamic, Slot


# ═══════════════════════════════════════════════════
# 状态变更记录
# ═══════════════════════════════════════════════════

@dataclass
class DynamicDelta:
    """记录一次状态变更（用于增量同步给前端）。"""
    npc_id: str
    field: str                # 变更字段名
    old_value: object         # 旧值
    new_value: object         # 新值
    reason: str = ""          # 变更原因（事件 ID 或系统描述）

    def as_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "field": self.field,
            "old_value": str(self.old_value),
            "new_value": str(self.new_value),
            "reason": self.reason,
        }


# ═══════════════════════════════════════════════════
# 动态状态管理
# ═══════════════════════════════════════════════════

class DynamicState:
    """管理单个 NPC 的动态状态，追踪变更。"""

    def __init__(self, state: Optional[NpcDynamic] = None):
        self._state = state or self._default_state()
        self._deltas: List[DynamicDelta] = []

    @staticmethod
    def _default_state() -> NpcDynamic:
        return NpcDynamic(
            location=Location.RESIDENCE,
            happiness=50,
            energy=100,
            emotion=Emotion.NEUTRAL,
            current_goal="适应归潮镇的生活",
        )

    # ── 查询 ──────────────────────────────────────

    @property
    def current(self) -> NpcDynamic:
        return self._state

    @property
    def deltas(self) -> List[DynamicDelta]:
        """返回并清空变更记录。"""
        result = self._deltas[:]
        self._deltas.clear()
        return result

    def snapshot(self) -> dict:
        """返回当前状态摘要（给 LLM 当上下文）。"""
        s = self._state
        return {
            "location": s.location.value,
            "happiness": s.happiness,
            "energy": s.energy,
            "emotion": s.emotion.value,
            "current_goal": s.current_goal,
            "karma_main_progress": f"{s.karma_main_progress:.0f}%",
        }

    # ── 修改 ──────────────────────────────────────

    def set_location(self, npc_id: str, location: Location, reason: str = "") -> None:
        old = self._state.location
        self._state.location = location
        if old != location:
            self._deltas.append(DynamicDelta(npc_id, "location", old, location, reason))

    def set_happiness(self, npc_id: str, delta: int, reason: str = "") -> None:
        old = self._state.happiness
        self._state.happiness = max(0, min(100, old + delta))
        if old != self._state.happiness:
            self._deltas.append(DynamicDelta(npc_id, "happiness", old, self._state.happiness, reason))

    def set_energy(self, npc_id: str, delta: int, reason: str = "") -> None:
        old = self._state.energy
        self._state.energy = max(0, min(100, old + delta))
        if old != self._state.energy:
            self._deltas.append(DynamicDelta(npc_id, "energy", old, self._state.energy, reason))

    def set_emotion(self, npc_id: str, emotion: Emotion, reason: str = "") -> None:
        old = self._state.emotion
        self._state.emotion = emotion
        if old != emotion:
            self._deltas.append(DynamicDelta(npc_id, "emotion", old, emotion, reason))

    def set_goal(self, npc_id: str, goal: str, reason: str = "") -> None:
        old = self._state.current_goal
        self._state.current_goal = goal
        if old != goal:
            self._deltas.append(DynamicDelta(npc_id, "current_goal", old, goal, reason))

    def set_karma_main(self, npc_id: str, progress: float, reason: str = "") -> None:
        old = self._state.karma_main_progress
        self._state.karma_main_progress = max(0.0, min(100.0, progress))
        if abs(old - self._state.karma_main_progress) > 0.01:
            self._deltas.append(DynamicDelta(npc_id, "karma_main_progress", old, self._state.karma_main_progress, reason))

    # ── 序列化 ────────────────────────────────────

    def to_dict(self) -> dict:
        return self._state.model_dump()

    @classmethod
    def from_dict(cls, data: dict) -> "DynamicState":
        return cls(NpcDynamic(**data))


# ═══════════════════════════════════════════════════
# 一键创建
# ═══════════════════════════════════════════════════

def create_initial_dynamic(location: Location = Location.RESIDENCE) -> DynamicState:
    """为新游戏创建初始动态状态。"""
    state = NpcDynamic(
        location=location,
        happiness=50,
        energy=100,
        emotion=Emotion.NEUTRAL,
        current_goal="",
    )
    return DynamicState(state)
