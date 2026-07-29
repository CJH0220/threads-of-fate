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
- 为每个产出的事件评估戏剧冲突性（0-10 分），驱动后续管线资源分配
- 生成本时段的"时段预告"摘要（土地公视角，60-120 字），供玩家决策

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

【时间背景】
当前时段是 {slot_label}。请根据时段特征选择事件类型：
- 早晨（morning）：适合晨练、买菜、上学路上、开始一天的工作。气氛清新，节奏舒缓。
- 下午（noon）：适合工作间隙、逛街、偶遇、喝茶聊天。气氛活跃，节奏中等。
- 夜晚（night）：适合独处反思、秘密会面、夜间工作、酒吧闲聊。气氛沉静或暧昧，节奏较慢。
你的事件选择应反映当前时段的自然节律——不要让 NPC 在深夜买菜或在清晨去酒吧。

【有效地点列表】
以下是归潮镇的全部地点，事件只能在这些地点中发生。每个地点的英文 ID 和中文名一一对应：
{location_list}
事件中的 location 字段必须使用上述英文 ID，detail 和 dialogue_skeleton 中则使用中文名。

【事件模板库】
每个时段你都必须生成 {min_spontaneous}-{max_spontaneous} 个即兴日常事件，让小镇有呼吸感。这是你最重要的工作——没有人会替你填充日常。即使没有任何节拍触发，NPC 也在生活，小镇在运转，总有值得记录的小事。请尽量选择 2-3 人互动的模板，避免每时段都是单人独处。

你可以从以下模板中选择来生成即兴日常事件。不要凭空创造新的事件类型。每个模板定义了参与者数量、适用调性、delta 数值上限：
{template_descriptions}

【对话骨架要求（重要！）】
对于戏剧分 >= 3 的即兴事件，你必须提供 dialogue_skeleton，让后续对白管线能生成角色之间的实际对话。没有 dialogue_skeleton 的事件会是无声的——这会让游戏体验大打折扣。
dialogue_skeleton 格式：{{"goal": "场景目的", "tone": "氛围", "line_steps": [{{"actor": "npc_id", "intent": "意图", "must_convey": "必须传达", "must_avoid": "必须避免"}}]}}
- goal: 这个场景的叙事目的（一句话）
- tone: 氛围调性（warm/tense/mysterious/intimate/neutral）
- line_steps: 每个参与者至少 1 步，每步包含 intent（意图）、must_convey（必须传达的信息）、must_avoid（必须避免的内容）
- 一个好的 dialogue_skeleton 应该让每个角色有 2-3 步台词，形成对话的起承转合

【调性约束】
{composition_rules_text}

以下规则你必须遵守：
{tone_rules_text}

【戏剧冲突性评分规则（dramatic_score）】
你必须对每个产出的事件（包括节拍事件和即兴事件）给出一个整数分 0-10：
- 0-2（环境氛围）：某 NPC 独自吃饭、发呆、日常劳作。不进入对白管线。
- 3-5（日常互动）：两人闲聊、路人打招呼、日常偶遇。轻量模板处理，不走完整对白管线。
- 6-8（显著戏剧）：争吵、告白、重要决定、秘密被发现。走完整对白管线。
- 9-10（转折/命运节点）：关系逆转、重大秘密揭示、命运抉择时刻。完整管线 + 强制暴露为赐福节点。

评分参考维度（不是硬规则，是你作为编剧的主观判断）：
1. 是否涉及关系逆转 / 秘密揭示 / 抉择时刻
2. 是否触碰节拍库中的 anchor 或 key beat
3. 参与者情绪极值（情绪不是 neutral、变化幅度大的加 1-2 分）
4. 玩家近期干预是否指向本事件的参与者（+1 分，鼓励回应玩家意图）
5. 是否是全镇范围的大事件（+1 分）

评分不可修改：你输出后即固化为事件属性。

【时段预告摘要生成规则】
你必须输出 slot_summary 字段，生成一段 60-120 字的"时段预告"文本。语气从土地公视角出发，例：

"今晨的港口比往日更沉。陈海生的船迟迟未出，你隐约听见他与顾沉舟在船舱里争执什么。若你有心相助，此刻或可在他们的相遇处轻拨命运一二。"

摘要要求：
- 只描述"将要发生什么氛围"，不剧透任何结果
- 只涉及 dramatic_score ≥ 6 的事件参与者
- 明确点出至少一个可赐福节点的所在（若本时段有）
- 若本时段无 score ≥ 6 的事件，摘要可简短（30-50 字）描述小镇日常氛围

【输出格式】
你必须输出严格的 JSON（不要加 ```json 标记，不要加任何解释文字）：
{{
  "narrator_insight": "对当前叙事状态的简短点评，一句话即可",
  "slot_summary": "土地公视角的时段预告，60-120字，只描述氛围不剧透结果",
  "interventions": [
    {{
      "npc_id": "npc英文id",
      "decision": "pass",
      "reasoning": "为什么这样决定"
    }}
  ],
  "triggered_beats": [
    {{
      "beat_id": "beat英文id",
      "outcome_id": "所选结果分支id",
      "dramatic_score": 7,
      "reasoning": "为什么现在触发，为什么给这个分"
    }}
  ],
  "spontaneous_events": [
    {{
      "template_id": "idle_chat",
      "participants": ["lin_chaoyin", "chen_yuanzhou"],
      "location": "cafe",
      "detail": "两人讨论起最近岛上的流言，叶可可在一旁添油加醋。",
      "dramatic_score": 4,
      "dialogue_skeleton": {{
        "goal": "轻松的日常闲聊中暗含对未来的担忧",
        "tone": "轻松中带一丝不安",
        "line_steps": [
          {{"actor": "chen_yuanzhou", "intent": "试探潮音最近是否压力大", "must_convey": "关心但不直白", "must_avoid": "提及考试压力"}},
          {{"actor": "lin_chaoyin", "intent": "回答但不愿透露太多", "must_convey": "最近去了寺庙", "must_avoid": "提到巫女身份"}}
        ]
      }},
      "outcome": {{}},
      "reasoning": "为什么选这个模板，为什么给这个分"
    }}
  ]
}}

interventions 数组中每个元素是一个 NPC 的判决。可选的 decision：
- "pass"：放行
- "soft_guidance"：软引导，需额外提供 memory_to_inject 和 importance
- "hard_orchestration"：硬编排，需额外提供 force_location 和 memory_to_inject

triggered_beats 数组中每个元素是要触发的节拍：
- beat_id：节拍 ID
- outcome_id：选定的结果分支 ID
- dramatic_score：该节拍事件的戏剧冲突分（必填，0-10）
- reasoning：为什么现在触发，为什么给这个分

spontaneous_events 数组中每个元素是一个即兴日常事件（每个时段至少生成 {min_spontaneous} 个，最多 {max_spontaneous} 个，请尽量生成 {max_spontaneous} 个！）：
- template_id：从模板库中选择（必填）
- participants：参与 NPC 的英文 ID 列表（必填，人数在模板 min/max 范围内，优先选同地点且有缘线的 NPC，优先选 2-3 人互动的模板）
- location：发生地点（必填，从 NPC 当前所在的地点中选择）
- detail：具体发生了什么（必填，2-3句话，包含动作/对话/情绪细节，必须生动具体，符合模板 tone）
- dramatic_score：戏剧冲突分（必填，0-10，鼓励给出 3-7 分的日常互动，避免全给低分）
- dialogue_skeleton：对话骨架（dramatic_score >= 3 时必须提供！这是生成对白的必要条件，没有它事件就是哑的）
  - goal：场景叙事目的
  - tone：氛围调性
  - line_steps：台词步列表，每个参与者至少 2 步！形成对话的起承转合
    - actor：说话者 NPC 的英文 ID
    - intent：该 NPC 说这句话的意图
    - must_convey：这句话必须传达的信息
    - must_avoid：这句话必须避免的内容
- outcome：微量 delta（可选，必须在模板 delta_budget 范围内）
- reasoning：为什么选这个模板，为什么给这个分（必填）

注意事项：
- 每个时段总共最多 {max_events} 个事件（triggered_beats + spontaneous_events 合计）
- spontaneous_events 至少 {min_spontaneous} 个、最多 {max_spontaneous} 个——不要留空
- 优先选择同地点的 NPC 组合，避免把不同地方的 NPC 强行拉到一起
- anchor 节拍优先级最高（即使评分低也必须触发，评分仅影响管线资源分配）
- 同一模板不连续两个时段使用
- 夜晚只允许 solitude_reflection / discovery / minor_conflict
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

    # NPC intentions block (cap at 8 to keep prompt within context limits)
    if npc_intentions:
        npc_lines = []
        for npc_id, name, action, loc in npc_intentions[:8]:
            action_short = (action or "发呆").strip().replace("\n", " ")
            if len(action_short) > 40:
                action_short = action_short[:40] + "…"
            npc_lines.append(f"- {name}：在 {loc}，{action_short}")
        if len(npc_intentions) > 8:
            npc_lines.append(f"- （还有 {len(npc_intentions) - 8} 位 NPC，略）")
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

    # NPC personality/emotion summaries for dialogue skeleton writing
    npc_summaries = _build_npc_summaries(npc_intentions, recent_memories)
    if npc_summaries:
        npc_summary_block = '\n'.join(npc_summaries)
    else:
        npc_summary_block = '（无）'

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
        f"【NPC 人设摘要】\n{npc_summary_block}\n"
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
    for b in pending[:5]:  # Cap at 5 to keep system prompt compact
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


def format_templates_for_system_prompt(templates: dict) -> str:
    """Format event templates into system prompt context."""
    tmpl_list = templates.get("templates", []) if templates else []
    if not tmpl_list:
        return "（无可用事件模板）"

    lines = []
    for t in tmpl_list:
        db = t.get("delta_budget", {})
        bond_b = db.get("bond", {})
        hap_b = db.get("happiness", {})
        lines.append(
            f"- [{t['id']}] {t['name']} "
            f"({t.get('tone', '?')}) "
            f"{t['min_participants']}-{t['max_participants']}人 "
            f"bond[{bond_b.get('min',0)},{bond_b.get('max',0)}] "
            f"happiness[{hap_b.get('min',0)},{hap_b.get('max',0)}]"
        )
    return "\n".join(lines)


# Time slot Chinese labels
_SLOT_LABELS = {"morning": "早晨", "noon": "下午", "night": "夜晚"}


def format_locations_for_system_prompt() -> str:
    """Format all valid locations into system prompt context."""
    locations = [
        ("temple", "土地庙"), ("plaza", "广场"), ("beach", "沙滩"), ("school", "学校"),
        ("clinic", "诊所"), ("shopping_street", "商业街"), ("bookstore", "书店"),
        ("cafe", "咖啡馆"), ("police_station", "警局"), ("mountain_forest", "山林"),
        ("port", "港口"), ("residence", "住所"), ("coffee_shop", "咖啡店"),
        ("wine_bar", "酒吧"), ("seafood_shop", "海鲜店"), ("dock", "码头"),
        ("church", "教堂"), ("hospital", "医院"), ("park", "公园"),
        ("market", "市场"), ("restaurant", "餐馆"), ("library", "图书馆"),
        ("gym", "健身房"), ("office", "办公楼"), ("factory", "工厂"),
        ("station", "车站"), ("seaside", "海边"), ("bathhouse", "澡堂"),
        ("teahouse", "茶馆"), ("kitchen", "厨房"), ("backyard", "后院"),
        ("rooftop", "天台"),
    ]
    return "\n".join(f"- {eid}: {cname}" for eid, cname in locations)


def format_composition_rules_for_system_prompt(templates: dict) -> str:
    """Format composition rules into system prompt."""
    rules = templates.get("composition_rules", {}) if templates else {}
    if not rules:
        return ""
    lines = []
    if rules.get("max_spontaneous_per_slot"):
        lines.append(f"- 每时段最多 {rules['max_spontaneous_per_slot']} 个即兴事件")
    if rules.get("no_same_template_consecutive"):
        lines.append("- 禁止同一模板连续两个时段使用")
    night = rules.get("night_allowed_only", [])
    if night:
        lines.append(f"- 夜晚只允许: {', '.join(night)}")
    return "\n".join(lines)


def _build_npc_summaries(
    npc_intentions: list,
    recent_memories: dict,
) -> list:
    """Build compact NPC personality/emotion summaries for dialogue skeleton writing."""
    # This is a placeholder that returns basic summaries from available data.
    # The actual personality/emotion data comes from the agent objects, not from
    # npc_intentions tuples alone. The caller should expand this if richer data is needed.
    lines = []
    for item in npc_intentions:
        if len(item) >= 4:
            npc_id, name, action, loc = item[0], item[1], item[2], item[3]
            mems = recent_memories.get(npc_id, [])
            mem_tail = ('; '.join(mems[-2:]) if mems else '暂无近期记忆')
            lines.append(
                f"- {name}({npc_id})：在{loc}，{action[:30]}。" +
                f"近期：{mem_tail}"
            )
    return lines
