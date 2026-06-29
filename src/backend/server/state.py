"""服务器全局状态管理。

Demo 阶段：使用模块级单例持有 GameSession。
后期升级：替换为会话池（如 Redis / 内存 dict），对外接口不变。
"""

from __future__ import annotations

from typing import Optional

from src.backend.ai.npc_agent.manager import AgentManager
from src.backend.data.npc_loader import load_npcs
from src.backend.ai.llm_client.load_balanced import LoadBalancedClient
from src.backend.engine.bond import BondManager
from src.backend.engine.karma import KarmaManager
from src.backend.engine.time import TimeState
from src.backend.engine.resource import ResourceState
from src.backend.engine.game_session import GameSession


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


# ── 缘线 ────────────────────────────────────────

def _create_bond_manager(npcs) -> BondManager:
    """创建缘线管理器并注入初始关系。"""
    mgr = BondManager()
    mgr.register_npcs([n.id for n in npcs])

    # 核心初始关系（设计文档 §8.7）
    mgr.set("lin_chaoyin", "chen_yuanzhou", "红", 70, 60)
    mgr.set("chen_yuanzhou", "lin_chaoyin", "红", 75, 55)
    mgr.set("lin_chaoyin", "huiyuan", "灰", 20, 50)
    mgr.set("huiyuan", "lin_chaoyin", "金", 50, 70)
    mgr.set("gu_chenzhou", "chen_haisheng", "金", 60, 85)
    mgr.set("gu_chenzhou", "lin_chaoyin", "黑", 15, 80)
    mgr.set("chen_haisheng", "chen_yuanzhou", "蓝", 35, 20)
    mgr.set("chen_yuanzhou", "chen_haisheng", "蓝", 40, 30)
    mgr.set("chen_haisheng", "su_wan", "蓝", 45, 15)
    mgr.set("lin_yueqin", "lin_chaoyin", "蓝", 70, 40)
    mgr.set("jiang_xueyi", "xu_qing", "金", 45, 60)
    mgr.set("xu_mingchuan", "xu_qing", "蓝", 80, 30)
    mgr.set("xu_mingchuan", "zhou_xingzhi", "蓝", 55, 50)

    return mgr


# ── 业线 ────────────────────────────────────────

def _create_karma_manager() -> KarmaManager:
    """创建业线管理器并加载节点定义。"""
    mgr = KarmaManager()
    mgr.init_from_csv()
    return mgr


# 全局单例
_session: Optional[GameSession] = None


def get_session() -> GameSession:
    """获取当前 GameSession。"""
    global _session
    if _session is None:
        raise RuntimeError("游戏尚未初始化，请先调用 POST /new-game")
    return _session


def get_manager() -> AgentManager:
    """获取当前 AgentManager（便捷方法）。"""
    return get_session().agents


def init_session() -> GameSession:
    """初始化完整游戏会话。"""
    global _session
    npcs = load_npcs()
    llm = _create_llm_client()

    bonds = _create_bond_manager(npcs)
    karma = _create_karma_manager()
    agents = AgentManager(llm=llm, bond_manager=bonds)
    agents.init_from_statics(npcs)

    _session = GameSession(
        time=TimeState(day=1),
        resource=ResourceState(),
        agents=agents,
        bonds=bonds,
        karma=karma,
    )
    return _session


def load_session(session: GameSession) -> None:
    """从存档恢复 GameSession，重新注入 LLM 客户端。"""
    global _session
    llm = _create_llm_client()
    for npc_id in session.agents.npc_ids:
        agent = session.agents.get(npc_id)
        if agent:
            agent.llm = llm
    _session = session


def is_initialized() -> bool:
    """检查是否已初始化。"""
    return _session is not None


def reset() -> None:
    """重置游戏会话。"""
    global _session
    _session = None
