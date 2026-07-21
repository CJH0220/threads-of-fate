"""对白设计师 — 润色对白，输出定稿。"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.backend.ai.llm_client.interface import BaseLLMClient


# ═══════════════════════════════════════════════════
# Prompt
# ═══════════════════════════════════════════════════

POLISH_SYSTEM_PROMPT = """你是一个对白编辑，你的任务是润色一段角色扮演场景的对白。

【你可以做的事】
- 修正口吻不一致（同一角色前后风格突变）
- 调整节奏（拆分过长独白，穿插动作描述）
- 删除相邻行的重复语义（去复读）
- 让 tone 更贴合场景氛围
- 精简冗余表达，但保留所有关键信息

【你不能做的事】
- 新增或删除角色（speaker/actor）
- 改变场景地点、时间、道具
- 改变对话的核心信息和情节走向
- 引入场景背景中没有的新信息
- 把对话改成完全不同的话题

【输出格式】
输出严格 JSON（不要 markdown 代码块，不要解释）：
{{
  "location": "地点",
  "lines": [
    {{"actor": "角色英文id", "type": "action或dialogue或thought", "text": "动作描述或对白"}}
  ]
}}

type 说明：
- action：动作/神态描述（前端渲染为叙述文本）
- dialogue：对白（前端渲染为对话气泡）
- thought：内心独白（前端渲染为斜体/括号，可选）
"""


# ═══════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════

async def polish_dialogue(
    skeleton: dict,
    filled_lines: List[dict],
    llm: "BaseLLMClient",
    npc_name_map: Optional[Dict[str, str]] = None,
) -> Optional[dict]:
    """润色拼接后的对白，输出最终定稿。

    Args:
        skeleton: 编剧产出的对话骨架 {goal, tone, location, line_steps}
        filled_lines: 所有 NPC 填写的台词 [{actor, lines: [{step_ref, type, text}]}]
        llm: LLM 客户端
        npc_name_map: {npc_id: chinese_name} 映射表（用于 prompt 中的角色说明）

    Returns:
        润色后的定稿 {location, lines: [{actor, type, text}]}，失败返回 None
    """
    if not filled_lines:
        return None

    name_map = npc_name_map or {}

    # 拼接所有 NPC 的台词为纯文本
    merged_text = _merge_filled_lines(filled_lines, name_map)

    # 提取骨架摘要
    skeleton_summary = _format_skeleton_summary(skeleton, name_map)

    user_prompt = f"""【场景背景】
地点：{skeleton.get('location', '某处')}
场景目的：{skeleton.get('goal', '日常对话')}
氛围调性：{skeleton.get('tone', '日常')}

【角色设定】
{skeleton_summary}

【拼接后的对白（需要润色）】
{merged_text}

请润色以上对白，输出 JSON 格式的定稿。"""

    messages = [
        {"role": "system", "content": POLISH_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        reply = await llm.chat(messages, max_tokens=2048, temperature=0.6)
    except Exception:
        return None

    if not reply:
        return None

    return _parse_polish_output(reply.strip())


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def _merge_filled_lines(filled_lines: List[dict], name_map: dict) -> str:
    """Merge all NPC filled lines into a single text for the polisher."""
    parts = []
    for entry in filled_lines:
        actor_id = entry.get("actor", "?")
        actor_name = name_map.get(actor_id, actor_id)
        lines = entry.get("lines", [])
        for line in lines:
            ltype = line.get("type", "dialogue")
            text = line.get("text", "")
            if not text:
                continue
            if ltype == "action":
                parts.append(f"[{actor_name}]（动作）{text}")
            elif ltype == "thought":
                parts.append(f"[{actor_name}]（内心）{text}")
            else:
                parts.append(f"[{actor_name}]：{text}")
    return "\n".join(parts)


def _format_skeleton_summary(skeleton: dict, name_map: dict) -> str:
    """Format skeleton line steps as actor role summaries."""
    line_steps = skeleton.get("line_steps", [])
    if not line_steps:
        return "（无）"

    # Group by actor
    actor_steps: dict = {}
    for step in line_steps:
        actor_id = step.get("actor", "?")
        if actor_id not in actor_steps:
            actor_steps[actor_id] = []
        actor_steps[actor_id].append(step)

    parts = []
    for actor_id, steps in actor_steps.items():
        actor_name = name_map.get(actor_id, actor_id)
        intents = "；".join(s.get("intent", "") for s in steps if s.get("intent"))
        parts.append(f"- {actor_name}：{intents}")
    return "\n".join(parts)


def _parse_polish_output(text: str) -> Optional[dict]:
    """Parse the polisher's JSON output. Same 3-tier fallback as screenwriter."""
    # Tier 1: direct
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Tier 2: outermost {...}
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Tier 3: ```json ... ```
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None
