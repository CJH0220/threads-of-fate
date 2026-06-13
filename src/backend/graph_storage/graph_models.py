"""数据模型定义：NPC 节点 与 缘线边。"""

import re
from dataclasses import dataclass
from typing import Set

# 合法的缘线类型
VALID_EDGE_TYPES: Set[str] = {"红", "金", "蓝", "灰", "黑"}

# NPC id 合法性正则：仅允许字母、数字、下划线
_NPC_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_]+$")


@dataclass
class NPC:
    """NPC 节点。"""
    id: str       # 唯一标识，如 "lin_chaoyin"
    name: str     # 中文名，如 "林潮音"

    def __post_init__(self):
        if not self.id or not isinstance(self.id, str):
            raise ValueError(f"NPC id 不能为空: {self.id!r}")
        if not _NPC_ID_PATTERN.match(self.id):
            raise ValueError(
                f"NPC id 只能包含字母、数字、下划线: {self.id!r}"
            )
        if not self.name or not isinstance(self.name, str):
            raise ValueError(f"NPC name 不能为空: {self.name!r}")


@dataclass
class Edge:
    """缘线边（有向）。"""
    from_id: str     # 源 NPC id
    to_id: str       # 目标 NPC id
    type: str        # 关系性质: 红/金/蓝/灰/黑
    strength: int    # 强度 0–100
    glow: int        # 活跃值 0–100

    def __post_init__(self):
        if not self.from_id or not isinstance(self.from_id, str):
            raise ValueError(f"Edge from_id 不能为空: {self.from_id!r}")
        if not self.to_id or not isinstance(self.to_id, str):
            raise ValueError(f"Edge to_id 不能为空: {self.to_id!r}")
        if self.type not in VALID_EDGE_TYPES:
            raise ValueError(
                f"Edge type 必须是 {VALID_EDGE_TYPES} 之一: {self.type!r}"
            )
        if not isinstance(self.strength, int) or not (0 <= self.strength <= 100):
            raise ValueError(
                f"strength 必须是 0–100 的整数: {self.strength!r}"
            )
        if not isinstance(self.glow, int) or not (0 <= self.glow <= 100):
            raise ValueError(
                f"glow 必须是 0–100 的整数: {self.glow!r}"
            )
