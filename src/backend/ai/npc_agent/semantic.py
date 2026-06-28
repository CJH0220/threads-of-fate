"""语义记忆系统 —— 条目存储 + 知识图谱 + 检索 + LLM 提取桩。

对应设计文档：NPCAgent记忆系统设计.md §4-7
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Set, Tuple

from src.backend.models.npc import (
    Entity,
    KnowledgeGraph,
    Relation,
    RetrievalContext,
    ScoredEntry,
    SemanticCategory,
    SemanticEntry,
    SemanticMemory,
)

# ═══════════════════════════════════════════════════
# 配置常量
# ═══════════════════════════════════════════════════

DEFAULT_SEMANTIC_CONFIG = {
    "vector_top_k": 10,
    "graph_max_hops": 2,
    "graph_hop_weights": {0: 1.0, 1: 0.5, 2: 0.25},
    "final_top_n": 8,
    "alpha": 0.6,        # 向量权重
    "beta": 0.4,         # 图谱权重
    "confidence_min": 0.3,
    "episodic_pending_threshold": 10,
    "semantic_overflow_threshold": 30,
    "graph_extract_threshold": 15,
    "extract_schedule": "end_of_day",
}


# ═══════════════════════════════════════════════════
# 知识图谱遍历
# ═══════════════════════════════════════════════════

def graph_one_hop(entity: str, relations: List[Relation]) -> List[Relation]:
    """一跳：找所有与该实体直接相关的关系。"""
    return [r for r in relations if r.subject == entity or r.object == entity]


def graph_two_hop(entity: str, relations: List[Relation]) -> List[Relation]:
    """两跳：通过中间实体找到间接关联的关系。"""
    neighbors: Set[str] = set()
    for r in graph_one_hop(entity, relations):
        neighbors.add(r.subject)
        neighbors.add(r.object)
    neighbors.discard(entity)

    result: List[Relation] = []
    seen_ids: Set[int] = set()
    for neighbor in neighbors:
        for r in graph_one_hop(neighbor, relations):
            rid = id(r)
            if rid not in seen_ids:
                seen_ids.add(rid)
                result.append(r)
    return result


def graph_distance(
    entity_a: str,
    entity_b: str,
    relations: List[Relation],
    max_hops: int = 3,
) -> int:
    """BFS 计算两个实体之间的最短跳数。"""
    if entity_a == entity_b:
        return 0

    visited: Set[str] = {entity_a}
    frontier: Set[str] = {entity_a}
    distance = 0

    for _ in range(max_hops):
        distance += 1
        next_frontier: Set[str] = set()
        for node in frontier:
            for r in graph_one_hop(node, relations):
                neighbor = r.object if r.subject == node else r.subject
                if neighbor == entity_b:
                    return distance
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier
        if not frontier:
            break

    return max_hops + 1  # 不可达


# ═══════════════════════════════════════════════════
# 语义记忆检索
# ═══════════════════════════════════════════════════

class SemanticRetriever:
    """语义记忆检索器 —— 向量检索 + 图谱检索，并行合并。

    公式（来自设计文档 §4.6）：
        final_score = alpha * vector_score + beta * normalized_graph_score
    """

    def __init__(self, config: Optional[dict] = None):
        cfg = {**DEFAULT_SEMANTIC_CONFIG, **(config or {})}
        self.vector_top_k: int = cfg["vector_top_k"]
        self.graph_max_hops: int = cfg["graph_max_hops"]
        self.graph_hop_weights: Dict[int, float] = cfg["graph_hop_weights"]
        self.final_top_n: int = cfg["final_top_n"]
        self.alpha: float = cfg["alpha"]
        self.beta: float = cfg["beta"]
        self.confidence_min: float = cfg["confidence_min"]

    def retrieve(
        self,
        entries: List[SemanticEntry],
        graph: KnowledgeGraph,
        context: RetrievalContext,
        query_embedding: Optional[List[float]] = None,
    ) -> List[ScoredEntry]:
        """并行检索语义记忆。

        Args:
            entries: 所有语义记忆
            graph: 知识图谱
            context: 当前情境
            query_embedding: 查询向量（embedding 模型提供）

        Returns:
            按 final_score 降序排列的命中列表
        """
        if not entries:
            return []

        context_entities = set(context.context_entities)
        if not context_entities and context.location:
            context_entities.add(context.location)
        if not context_entities and context.query_text:
            context_entities.add(context.query_text)

        # 置信度过滤
        entries = [e for e in entries if e.confidence >= self.confidence_min]

        results: Dict[str, ScoredEntry] = {}

        # ── 向量检索 ──────────────────────────────
        vector_hits = self._vector_retrieve(entries, query_embedding,
                                            context.query_text)

        # ── 图谱检索 ──────────────────────────────
        graph_hits = self._graph_retrieve(entries, graph, context_entities)

        # ── 合并 ──────────────────────────────────
        all_graph_scores = [h.graph_score for h in graph_hits if h.graph_score > 0]
        max_graph = max(all_graph_scores) if all_graph_scores else 1.0

        # 向量命中写入
        for vh in vector_hits:
            results[vh.description] = ScoredEntry(
                description=vh.description,
                vector_score=vh.vector_score,
                graph_score=0.0,
                final_score=0.0,
                source="vector",
            )

        # 图谱命中写入（合并时取 max 分数）
        for gh in graph_hits:
            norm_graph = gh.graph_score / max_graph if max_graph > 0 else 0.0
            if gh.description in results:
                existing = results[gh.description]
                existing.graph_score = max(existing.graph_score, norm_graph)
                existing.source = "both"
            else:
                results[gh.description] = ScoredEntry(
                    description=gh.description,
                    vector_score=0.0,
                    graph_score=norm_graph,
                    final_score=0.0,
                    source="graph",
                )

        # 最终得分
        for entry in results.values():
            entry.final_score = (
                self.alpha * entry.vector_score + self.beta * entry.graph_score
            )

        # 降序排序 + Top N
        sorted_entries = sorted(
            results.values(), key=lambda e: e.final_score, reverse=True
        )
        return sorted_entries[:self.final_top_n]

    # ── 内部方法 ──────────────────────────────────

    def _vector_retrieve(
        self,
        entries: List[SemanticEntry],
        query_embedding: Optional[List[float]],
        query_text: str,
    ) -> List[ScoredEntry]:
        """向量检索：embedding 余弦相似度（或 TF-IDF 兜底）。"""
        hits: List[ScoredEntry] = []
        for entry in entries:
            if query_embedding and entry.embedding:
                score = SemanticRetriever._cosine(
                    query_embedding, entry.embedding
                )
            elif query_text and entry.statement:
                # TF-IDF 简易兜底：关键词重叠
                score = SemanticRetriever._text_similarity(
                    query_text, entry.statement
                )
            else:
                score = 0.5

            hits.append(ScoredEntry(
                description=entry.statement,
                vector_score=score,
                graph_score=0.0,
                final_score=0.0,
                source="vector",
            ))

        hits.sort(key=lambda h: h.vector_score, reverse=True)
        return hits[:self.vector_top_k]

    def _graph_retrieve(
        self,
        entries: List[SemanticEntry],
        graph: KnowledgeGraph,
        context_entities: Set[str],
    ) -> List[ScoredEntry]:
        """图谱检索：从上下文实体出发，两跳内找到关联语义记忆。"""
        if not context_entities or not graph.relations:
            return []

        # 收集两跳内的所有关联实体
        related_entities: Dict[str, float] = {}  # entity → max_score

        for ctx_entity in context_entities:
            if ctx_entity not in graph.entities:
                continue
            # 0 跳：自己
            related_entities[ctx_entity] = max(
                related_entities.get(ctx_entity, 0.0),
                self.graph_hop_weights.get(0, 1.0),
            )

            # 1 跳
            for r in graph_one_hop(ctx_entity, graph.relations):
                neighbor = r.object if r.subject == ctx_entity else r.subject
                hop_score = self.graph_hop_weights.get(1, 0.5) * (
                    r.frequency / max(1, r.frequency)
                )
                related_entities[neighbor] = max(
                    related_entities.get(neighbor, 0.0), hop_score
                )

            # 2 跳
            if self.graph_max_hops >= 2:
                for r in graph_two_hop(ctx_entity, graph.relations):
                    for endpoint in (r.subject, r.object):
                        if endpoint != ctx_entity and endpoint not in related_entities:
                            hop_score = self.graph_hop_weights.get(2, 0.25)
                            related_entities[endpoint] = hop_score

        if not related_entities:
            return []

        # 将实体的图谱得分映射到语义记忆
        hits: List[ScoredEntry] = []
        for entry in entries:
            statement_entities = self._extract_entities_from_statement(
                entry.statement, graph
            )
            # 取该语句所有涉及的实体中，最大图谱得分
            max_graph_score = max(
                (related_entities.get(e, 0.0) for e in statement_entities),
                default=0.0,
            )
            if max_graph_score > 0:
                hits.append(ScoredEntry(
                    description=entry.statement,
                    vector_score=0.0,
                    graph_score=max_graph_score,
                    final_score=0.0,
                    source="graph",
                ))

        hits.sort(key=lambda h: h.graph_score, reverse=True)
        return hits

    # ── 工具方法 ──────────────────────────────────

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        """余弦相似度。"""
        if not a or not b or len(a) != len(b):
            return 0.5
        dot = sum(ai * bi for ai, bi in zip(a, b))
        norm_a = math.sqrt(sum(ai * ai for ai in a))
        norm_b = math.sqrt(sum(bi * bi for bi in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))

    @staticmethod
    def _text_similarity(query: str, statement: str) -> float:
        """词袋相似度（embedding 不可用时的兜底）。"""
        query_chars = set(query.replace(" ", ""))
        stmt_chars = set(statement.replace(" ", ""))
        if not stmt_chars:
            return 0.5
        overlap = len(query_chars & stmt_chars)
        return min(1.0, 0.3 + overlap / max(len(stmt_chars), 1) * 0.7)

    @staticmethod
    def _extract_entities_from_statement(
        statement: str, graph: KnowledgeGraph
    ) -> List[str]:
        """从 statement 中提取已知图谱实体的名字。"""
        found: List[str] = []
        for name in graph.entities:
            if name in statement:
                found.append(name)
        return found if found else [statement[:20]]


# ═══════════════════════════════════════════════════
# SemanticStore
# ═══════════════════════════════════════════════════

class SemanticStore:
    """管理单个 NPC 的语义记忆。

    内部：
    - entries: 语义记忆列表
    - graph: 知识图谱
    - retriever: SemanticRetriever
    """

    def __init__(self, npc_id: str, config: Optional[dict] = None):
        self.npc_id = npc_id
        self.entries: List[SemanticEntry] = []
        self.graph = KnowledgeGraph(npc_id=npc_id)
        self.retriever = SemanticRetriever(config)

        self._config = {**DEFAULT_SEMANTIC_CONFIG, **(config or {})}
        self.pending_episodic: List[str] = []
        self.last_extraction_day: int = 0
        self.last_graph_extraction_day: int = 0

    # ── 查询 ──────────────────────────────────────

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    def by_category(self, category: SemanticCategory) -> List[SemanticEntry]:
        return [e for e in self.entries if e.category == category]

    def by_confidence_above(self, threshold: float) -> List[SemanticEntry]:
        return [e for e in self.entries if e.confidence >= threshold]

    # ── 写入 ──────────────────────────────────────

    def add(self, statement: str, category: SemanticCategory = SemanticCategory.RULE,
            confidence: float = 0.5, source_events: Optional[List[str]] = None,
            created_day: int = 1, embedding: Optional[List[float]] = None,
            entities: Optional[List[dict]] = None,
            relations: Optional[List[dict]] = None) -> SemanticEntry:
        """添加一条语义记忆，同时更新知识图谱。"""
        entry = SemanticEntry(
            statement=statement,
            confidence=confidence,
            category=category,
            source_events=source_events or [],
            created_day=created_day,
            embedding=embedding or [],
        )
        self.entries.append(entry)

        # 更新知识图谱
        if entities:
            for e_data in entities:
                name = e_data.get("name", "")
                if name and name not in self.graph.entities:
                    self.graph.entities[name] = Entity(
                        name=name,
                        type=e_data.get("type", "concept"),
                        mentions=1,
                    )
                elif name in self.graph.entities:
                    self.graph.entities[name].mentions += 1

        if relations:
            for r_data in relations:
                rel = Relation(
                    subject=r_data.get("subject", ""),
                    predicate=r_data.get("predicate", ""),
                    object=r_data.get("object", ""),
                    source_statement=statement,
                    frequency=1,
                )
                # 检查是否重复
                existing = [
                    r for r in self.graph.relations
                    if r.subject == rel.subject
                    and r.predicate == rel.predicate
                    and r.object == rel.object
                ]
                if existing:
                    existing[0].frequency += 1
                else:
                    self.graph.relations.append(rel)

        return entry

    def update_confidence(self, statement: str, delta: float) -> bool:
        """增量更新置信度。"""
        for entry in self.entries:
            if entry.statement == statement:
                entry.confidence = max(0.0, min(1.0, entry.confidence + delta))
                return True
        return False

    # ── 检索 ──────────────────────────────────────

    def retrieve(
        self,
        context: RetrievalContext,
        query_embedding: Optional[List[float]] = None,
    ) -> List[ScoredEntry]:
        """检索语义记忆。"""
        return self.retriever.retrieve(
            entries=self.entries,
            graph=self.graph,
            context=context,
            query_embedding=query_embedding,
        )

    # ── LLM 提取桩（等后续实现）──────────────────

    def mark_episodic_processed(self, event_id: str) -> None:
        """标记一条情景记忆已处理（等待提取）。"""
        self.pending_episodic.append(event_id)

    def should_extract_from_episodic(self) -> bool:
        """是否应该触发"情景→语义"提取。"""
        return (
            len(self.pending_episodic)
            >= self._config["episodic_pending_threshold"]
        )

    def should_extract_graph(self) -> bool:
        """是否应该触发"语义→图谱"提取。"""
        new_since_last = [
            e for e in self.entries
            if e.created_day > self.last_graph_extraction_day
        ]
        return len(new_since_last) >= self._config["graph_extract_threshold"]

    def needs_overflow_compaction(self) -> bool:
        """检查语义记忆是否超过溢出上限。"""
        return len(self.entries) >= self._config["semantic_overflow_threshold"]

    # ── 序列化 ────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "entries": [e.model_dump() for e in self.entries],
            "graph": self.graph.model_dump(),
            "pending_episodic": list(self.pending_episodic),
            "last_extraction_day": self.last_extraction_day,
            "last_graph_extraction_day": self.last_graph_extraction_day,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticStore":
        store = cls(npc_id=data["npc_id"])
        store.entries = [
            SemanticEntry(**e) for e in data.get("entries", [])
        ]
        store.graph = KnowledgeGraph(**data.get("graph", {"npc_id": data["npc_id"]}))
        store.pending_episodic = list(data.get("pending_episodic", []))
        store.last_extraction_day = data.get("last_extraction_day", 0)
        store.last_graph_extraction_day = data.get("last_graph_extraction_day", 0)
        return store
