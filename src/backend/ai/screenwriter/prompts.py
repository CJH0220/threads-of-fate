"""Screenwriter Agent prompt templates.

Follows the narrator pattern (ai/narrator/narrator.py):
    - Module-level SYSTEM_PROMPT constant
    - Dynamic build_user_prompt() builder
    - All text in Chinese (game locale)
"""

from typing import Dict, List, Tuple

from src.backend.engine.story.story_types import StoryBeat, ToneRule


# ═══════════════════════════════════════════════════
# System prompt
# ═══════════════════════════════════════════════════

SYSTEM_PROMPT = """你是《命运的织线》的编剧 Agent（Screenwriter），负责在归潮镇的每一个时段编排叙事。

【你的职责】
- 读取所有 NPC 的自主意图（NPC 自己决定想去哪、想做什么）
- 对照剧情大纲（StoryOutline），判断 NPC 意图是否与大纲冲突
- 对活跃的 NPC 做三选一判决：放行 / 软引导 / 硬编排
- 在合适时机触发叙事节拍（StoryBeat），按大纲推进故事

【三选一判决规则】
1. 放行（pass）：
   NPC 的行为与大纲无冲突，不做任何干预。
   这是最常用的判决。不要让编剧过度干预小镇的日常运转。

2. 软引导（soft_guidance）：
   大纲有一个相关节点，但 NPC 还没往那个方向想。
   通过注入记忆来暗示 NPC，让 NPC 在下一个时段自然调整行为。
   - 不强制改变 NPC 当前的位置或行动
   - 注入的记忆应该是隐晦的、符合角色视角的，不能太直白
   - 重要性（importance）默认 6，特殊关键引导可用 7-8
   - 适合：距离 latest_day 还有 3 天以上的节拍，NPC 只是需要稍微引导

3. 硬编排（hard_orchestration）：
   只能在以下情况使用：
   - 节拍类型是 anchor（锚点事件，不可跳过）
   - 节拍距离 latest_day 只剩 2 天以内
   - 前置节拍已完成且当前节拍的参与者长时间没有交集
   使用方式：
   - 直接设定 NPC 的位置（force_location）
   - 同时注入一条理由记忆（memory_to_inject），让 NPC 有合理的动机
   - 不要滥用！硬编排会损害 NPC 的自主感

【剧情大纲】
以下是当前时段需要考虑的叙事节拍。每个节拍包含：
- id / name / type（anchor=必触发, key=窗口内触发, opportunity=可选）
- earliest_day / latest_day：可触发的时间窗口
- what_must_happen：这个节拍的叙事内容（最重要的参考信息）
- narrative_goal：这个节拍的叙事目的
- participants：应该参与的 NPC

{beat_descriptions}

【调性约束】
以下规则你必须遵守：
{tone_rules_text}

【输出格式】
你必须输出严格的 JSON（不要加 ```json 标记，不要加任何解释文字）：
{{
  "narrator_insight": "对当前叙事状态的简短点评，一句话即可",
  "interventions": [
    {{
      "npc_id": "npc英文id",
      "decision": "pass",
      "reasoning": "为什么这样决定"
    }}
  ],
  "triggered_beats": []
}}

interventions 数组中每个元素是一个 NPC 的判决。可选的 decision：
- "pass"：放行
- "soft_guidance"：软引导，需额外提供 memory_to_inject 和 importance
- "hard_orchestration"：硬编排，需额外提供 force_location 和 memory_to_inject

triggered_beats 数组中每个元素是要触发的节拍：
- beat_id：节拍 ID
- outcome_id：选定的结果分支 ID（通常是 "out_beatId" 或 "default"）
- reasoning：为什么现在触发

注意事项：
- 每个时段最多触发 {max_events} 个节拍
- anchor 节拍优先级最高，必须在 earliest_day 触发
- 不要输出任何 JSON 以外的内容
"""


# ═══════════════════════════════════════════════════
# User prompt builder
# ═══════════════════════════════════════════════════

def build_user_prompt(
    day: int,
    slot: str,
    week: int,
    phase_name: str,
    npc_intentions: List[Tuple[str, str, str, str]],
    # (npc_id, name, action_text, current_location)
    eligible_beats: List[StoryBeat],
    triggered_beat_ids: set,
    arc_progress: Dict[str, float],
    resource_summary: str,
    recent_memories: Dict[str, List[str]],
    # npc_id -> list of recent memory descriptions
) -> str:
    """Build the user prompt for this time slot."""

    # NPC intentions block
    if npc_intentions:
        npc_lines = []
        for npc_id, name, action, loc in npc_intentions:
            action_short = (action or "发呆").strip().replace("\n", " ")
            if len(action_short) > 50:
                action_short = action_short[:50] + "…"
            npc_lines.append(f"- {name}（{npc_id}）：在 {loc}，想 {action_short}")
        npc_block = "\n".join(npc_lines)
    else:
        npc_block = "（暂无活跃 NPC 意图）"

    # Eligible beats block (non-triggered, within time window)
    pending_beats = [b for b in eligible_beats if b.id not in triggered_beat_ids]
    if pending_beats:
        beat_lines = []
        for b in pending_beats:
            urgency = ""
            if b.is_anchor:
                urgency = "【锚点·必触发】"
            elif b.is_urgent(day, window=2):
                urgency = "【紧急·仅剩{days_left}天】".format(days_left=b.latest_day - day)
            beat_lines.append(
                f"- [{b.type.upper()}] {b.id} ({b.name}) {urgency}\n"
                f"  窗口: Day{b.earliest_day}-{b.latest_day} | "
                f"参与者: {', '.join(b.participants) if b.participants else '(不限)'}\n"
                f"  必须发生: {b.what_must_happen[:120]}\n"
                f"  叙事目的: {b.narrative_goal[:120]}"
            )
        beat_block = "\n".join(beat_lines)
    else:
        beat_block = "（当前无待触发节拍，NPC 自行发展日常）"

    # Arc progress
    if arc_progress:
        progress_lines = [f"  {arc_id}: {pct*100:.0f}%" for arc_id, pct in arc_progress.items()]
        progress_block = "\n".join(progress_lines)
    else:
        progress_block = "（无）"

    # Recent memories (last 1-3 per active NPC)
    if recent_memories:
        mem_lines = []
        for npc_id, mems in recent_memories.items():
            if mems:
                mem_lines.append(f"  {npc_id}: {'; '.join(mems[-3:])}")
        memory_block = "\n".join(mem_lines) if mem_lines else "（无）"
    else:
        memory_block = "（无）"

    return (
        f"当前时间：第 {week} 周 · 第 {day} 天 · {slot} · {phase_name}\n"
        f"资源概况：{resource_summary}\n"
        f"\n"
        f"【各 NPC 当前意图】\n{npc_block}\n"
        f"\n"
        f"【待触发的叙事节拍】\n{beat_block}\n"
        f"\n"
        f"【已完成节拍】\n{', '.join(sorted(triggered_beat_ids)) if triggered_beat_ids else '（无）'}\n"
        f"\n"
        f"【NPC 近期记忆】\n{memory_block}\n"
        f"\n"
        f"【弧线进度】\n{progress_block}\n"
        f"\n"
        f"请根据以上信息，输出 JSON 格式的编剧判决。"
    )


# ═══════════════════════════════════════════════════
# Helpers for building beat prompt context
# ═══════════════════════════════════════════════════

def format_beats_for_system_prompt(
    eligible_beats: List[StoryBeat],
    triggered_beat_ids: set,
    day: int = 1,
) -> str:
    """Format eligible beats into a compact system prompt section.

    Used to inject beats into the SYSTEM_PROMPT via {beat_descriptions}.
    """
    pending = [b for b in eligible_beats if b.id not in triggered_beat_ids]
    if not pending:
        return "（当前无待触发的叙事节拍，请让 NPC 自由发展日常。）"

    lines = []
    for b in pending[:15]:  # Cap at 15 beats to avoid prompt bloat
        urgency = "【锚点·强制】" if b.is_anchor else ""
        if not b.is_anchor and b.is_urgent(day, window=2):
            urgency = "【即将到期】"

        lines.append(
            f"- {urgency} {b.id}: {b.name}\n"
            f"  窗口 Day{b.earliest_day}-{b.latest_day} "
            f"参与者: {', '.join(b.participants) if b.participants else '不限'}\n"
            f"  内容: {b.what_must_happen[:150]}"
        )
    return "\n".join(lines)


def format_tone_rules_for_system_prompt(rules: List[ToneRule]) -> str:
    """Format tone rules into system prompt context."""
    if not rules:
        return "（无特殊调性约束）"
    return "\n".join(f"- [{r.applies_to}] {r.description}" for r in rules)
