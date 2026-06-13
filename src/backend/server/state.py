"""服务器全局状态管理。

Demo 阶段：使用模块级单例持有 AgentManager。
后期升级：替换为会话池（如 Redis / 内存 dict），对外接口不变。
"""

from __future__ import annotations

from typing import Optional

from src.backend.ai.npc_agent.manager import AgentManager


# 全局单例
_agent_manager: Optional[AgentManager] = None


def get_manager() -> AgentManager:
    """获取当前 AgentManager。"""
    global _agent_manager
    if _agent_manager is None:
        raise RuntimeError("AgentManager 尚未初始化，请先调用 init_manager()")
    return _agent_manager


def init_manager() -> AgentManager:
    """初始化 AgentManager（加载 Demo NPC）。"""
    global _agent_manager
    _agent_manager = AgentManager()
    _agent_manager.init_from_demo()
    return _agent_manager


def is_initialized() -> bool:
    """检查是否已初始化。"""
    return _agent_manager is not None


def reset() -> None:
    """重置 AgentManager（用于重新开始游戏）。"""
    global _agent_manager
    _agent_manager = None
