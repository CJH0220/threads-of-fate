"""NPC 静态属性 —— 不可变层。

提供：
- 从配置字典批量构建 NpcStatic
- 预设 Demo NPC（林潮音、陈远舟）
- 属性查询接口

静态属性在游戏过程中不会变化，只在创建 Agent 时设置一次。
"""

from __future__ import annotations

from src.backend.models.npc import (
    AgentTier,
    FixedAttributes,
    NpcStatic,
    Personality,
)


# ═══════════════════════════════════════════════════
# 构建函数
# ═══════════════════════════════════════════════════

def build_static(data: dict) -> NpcStatic:
    """从配置字典构建 NpcStatic。

    示例:
        build_static({
            "id": "lin_chaoyin",
            "name": "林潮音",
            "age": 17,
            "occupation": "高中生",
            "tier": "S",
            "background": "灵力少女...",
            "attributes": {"mind": 8, "faith": 3, "physique": 4, "charm": 7},
            "personality": {"kindness": 0.8, "sensibility": 0.9, "curiosity": 0.7},
        })
    """
    return NpcStatic(
        id=data["id"],
        name=data["name"],
        age=data["age"],
        occupation=data["occupation"],
        tier=AgentTier(data.get("tier", "A")),
        background=data.get("background", ""),
        attributes=FixedAttributes(**(data.get("attributes", {}))),
        personality=Personality(**(data.get("personality", {}))),
        core_wish=data.get("core_wish", ""),
    )


# ═══════════════════════════════════════════════════
# Demo NPC 预设（硬编码，后期迁移到 CSV）
# ═══════════════════════════════════════════════════

def demo_lin_chaoyin() -> NpcStatic:
    """林潮音 / 灵力少女 / 巫女候选 / S 级 Agent。"""
    return NpcStatic(
        id="lin_chaoyin",
        name="林潮音",
        age=17,
        occupation="高中生",
        tier=AgentTier.S,
        background=(
            "由单亲母亲林月琴独自抚养长大。从小体质特殊，偶尔能听见钟塔方向的"
            "声音，也会在梦中看见潮水吞没小镇。镇上的老人觉得她'有灵'。"
        ),
        attributes=FixedAttributes(mind=8, faith=3, physique=4, charm=7),
        personality=Personality(
            kindness=0.8,
            aggression=0.2,
            sensibility=0.9,
            rationality=0.6,
            curiosity=0.7,
        ),
        core_wish="决定自己的人生，而不是被母亲、寺庙、土地公、邪教或命运安排",
    )


def demo_chen_yuanzhou() -> NpcStatic:
    """陈远舟 / 离岛梦想者 / 普通男高中生 / S 级 Agent。"""
    return NpcStatic(
        id="chen_yuanzhou",
        name="陈远舟",
        age=18,
        occupation="高中生",
        tier=AgentTier.S,
        background=(
            "陈海生和苏婉的儿子。聪明、努力、善良，梦想考上大学离开小镇。"
            "他从小和林潮音一起长大，知道她身上的特殊之处。"
        ),
        attributes=FixedAttributes(mind=7, faith=4, physique=6, charm=6),
        personality=Personality(
            kindness=0.7,
            aggression=0.3,
            sensibility=0.6,
            rationality=0.7,
            curiosity=0.8,
        ),
        core_wish="考上大学，离开小镇，带林潮音去外面的世界",
    )


# ═══════════════════════════════════════════════════
# 批量获取
# ═══════════════════════════════════════════════════

def demo_npcs() -> list[NpcStatic]:
    """获取所有 Demo NPC 的静态数据。"""
    return [demo_lin_chaoyin(), demo_chen_yuanzhou()]
