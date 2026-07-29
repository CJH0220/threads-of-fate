"""对白管线编排 — fill_scene → merge → polish。

单个事件的完整对白生成流程。
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Dict, List, Optional

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


_LIGHT_SYSTEM_PROMPT = """你是一个对白编辑，为日常小事件写 6-12 行生动对白。
要求：
- 只输出 JSON,不加任何解释,不加 markdown
- 每行控制在 35 字以内,自然口语化,符合角色性格和身份
- 至少 2 个角色开口说话,每个角色至少 2 句台词
- 穿插 2-3 个动作/神态/环境描写（type: action）
- 对话要有起伏：问候/引出话题→展开讨论→情绪变化→结束或约定下次
- 可以加入角色的小心思（type: thought），让对话更有层次
- 根据角色的性格和关系来写：熟人说话和陌生人完全不同
- 不要引入新人物或改变事件描述

输出格式(严格 JSON):
{
  "location": "中文地点名",
  "lines": [
    {"actor": "角色id", "type": "action或dialogue或thought", "text": "文本"}
  ]
}

好的例子（注意对话的自然流动和情绪的微妙变化）：
{
  "location": "码头",
  "lines": [
    {"actor": "chen_haisheng", "type": "action", "text": "陈海生站在码头边，朝海里扔了颗石子，水花溅起老高。"},
    {"actor": "chen_haisheng", "type": "dialogue", "text": "老周，你说这潮水天天涨天天落，跟人心一样没个准数。"},
    {"actor": "zhou_xingzhi", "type": "action", "text": "周行知靠在缆桩上，闻言笑了笑。"},
    {"actor": "zhou_xingzhi", "type": "dialogue", "text": "你海生也有这种感慨？少见啊。是不是潮音那孩子又让你操心了？"},
    {"actor": "chen_haisheng", "type": "thought", "text": "这小子什么都知道……"},
    {"actor": "chen_haisheng", "type": "dialogue", "text": "不是她。是昨晚做了个梦，梦到以前的事了。算了，不提了。"},
    {"actor": "zhou_xingzhi", "type": "dialogue", "text": "梦啊……有时候梦比醒着还真。走吧，去喝一杯，你这满腹心事的样子我看着难受。"}
  ]
}"""


async def run_light_dialogue(
    event: "EventTemplate",
    session: "GameSession",
    day: int,
    slot: "Slot",
    llm: "BaseLLMClient",
) -> Optional[dict]:
    """轻量短对白管线(score 3-5 日常事件用)。

    单次 LLM 调用,不走 fill_scene/merge/polish 全流程,主打快。
    产出与 run_dialogue_pipeline 相同结构的 dialogue dict。
    """
    participants = event.participants or []
    if not participants:
        return None

    name_map: Dict[str, str] = {}
    role_lines = []
    for pid in participants:
        ag = session.agents.get(pid)
        if ag is None:
            continue
        name_map[pid] = ag.name
        role_lines.append(f"- {pid}({ag.name})")

    if not role_lines:
        return None

    desc = (event.description or event.name or "").strip()
    location = event.location or ""
    user_prompt = (
        f"【事件】{event.name}\n"
        f"【地点】{location}\n"
        f"【发生】{desc}\n"
        f"【参与者】\n" + "\n".join(role_lines) + "\n\n"
        f"请为这个日常事件写 2-4 行简短对白,输出 JSON。"
    )

    messages = [
        {"role": "system", "content": _LIGHT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        reply = await llm.chat(messages, max_tokens=2048, temperature=0.85)
    except Exception:
        return None

    if not reply:
        return None

    from src.backend.ai.dialogue_designer.designer import _parse_polish_output
    parsed = _parse_polish_output(reply.strip())
    if parsed and "location" not in parsed:
        parsed["location"] = location
    return parsed
