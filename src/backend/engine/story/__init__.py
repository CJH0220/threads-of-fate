"""Story system — 剧情大纲 + 运行时状态。

静态数据：
    StoryOutline / StoryArc / StoryBeat / OutcomeDef — 从 JSON 加载
运行时状态：
    StoryState / TriggeredBeat / Intervention — 随 GameSession 保存

Public API:
    load_story_outline() → Optional[StoryOutline]
"""

from src.backend.engine.story.story_types import (
    GlobalConstraints,
    Intervention,
    OnMissedDef,
    OutcomeDef,
    StoryArc,
    StoryBeat,
    StoryOutline,
    StoryState,
    ToneRule,
    TriggeredBeat,
)
from src.backend.engine.story.story_loader import load_story_outline

__all__ = [
    "GlobalConstraints",
    "Intervention",
    "OnMissedDef",
    "OutcomeDef",
    "StoryArc",
    "StoryBeat",
    "StoryOutline",
    "StoryState",
    "ToneRule",
    "TriggeredBeat",
    "load_story_outline",
]
