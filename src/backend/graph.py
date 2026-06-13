"""缘线图存储核心：邻接表 + 边字典 双索引结构。"""

from typing import Dict, List, Optional, Set, Tuple

from .models import NPC, Edge


class RelationshipGraph:
    """NPC 人物关系有向图。

    内部维护：
    - _npcs: 节点字典 {npc_id: NPC}
    - _edges: 边字典 {(from_id, to_id): Edge}
    - _outgoing: 出边邻接表 {from_id: {to_id, ...}}
    - _incoming: 入边邻接表 {to_id: {from_id, ...}}
    """

    def __init__(self):
        self._npcs: Dict[str, NPC] = {}
        self._edges: Dict[Tuple[str, str], Edge] = {}
        self._outgoing: Dict[str, Set[str]] = {}
        self._incoming: Dict[str, Set[str]] = {}

    # ─── 节点操作 ──────────────────────────────────

    def add_npc(self, npc_id: str, name: str) -> NPC:
        """添加一个 NPC 节点。id 重复时抛出 ValueError。"""
        if npc_id in self._npcs:
            raise ValueError(f"NPC '{npc_id}' 已存在")
        npc = NPC(id=npc_id, name=name)
        self._npcs[npc_id] = npc
        self._outgoing[npc_id] = set()
        self._incoming[npc_id] = set()
        return npc

    def remove_npc(self, npc_id: str) -> None:
        """删除 NPC 及其所有关联边。NPC 不存在时静默忽略。"""
        if npc_id not in self._npcs:
            return

        # 收集所有需要删除的边 key
        keys_to_remove = []
        for (f, t) in self._edges:
            if f == npc_id or t == npc_id:
                keys_to_remove.append((f, t))

        for key in keys_to_remove:
            self._remove_edge_internal(*key)

        self._outgoing.pop(npc_id, None)
        self._incoming.pop(npc_id, None)
        self._npcs.pop(npc_id, None)

    def get_npc(self, npc_id: str) -> Optional[NPC]:
        """获取 NPC，不存在返回 None。"""
        return self._npcs.get(npc_id)

    def list_npcs(self) -> List[NPC]:
        """列出所有 NPC。"""
        return list(self._npcs.values())

    @property
    def npc_count(self) -> int:
        return len(self._npcs)

    # ─── 边操作 ────────────────────────────────────

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        strength: int,
        glow: int,
    ) -> Edge:
        """添加或覆盖一条缘线。返回 Edge 对象。"""
        if from_id not in self._npcs:
            raise ValueError(f"源 NPC '{from_id}' 不存在")
        if to_id not in self._npcs:
            raise ValueError(f"目标 NPC '{to_id}' 不存在")

        edge = Edge(
            from_id=from_id,
            to_id=to_id,
            type=edge_type,
            strength=strength,
            glow=glow,
        )
        key = (from_id, to_id)
        self._edges[key] = edge
        self._outgoing[from_id].add(to_id)
        self._incoming[to_id].add(from_id)
        return edge

    def remove_edge(self, from_id: str, to_id: str) -> bool:
        """删除缘线。返回是否实际删除了边。"""
        return self._remove_edge_internal(from_id, to_id)

    def _remove_edge_internal(self, from_id: str, to_id: str) -> bool:
        """内部删除边，不做存在性检查。"""
        key = (from_id, to_id)
        if key not in self._edges:
            return False
        self._edges.pop(key, None)
        self._outgoing.get(from_id, set()).discard(to_id)
        self._incoming.get(to_id, set()).discard(from_id)
        return True

    def get_edge(self, from_id: str, to_id: str) -> Optional[Edge]:
        """查询单条缘线。"""
        return self._edges.get((from_id, to_id))

    def get_edges_of(self, npc_id: str, edge_type: Optional[str] = None) -> List[Edge]:
        """获取某 NPC 的所有出入边，可按类型过滤。NPC 不存在返回空列表。"""
        if npc_id not in self._npcs:
            return []
        result = []
        # 出边
        for to_id in self._outgoing.get(npc_id, set()):
            edge = self._edges.get((npc_id, to_id))
            if edge and (edge_type is None or edge.type == edge_type):
                result.append(edge)
        # 入边
        for from_id in self._incoming.get(npc_id, set()):
            edge = self._edges.get((from_id, npc_id))
            if edge and (edge_type is None or edge.type == edge_type):
                result.append(edge)
        return result

    def get_neighbors(
        self, npc_id: str, edge_type: Optional[str] = None
    ) -> Set[str]:
        """获取某 NPC 的所有邻居（被指向 + 指向它的 NPC），可按类型过滤。"""
        if npc_id not in self._npcs:
            return set()
        neighbors: Set[str] = set()
        for to_id in self._outgoing.get(npc_id, set()):
            edge = self._edges.get((npc_id, to_id))
            if edge and (edge_type is None or edge.type == edge_type):
                neighbors.add(to_id)
        for from_id in self._incoming.get(npc_id, set()):
            edge = self._edges.get((from_id, npc_id))
            if edge and (edge_type is None or edge.type == edge_type):
                neighbors.add(from_id)
        return neighbors

    def get_all_edges(self) -> List[Edge]:
        """列出图中所有边。"""
        return list(self._edges.values())

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    # ─── 批量查询 ──────────────────────────────────

    def get_outgoing(self, npc_id: str, edge_type: Optional[str] = None) -> List[Edge]:
        """获取 npc_id 指向别人的边。"""
        if npc_id not in self._npcs:
            return []
        result = []
        for to_id in self._outgoing.get(npc_id, set()):
            edge = self._edges.get((npc_id, to_id))
            if edge and (edge_type is None or edge.type == edge_type):
                result.append(edge)
        return result

    def get_incoming(self, npc_id: str, edge_type: Optional[str] = None) -> List[Edge]:
        """获取指向 npc_id 的边。"""
        if npc_id not in self._npcs:
            return []
        result = []
        for from_id in self._incoming.get(npc_id, set()):
            edge = self._edges.get((from_id, npc_id))
            if edge and (edge_type is None or edge.type == edge_type):
                result.append(edge)
        return result

    # ─── 摘要 ──────────────────────────────────────

    def summary(self) -> dict:
        """返回图的基本统计信息。"""
        return {
            "npc_count": self.npc_count,
            "edge_count": self.edge_count,
            "edge_type_distribution": self._type_distribution(),
        }

    def _type_distribution(self) -> Dict[str, int]:
        dist: Dict[str, int] = {}
        for edge in self._edges.values():
            dist[edge.type] = dist.get(edge.type, 0) + 1
        return dist
