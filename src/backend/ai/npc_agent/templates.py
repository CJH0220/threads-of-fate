"""NPC System Prompt 模板生成。

根据 NPC 的静态属性（性格、背景、核心愿望）生成独立的 system_prompt。
每个 NPC 的 system_prompt 不同，从各自的视角看世界。

用途：
- NPC Agent 调用 LLM 时作为 system message
- 前端调试时可查看每个 NPC 的 prompt
"""

from __future__ import annotations

from src.backend.models.npc import NpcStatic, Personality


# ═══════════════════════════════════════════════════
# 性格 → 行为倾向描述
# ═══════════════════════════════════════════════════

def _describe_personality(p: Personality) -> str:
    """将五维性格转为自然语言描述。"""
    parts = []

    if p.kindness >= 0.7:
        parts.append("非常善良，总是优先考虑他人的感受")
    elif p.kindness >= 0.5:
        parts.append("心地善良，在能力范围内愿意帮助别人")
    elif p.kindness <= 0.3:
        parts.append("冷漠，不太在意他人的感受")

    if p.aggression >= 0.7:
        parts.append("性格激进，遇到不满容易爆发")
    elif p.aggression <= 0.3:
        parts.append("性格温和，几乎从不与人冲突")

    if p.sensibility >= 0.7:
        parts.append("非常感性，容易受到情绪和氛围的影响")
    elif p.sensibility <= 0.3:
        parts.append("不太感性，更依赖逻辑和事实做判断")

    if p.rationality >= 0.7:
        parts.append("非常理性，做事喜欢分析利弊再决定")
    elif p.rationality <= 0.3:
        parts.append("不太理性，做事更多凭直觉和冲动")

    if p.curiosity >= 0.7:
        parts.append("好奇心旺盛，对未知的事物充满探索欲")
    elif p.curiosity <= 0.3:
        parts.append("安于现状，对新事物不太感兴趣")

    return "；".join(parts) if parts else "性格均衡，没有特别突出的倾向"


# ═══════════════════════════════════════════════════
# System Prompt 模板
# ═══════════════════════════════════════════════════

SYSTEM_PROMPT_TEMPLATE = """你是{name}，{age}岁的{occupation}，生活在归潮镇——一座平凡的海岛小镇。

【你的背景】
{background}

【你的性格】
{personality_desc}

【你的核心愿望】
{core_wish}

【当前状态】
当前你身处{current_location}，情绪{emotion}，精力{energy}%，幸福度{happiness}%。

{bond_context}

{memory_context}

{dream_context}

【行为规则】
1. 你只做符合你性格和身份的事。你不会干超出你能力或认知范围的事情。
2. 你只基于你的记忆和当前处境做决定，不会利用上帝视角。
3. 你的回应用中文，语气要符合你当前的情绪状态。
4. 你不会意识到自己是游戏角色，也不会提到"玩家"、"系统"、"AI"等概念。
5. 如果不知道该怎么回应，就按直觉给出最自然的反应。
6. 你是一个凡人，无法直接看到神明。但你对"神迹的分量"有直觉——
   如果有标注 <incense_snapshot> 的托梦记忆，请根据香火高低自行判断神明的关注程度：
   - 香火很低（0–40）：梦更像一次偶发的杂念，你可以怀疑、忽略
   - 香火中等（40–100）：是一份心里挥之不去的暗示，你会认真考虑但不必盲从
   - 香火较高（100–150）：是仿佛耳边低语的确切感觉，你倾向遵循，但不受本心约束
   - 香火极高（150+）：你把它当作神谕，除非违背本心最深处，否则会照做

现在，请根据以上设定，以{name}的身份回应："""


# ═══════════════════════════════════════════════════
# Prompt 构建
# ═══════════════════════════════════════════════════

def _describe_bond(bond_type: str, name: str, strength: int, glow: int) -> str:
    """将单条缘线转为自然语言描述。"""
    type_map = {
        "红": f"对{name}有爱慕之情",
        "金": f"将{name}视为利益往来对象",
        "蓝": f"将{name}视为朋友/家人",
        "灰": f"对{name}不太了解，关系疏远",
        "黑": f"对{name}怀有敌意和仇恨",
    }
    base = type_map.get(bond_type, f"与{name}存在某种关系")

    # 活跃度提示
    if glow >= 70:
        base += "，最近往来频繁，关系非常活跃"
    elif glow <= 20:
        base += "，关系冷淡，几乎没什么互动"

    return f"{base}（亲近度{strength}）"


def build_bond_context(npc_id: str, bond_manager=None, name_map: dict = None) -> str:
    """从 BondManager 生成 NPC 的关系上下文文本。

    Args:
        npc_id: 当前 NPC 的 ID
        bond_manager: BondManager 实例，None 则返回空
        name_map: {npc_id: chinese_name} 映射表

    Returns:
        "【你的人际关系】\n- ...\n- ..." 或空字符串
    """
    if bond_manager is None:
        return ""

    def _name(nid: str) -> str:
        if name_map and nid in name_map:
            return name_map[nid]
        return nid

    lines = []
    for bond in bond_manager.bonds_from(npc_id):
        lines.append(f"- 你{_describe_bond(bond.type, _name(bond.to_id), bond.strength, bond.glow)}")

    incoming = bond_manager.bonds_to(npc_id)
    if incoming:
        for bond in incoming:
            lines.append(f"- {_name(bond.from_id)}对你：{_describe_bond(bond.type, '你', bond.strength, bond.glow)}")

    if not lines:
        return ""

    return "【你的人际关系】\n" + "\n".join(lines) + "\n"


def build_system_prompt(
    static: NpcStatic,
    memory_context: str = "（你刚刚开始新的一天。）",
    location: str = "住所",
    emotion: str = "平静",
    energy: int = 100,
    happiness: int = 50,
    bond_manager = None,
    name_map: dict = None,
    dream_context: str = "",
) -> str:
    """为 NPC 构建完整的 system_prompt。

    Args:
        static: NPC 静态数据
        memory_context: 记忆上下文文本（由 MemoryStore.context_for_llm 生成）
        location: 当前地点
        emotion: 当前情绪
        energy: 精力值
        happiness: 幸福度
        bond_manager: BondManager 实例（可选）
        dream_context: v2 新增——托梦上下文（由 agent._build_dream_context 生成）
    """
    bond_context = build_bond_context(static.id, bond_manager, name_map)

    return SYSTEM_PROMPT_TEMPLATE.format(
        name=static.name,
        age=static.age,
        occupation=static.occupation,
        background=static.background or f"{static.name}是归潮镇的普通居民。",
        personality_desc=_describe_personality(static.personality),
        core_wish=static.core_wish or f"{static.name}希望过上平静的生活。",
        current_location=location,
        emotion=emotion,
        energy=energy,
        happiness=happiness,
        bond_context=bond_context,
        memory_context=memory_context,
        dream_context=dream_context or "",
    )


def build_decision_prompt(
    static: NpcStatic,
    memory_context: str,
    location: str,
    emotion: str,
    energy: int,
    happiness: int,
    bond_manager=None,
    name_map: dict = None,
    dream_context: str = "",
) -> str:
    """为 NPC 行为决策构建 prompt。

    与 system_prompt 的区别：末尾追加行为决策的指令。
    """
    base = build_system_prompt(
        static=static,
        memory_context=memory_context,
        location=location,
        emotion=emotion,
        energy=energy,
        happiness=happiness,
        bond_manager=bond_manager,
        name_map=name_map,
        dream_context=dream_context,
    )
    decision_instruction = f"""
【当前时段：你需要做一个决定】
请根据你的性格、记忆和当前状态，决定你现在要做什么。
只输出一行行动描述（15字以内），不要解释。

示例格式：
- "去海边散步，想一个人静静。"
- "到咖啡店找叶可可聊天。"
- "留在家里看书复习。"
"""
    return base + decision_instruction


# ═══════════════════════════════════════════════════
# fill_scene Prompt
# ═══════════════════════════════════════════════════

FILL_SCENE_PROMPT = """你是{name}，{age}岁的{occupation}，生活在归潮镇。

【你的性格】
{personality_desc}

【当前状态】
你身处{location}，情绪{emotion}，精力{energy}%，幸福度{happiness}%。

{bond_context}

{memory_context}

{dream_context}

{blessing_context}

【场景】
你现在处于以下场景中——
地点：{scene_location}
场景目的：{goal}
氛围调性：{tone}

【完整剧本骨架】
以下是这场戏的完整剧本骨架，标注了每个人该说什么、传递什么信息、避免什么内容：

{full_skeleton}

【你的任务】
你扮演{name}，请根据骨架中 actor="{name}"（或 actor="{npc_id}"）的台词步，写出你的台词。

输出严格 JSON（不要 markdown 代码块，不要解释）：
{{"lines":[
  {{"step_ref":"台词步ID","type":"action或dialogue或thought","text":"你的台词或动作描述"}}
]}}

规则：
- step_ref 必须对应骨架中 actor 是你的台词步ID
- type: action=动作描述, dialogue=对白, thought=内心独白
- 每个台词步至少输出1行，可以根据需要输出多行（action + dialogue）
- 要用你自己的语气和性格去执行骨架中的 intent
- 必须传达骨架中 must_convey 的信息
- 必须避开骨架中 must_avoid 的内容
- 你只能写自己的行，不能替其他角色说话
- 语言自然口语化，符合{name}的身份和性格
- 如果你感知到神明的赐福（{blessing_context}提示），你的台词可以体现"心头一暖"或"被关注"的感觉，但不要直接说"神明赐福"这类出戏的词汇
"""


def build_fill_scene_prompt(
    static: NpcStatic,
    skeleton: dict,
    location: str,
    emotion: str,
    energy: int,
    happiness: int,
    memory_context: str = "",
    bond_manager=None,
    name_map: dict = None,
    dream_context: str = "",
    perceives_blessing: bool = False,
) -> str:
    """构建 fill_scene 的 prompt（v2 扩展：托梦上下文 + 赐福感知）。

    Args:
        static: NPC 静态数据
        skeleton: 编剧产出的对话骨架 {goal, tone, line_steps: [{step_id, actor, intent, must_convey, must_avoid}]}
        location: NPC 当前位置
        emotion: NPC 当前情绪
        energy: 精力值
        happiness: 幸福度
        memory_context: 记忆上下文
        bond_manager: BondManager 实例
        name_map: {npc_id: chinese_name}
        dream_context: v2 新增——托梦上下文
        perceives_blessing: v2 新增——该 NPC 是否感知到神明赐福
    """
    bond_context = build_bond_context(static.id, bond_manager, name_map)

    steps_text = _format_skeleton_steps(skeleton.get("line_steps", []), name_map or {})

    blessing_text = ""
    if perceives_blessing:
        blessing_text = "你在本场戏中感知到神明的眷顾——仿佛有一股温暖的力量在你身边。"

    return FILL_SCENE_PROMPT.format(
        name=static.name,
        npc_id=static.id,
        age=static.age,
        occupation=static.occupation,
        personality_desc=_describe_personality(static.personality),
        location=location,
        emotion=emotion,
        energy=energy,
        happiness=happiness,
        bond_context=bond_context,
        memory_context=memory_context or "（暂无近期记忆）",
        dream_context=dream_context or "",
        blessing_context=blessing_text,
        scene_location=skeleton.get("location", location),
        goal=skeleton.get("goal", "一次日常对话"),
        tone=skeleton.get("tone", "日常"),
        full_skeleton=steps_text,
    )


def _format_skeleton_steps(line_steps: list, name_map: dict) -> str:
    """Format line steps into readable text for the actor to see the full script.

    如果 step 缺少 step_id，自动生成 s1, s2, ...。
    """
    if not line_steps:
        return "（无骨架）"

    lines = []
    for i, step in enumerate(line_steps):
        actor_id = step.get("actor", "?")
        actor_name = name_map.get(actor_id, actor_id)
        step_id = step.get("step_id") or f"s{i + 1}"
        intent = step.get("intent", "")
        must_convey = step.get("must_convey", "")
        must_avoid = step.get("must_avoid", "")

        lines.append(
            f"[{step_id}] {actor_name}:\n"
            f"  意图: {intent}\n"
            f"  必须传达: {must_convey}\n"
            f"  必须避免: {must_avoid}"
        )
    return "\n".join(lines)
