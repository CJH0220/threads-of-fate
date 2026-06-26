"""服务器全局状态管理。

Demo 阶段：使用模块级单例持有 AgentManager。
后期升级：替换为会话池（如 Redis / 内存 dict），对外接口不变。
"""

from __future__ import annotations

from typing import Optional

from src.backend.ai.npc_agent.manager import AgentManager
from src.backend.data.npc_loader import load_npcs
from src.backend.ai.llm_client.load_balanced import LoadBalancedClient


# ── LLM 客户端 ───────────────────────────────────

def _create_llm_client() -> LoadBalancedClient:
    """创建负载均衡 LLM 客户端（连接本地 llama.cpp）。"""
    return LoadBalancedClient(
        endpoints=["http://172.21.125.241:8080/v1/chat/completions"],
        per_endpoint_concurrency=2,
        timeout=60.0,
        max_retries=2,
        default_extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


# 全局单例
_agent_manager: Optional[AgentManager] = None


def get_manager() -> AgentManager:
    """获取当前 AgentManager。"""
    global _agent_manager
    if _agent_manager is None:
        raise RuntimeError("AgentManager 尚未初始化，请先调用 init_manager()")
    return _agent_manager


def init_manager() -> AgentManager:
    """初始化 AgentManager（从 CSV 加载 NPC，连接 LLM）。"""
    global _agent_manager
    llm = _create_llm_client()
    _agent_manager = AgentManager(llm=llm)
    _agent_manager.init_from_statics(load_npcs())
    return _agent_manager


def is_initialized() -> bool:
    """检查是否已初始化。"""
    return _agent_manager is not None


def reset() -> None:
    """重置 AgentManager（用于重新开始游戏）。"""
    global _agent_manager
    _agent_manager = None
