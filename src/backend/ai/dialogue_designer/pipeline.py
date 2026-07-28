"""对白管线编排 — fill_scene → merge → polish。

单个事件的完整对白生成流程。
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, List, Optional

from src.backend.ai.dialogue_designer.designer import polish_dialogue
from src.backend.models.npc import Slot

if TYPE_CHECKING:
    from src.backend.engine.event.event_types import EventTemplate
    from src.backend.engine.game_session import GameSession
    from src.backend.ai.llm_client.interface import BaseLLMClient


async def run_dialogue_pipeline(
    event: "EventTemplate",
    session: "GameSession",
    day: int,
    slot: "Slot",
    llm: "BaseLLMClient",
    player_context: dict = None,
) -> Optional[dict]:
    """为单个事件运行完整对白管线（v2：支持 player_context）。

    流程：
    1. 对每个 S/A 级 participant 并发调用 fill_scene（注入 player_context）
    2. 拼接所有 SceneFilled
    3. 对白设计师润色
    4. 返回定稿 dialogue dict（可直接发给前端）

    Args:
        event: 带有 dialogue_skeleton 的事件模板
        session: 游戏会话
        day: 当前天数
        slot: 当前时段
        llm: LLM 客户端
        player_context: v2 新增——玩家在时段预告窗的介入结果

    Returns:
        定稿 dialogue {location, lines: [{actor, type, text}]}，失败返回 None
    """
    skeleton = event.dialogue_skeleton
    if not skeleton:
        return None

    participants = event.participants or []
    if not participants:
        return None

    # 1. 并发 fill_scene（仅 S/A 级 NPC，注入 player_context）
    async def _fill_one(npc_id: str):
        agent = session.agents.get(npc_id)
        if agent is None:
            return None
        if agent.static.tier.value not in ("S", "A"):
            return None
        return await agent.fill_scene(skeleton, day, slot, player_context=player_context)

    tasks = [_fill_one(pid) for pid in participants]
    filled = await asyncio.gather(*tasks, return_exceptions=True)

    # 过滤失败和 None
    filled_lines = []
    for item in filled:
        if item is None or isinstance(item, Exception):
            continue
        filled_lines.append(item)

    if not filled_lines:
        return None

    # 2. 拼接 + 3. 润色
    name_map = {}
    for pid in participants:
        ag = session.agents.get(pid)
        if ag:
            name_map[pid] = ag.name

    polished = await polish_dialogue(
        skeleton=skeleton,
        filled_lines=filled_lines,
        llm=llm,
        npc_name_map=name_map,
    )

    if polished:
        # 确保 location 字段存在
        if "location" not in polished:
            polished["location"] = skeleton.get("location", event.location or "")

    return polished


def dialogue_to_description(dialogue: Optional[dict]) -> str:
    """将定稿 dialogue 转为纯文本描述（用于 event.description 兼容）。"""
    if not dialogue:
        return ""
    lines = dialogue.get("lines", [])
    parts = []
    for line in lines:
        actor = line.get("actor", "?")
        ltype = line.get("type", "dialogue")
        text = line.get("text", "")
        if not text:
            continue
        if ltype == "action":
            parts.append(text)
        elif ltype == "thought":
            parts.append(f"（{actor}心想：{text}）")
        else:
            parts.append(f"{actor}：{text}")
    return "\n".join(parts)
