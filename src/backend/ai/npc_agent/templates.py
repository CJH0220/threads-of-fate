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

{memory_context}

【行为规则】
1. 你只做符合你性格和身份的事。你不会干超出你能力或认知范围的事情。
2. 你只基于你的记忆和当前处境做决定，不会利用上帝视角。
3. 你的回应用中文，语气要符合你当前的情绪状态。
4. 你不会意识到自己是游戏角色，也不会提到"玩家"、"系统"、"AI"等概念。
5. 如果不知道该怎么回应，就按直觉给出最自然的反应。

现在，请根据以上设定，以{name}的身份回应："""


# ═══════════════════════════════════════════════════
# Prompt 构建
# ═══════════════════════════════════════════════════

def build_system_prompt(
    static: NpcStatic,
    memory_context: str = "（你刚刚开始新的一天。）",
    location: str = "住所",
    emotion: str = "平静",
    energy: int = 100,
    happiness: int = 50,
) -> str:
    """为 NPC 构建完整的 system_prompt。

    Args:
        static: NPC 静态数据
        memory_context: 记忆上下文文本（由 MemoryStore.context_for_llm 生成）
        location: 当前地点
        emotion: 当前情绪
        energy: 精力值
        happiness: 幸福度
    """
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
        memory_context=memory_context,
    )


def build_decision_prompt(
    static: NpcStatic,
    memory_context: str,
    location: str,
    emotion: str,
    energy: int,
    happiness: int,
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
