"""故事编排 Agent（土地公视角旁白）。

在夜晚时段调用一次，读取当日全局状态 + S/A 级 NPC 的行动，
让 LLM 生成一段简短旁白（≤80 字），作为叙事节拍插入日志。

设计原则：
- 非阻塞：LLM 失败或超时直接返回 None，不影响主循环
- 轻量：只喂"必要的最少上下文"，避免抢占 NPC 决策 token 预算
- 语气固定：土地公第一人称，古朴克制，避免露骨描写
"""

from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from src.backend.ai.llm_client.interface import BaseLLMClient
    from src.backend.engine.game_session import GameSession


_SYSTEM_PROMPT = (
    "你是归潮镇的土地公，掌管这方土地已数百年。"
    "你正在夜色中俯瞰镇上的一切，将今日所见所感化为一段简短旁白。"
    "\n\n"
    "写作要求：\n"
    "- 用第一人称（我）叙述，古朴而克制\n"
    "- 长度不超过 80 字，一到两句话即可\n"
    "- 只点染氛围与心境，不复述已发生的事件\n"
    "- 涉及情感或私隐处使用暗示，不做露骨描写\n"
    "- 不要出现现代词汇（手机、网络等）\n"
    "- 直接输出旁白正文，不要加引号或前缀"
)


def _summarize_actions(recent_actions: List[Tuple[str, str, str]]) -> str:
    """把 (npc_id, name, action, ...) 列表压成一段简述。"""
    if not recent_actions:
        return "镇上今日无事，众人各安其位。"
    lines: List[str] = []
    for item in recent_actions[:6]:
        try:
            _npc_id, name, action, *_ = item  # tuple may have 3 or 4 elements
        except (TypeError, ValueError):
            continue
        action_str = (action or "").strip().replace("\n", " ")
        if len(action_str) > 40:
            action_str = action_str[:40] + "…"
        lines.append(f"- {name}：{action_str}")
    return "\n".join(lines) if lines else "镇上今日无事。"


def _summarize_resource(session: "GameSession") -> str:
    r = session.resource
    return (
        f"香火 {r.incense}，神力 {r.divine_power}/{r.divine_power_max}，"
        f"阴德 {getattr(r, 'yin_de', 0)}，阳德 {getattr(r, 'yang_de', 0)}"
    )


async def generate_narrator_beat(
    session: "GameSession",
    day: int,
    slot: str,
    recent_actions: List[Tuple[str, str, str]],
    llm: Optional["BaseLLMClient"] = None,
) -> Optional[str]:
    """生成一段土地公视角的夜间旁白。失败或不可用时返回 None。"""
    if llm is None:
        return None

    action_block = _summarize_actions(recent_actions or [])
    resource_block = _summarize_resource(session)

    user_prompt = (
        f"今日：第 {day} 天 · {slot}\n"
        f"香火与德业：{resource_block}\n"
        f"今日 S/A 级镇民行迹：\n{action_block}\n\n"
        f"请以土地公的视角，说一段今夜的心境旁白。"
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        reply = await llm.chat(messages, max_tokens=160, temperature=0.8)
    except Exception as e:
        print(f"[narrator] LLM 调用失败：{type(e).__name__}: {e}")
        return None

    if not reply:
        return None
    text = reply.strip().strip("「」\"'“”")
    return text or None
