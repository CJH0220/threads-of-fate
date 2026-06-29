"""Week phase definitions — the 9 narrative phases defined in design doc §13.4.

Each phase contains:
    - week: 1-9
    - day_range: e.g. "1-7"
    - name: Chinese phase name
    - theme: one-line atmosphere description, usable for LLM prompt injection

Currently hardcoded. Future migration path: data/ CSV config.
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class WeekPhase:
    """A single week's narrative phase. Immutable."""
    week: int           # 1-9
    day_range: str      # "1-7", "8-14", ...
    name: str           # Chinese phase name
    theme: str          # atmosphere description, usable for LLM prompt injection


# ── Design doc §13.4: 9 week phases ──

PHASES: List[WeekPhase] = [
    WeekPhase(week=1, day_range="1-7",  name="旧神将熄", theme="建立土地公绩效压力，介绍小镇和主要人物"),
    WeekPhase(week=2, day_range="8-14", name="外来者入潮", theme="邪教核心人物入场，外来力量开始渗透"),
    WeekPhase(week=3, day_range="15-21", name="异常初显", theme="巫女线、港口线索和第一起案件出现"),
    WeekPhase(week=4, day_range="22-28", name="命运交错", theme="三条主线开始交织"),
    WeekPhase(week=5, day_range="29-35", name="潮声入梦", theme="第60天天灾被明确化，邪教秘密聚会成型"),
    WeekPhase(week=6, day_range="36-42", name="信仰裂缝", theme="寺庙、家庭、警局、邪教四线压力集中"),
    WeekPhase(week=7, day_range="43-49", name="庙会争夺", theme="庙会 vs 邪教集会进入公开争夺"),
    WeekPhase(week=8, day_range="50-56", name="终局锁定", theme="聚集地点、证据链、火灾风险、巫女状态定型"),
    WeekPhase(week=9, day_range="57-60", name="潮落见神", theme="最后选择与天灾结算"),
]


def get_phase(week: int) -> WeekPhase:
    """Return the WeekPhase for a given week number.

    Args:
        week: 1-9

    Returns:
        WeekPhase dataclass instance

    Raises:
        ValueError: week not in range 1-9
    """
    for phase in PHASES:
        if phase.week == week:
            return phase
    raise ValueError(f"Invalid week number: {week}, expected 1-9")


def get_phase_name(day: int) -> str:
    """Return the current week phase name for a given day.

    Args:
        day: 1-60

    Returns:
        Chinese phase name string
    """
    import math
    week = math.ceil(day / 7)
    return get_phase(week).name
