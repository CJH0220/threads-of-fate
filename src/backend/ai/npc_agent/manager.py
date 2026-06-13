"""NPC Agent 管理器。

管理所有 NPC Agent 实例的生命周期：
- 创建（从配置或预设）
- 查询（按 ID、按等级、按地点）
- 批量状态更新
- 批量思考（异步并发）
- 生成初始化数据（给 Godot）
"""

from __future__ import annotations

import asyncio
from typing import Optional

from src.backend.models.npc import (
    AgentTier,
    Location,
    NpcListResponse,
    NpcSnapshot,
    NpcStatic,
    Slot,
)
from src.backend.ai.npc_agent.agent import NpcAgent
from src.backend.ai.npc_agent.static import demo_npcs


# ═══════════════════════════════════════════════════
# AgentManager
# ═══════════════════════════════════════════════════

class AgentManager:
    """管理所有 NPC Agent 实例。

    用法:
        manager = AgentManager()
        manager.init_from_demo()                # 加载 Demo NPC
        agent = manager.get("lin_chaoyin")      # 获取单个 Agent
        actions = await manager.all_think(1, Slot.MORNING)  # 批量思考
        response = manager.all_snapshots()      # 返回给前端
    """

    def __init__(self):
        self._agents: dict[str, NpcAgent] = {}

    # ── 创建 ──────────────────────────────────────

    def add(self, agent: NpcAgent) -> None:
        """添加一个 Agent。ID 重复时抛出 ValueError。"""
        if agent.npc_id in self._agents:
            raise ValueError(f"NPC '{agent.npc_id}' 已存在")
        self._agents[agent.npc_id] = agent

    def add_from_static(self, static: NpcStatic) -> NpcAgent:
        """从静态数据创建一个 Agent 并注册。"""
        agent = NpcAgent(static=static)
        self.add(agent)
        return agent

    def init_from_demo(self) -> None:
        """加载 Demo NPC（林潮音 + 陈远舟）。"""
        for static in demo_npcs():
            self.add_from_static(static)

    def init_from_statics(self, statics: list[NpcStatic]) -> None:
        """从静态数据列表批量创建。"""
        for static in statics:
            self.add_from_static(static)

    # ── 查询 ──────────────────────────────────────

    def get(self, npc_id: str) -> Optional[NpcAgent]:
        """获取单个 Agent，不存在返回 None。"""
        return self._agents.get(npc_id)

    def list_all(self) -> list[NpcAgent]:
        """获取所有 Agent。"""
        return list(self._agents.values())

    def list_by_tier(self, tier: AgentTier) -> list[NpcAgent]:
        """按等级筛选。"""
        return [a for a in self._agents.values() if a.tier == tier]

    def list_at_location(self, location: Location) -> list[NpcAgent]:
        """按地点筛选。"""
        return [a for a in self._agents.values() if a.location == location]

    @property
    def count(self) -> int:
        return len(self._agents)

    @property
    def npc_ids(self) -> list[str]:
        return list(self._agents.keys())

    # ── 快照 ──────────────────────────────────────

    def snapshot(self, npc_id: str) -> Optional[NpcSnapshot]:
        """获取单个 NPC 的完整快照。"""
        agent = self._agents.get(npc_id)
        return agent.snapshot() if agent else None

    def all_snapshots(self) -> NpcListResponse:
        """获取所有 NPC 的快照列表。"""
        snapshots = [a.snapshot() for a in self._agents.values()]
        return NpcListResponse(npcs=snapshots, total=len(snapshots))

    # ── 批量操作 ──────────────────────────────────

    async def all_think(self, day: int, slot: Slot) -> dict[str, str]:
        """所有 Agent 并发思考（S/A 级走 LLM，B/C 级走规则）。

        返回: {npc_id: 行动描述}
        """
        s_tier = self.list_by_tier(AgentTier.S) + self.list_by_tier(AgentTier.A)
        b_tier = self.list_by_tier(AgentTier.B) + self.list_by_tier(AgentTier.C)

        results: dict[str, str] = {}

        # S/A 级：并发 LLM 调用
        if s_tier:
            tasks = [agent.think(day, slot) for agent in s_tier]
            actions = await asyncio.gather(*tasks, return_exceptions=True)
            for agent, action in zip(s_tier, actions):
                if isinstance(action, Exception):
                    results[agent.npc_id] = agent._default_action(day, slot)
                else:
                    results[agent.npc_id] = action

        # B/C 级：同步规则
        for agent in b_tier:
            results[agent.npc_id] = agent._default_action(day, slot)

        return results

    def all_remember(self, day: int, slot: Slot, event_descriptions: dict[str, str],
                     importance: int = 5) -> None:
        """批量记录记忆。

        Args:
            event_descriptions: {npc_id: 事件描述}
        """
        for npc_id, desc in event_descriptions.items():
            agent = self._agents.get(npc_id)
            if agent:
                agent.remember(day, slot, desc, importance=importance)

    # ── 序列化 ────────────────────────────────────

    def to_dict(self) -> dict:
        """序列化所有 Agent（存档用）。"""
        return {
            npc_id: agent.to_dict()
            for npc_id, agent in self._agents.items()
        }

    @classmethod
    def from_dict(cls, data: dict, static_map: dict[str, NpcStatic]) -> "AgentManager":
        """从存档反序列化。"""
        manager = cls()
        for npc_id, agent_data in data.items():
            static = static_map.get(npc_id)
            if static is None:
                continue   # 跳过已删除的 NPC
            agent = NpcAgent.from_dict(agent_data, static)
            manager._agents[npc_id] = agent
        return manager
