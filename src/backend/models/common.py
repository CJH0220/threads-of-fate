"""通用 API 数据模型。

定义统一的请求/响应格式，供所有 API 端点使用。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .npc import NpcSnapshot


# ═══════════════════════════════════════════════════
# 统一响应格式
# ═══════════════════════════════════════════════════

class ApiResponse(BaseModel):
    """所有 REST 端点的统一响应外壳。"""
    success: bool = Field(..., description="请求是否成功")
    data: Any = Field(default=None, description="响应数据")
    error: str = Field(default="", description="错误信息（success=false 时）")
    changed_fields: Optional[List[str]] = Field(
        default=None, description="增量模式下变化的字段列表（可选）"
    )


# ═══════════════════════════════════════════════════
# 游戏状态响应（给前端的完整快照）
# ═══════════════════════════════════════════════════

class GameStateResponse(BaseModel):
    """游戏完整状态 —— 新游戏初始化或查询状态时返回。"""
    day: int = Field(default=1, ge=1, le=60, description="当前天数")
    slot: str = Field(default="morning", description="当前时段")
    incense: int = Field(default=50, ge=0, description="香火")
    divine_power: int = Field(default=10, ge=0, description="神力")
    yin_de: int = Field(default=0, ge=0, description="阴德")
    yang_de: int = Field(default=0, ge=0, description="阳德")
    npcs: List[NpcSnapshot] = Field(default_factory=list, description="所有 NPC 快照")
    npc_total: int = Field(default=0, description="NPC 总数")


# ═══════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════

def ok(data: Any = None) -> dict:
    """构建成功响应。"""
    return ApiResponse(success=True, data=data).model_dump()


def err(message: str) -> dict:
    """构建错误响应。"""
    return ApiResponse(success=False, error=message).model_dump()
