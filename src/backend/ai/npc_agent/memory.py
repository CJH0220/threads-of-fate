"""NPC 情景记忆系统 —— 双库存储 + 艾宾浩斯遗忘检索。

提供：
- StructMemoryStore: 结构库（day/slot/importance/participants/emotion/location）
- VectorMemoryStore: 向量库（embedding）
- EpisodicRetrieval: 检索公式（向量相似度 + 时间衰减 + 重要性加权 + 阈值过滤）
- MemoryStore: 兼容层（封装双库 + 溢出精简 + 印象管理）

设计依据：NPCAgent记忆系统设计.md §3
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from src.backend.models.npc import (
    AgentMemory,
    Emotion,
    Impression,
    MemoryEntry,
    Slot,
)

# ═══════════════════════════════════════════════════
# 配置常量
# ═══════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "base_decay": 30.0,
    "vec_weight": 0.8,
    "recency_weight": 0.2,
    "imp_weight_base": 0.8,
    "imp_weight_scale": 0.4,
    "threshold": 0.15,
    "top_k": 12,
    "max_event_chain": 50,
    "max_key_memories": 30,
    "importance_threshold": 7,
    "vector_backend": "tfidf",       # "tfidf" | "embedding"
}

MAX_EVENT_CHAIN = 50
MAX_KEY_MEMORIES = 30
IMPORTANCE_THRESHOLD = 7


# ═══════════════════════════════════════════════════
# 记忆摘要（溢出产物）
# ═══════════════════════════════════════════════════

@dataclass
class MemorySummary:
    """记忆被压缩后的摘要。"""
    text: str
    original_count: int
    compressed_at_day: int
    compressed_at_slot: Slot


# ═══════════════════════════════════════════════════
# 结构库
# ═══════════════════════════════════════════════════

class StructMemoryStore:
    """情景记忆结构库 —— 按 memory_id 索引。

    支持：
    - 按时间范围查询
    - 按参与者筛选
    - 按地点筛选
    - 按重要性筛选
    """

    def __init__(self):
        self._entries: Dict[str, MemoryEntry] = {}

    # ── CRUD ───────────────────────────────────────

    def put(self, entry: MemoryEntry) -> None:
        self._entries[entry.memory_id] = entry

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        return self._entries.get(memory_id)

    def remove(self, memory_id: str) -> bool:
        if memory_id in self._entries:
            del self._entries[memory_id]
            return True
        return False

    # ── 查询 ───────────────────────────────────────

    def all(self) -> List[MemoryEntry]:
        return list(self._entries.values())

    def count(self) -> int:
        return len(self._entries)

    def by_day_range(self, from_day: int, to_day: int) -> List[MemoryEntry]:
        return [
            e for e in self._entries.values()
            if from_day <= e.day <= to_day
        ]

    def by_participant(self, npc_id: str) -> List[MemoryEntry]:
        return [
            e for e in self._entries.values()
            if npc_id in e.participants
        ]

    def by_location(self, location: str) -> List[MemoryEntry]:
        return [
            e for e in self._entries.values()
            if e.location == location
        ]

    def by_importance_above(self, min_imp: int) -> List[MemoryEntry]:
        return [e for e in self._entries.values() if e.importance >= min_imp]

    def recent(self, n: int = 10, current_day: int = 60) -> List[MemoryEntry]:
        """按 day 排序，取最近 n 条。"""
        sorted_entries = sorted(self._entries.values(), key=lambda e: e.day, reverse=True)
        return sorted_entries[:n]

    def today(self, day: int) -> List[MemoryEntry]:
        return [e for e in self._entries.values() if e.day == day]

    # ── 序列化 ────────────────────────────────────

    def to_list(self) -> List[dict]:
        return [e.model_dump() for e in self._entries.values()]

    @classmethod
    def from_list(cls, data: List[dict]) -> "StructMemoryStore":
        store = cls()
        for item in data:
            entry = MemoryEntry(**item)
            store.put(entry)
        return store


# ═══════════════════════════════════════════════════
# 向量库
# ═══════════════════════════════════════════════════

class BaseVectorStore:
    """向量库抽象基类。

    子类实现：
    - put(): 存储 memory_id → 向量/文本
    - compute_similarity(): 计算查询与记忆的相似度 (0~1)
    - to_dict() / from_dict(): 序列化
    """

    def put(self, memory_id: str, embedding: Optional[List[float]] = None,
            description: str = "") -> None:
        raise NotImplementedError

    def get(self, memory_id: str) -> Optional[list]:
        raise NotImplementedError

    def remove(self, memory_id: str) -> bool:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def compute_similarity(
        self,
        memory_id: str,
        query_embedding: Optional[List[float]] = None,
        query_text: str = "",
    ) -> float:
        raise NotImplementedError

    def to_dict(self) -> dict:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict) -> "BaseVectorStore":
        raise NotImplementedError


class EmbeddingVectorStore(BaseVectorStore):
    """基于外部 embedding 模型的向量库。

    使用真实的 embedding 向量做余弦相似度计算。
    接入 DeepSeek API / 本地模型时使用。
    """

    def __init__(self):
        self._embeddings: Dict[str, List[float]] = {}

    def put(self, memory_id: str, embedding: Optional[List[float]] = None,
            description: str = "") -> None:
        self._embeddings[memory_id] = embedding or []

    def get(self, memory_id: str) -> Optional[List[float]]:
        return self._embeddings.get(memory_id)

    def remove(self, memory_id: str) -> bool:
        if memory_id in self._embeddings:
            del self._embeddings[memory_id]
            return True
        return False

    def count(self) -> int:
        return len(self._embeddings)

    def compute_similarity(
        self,
        memory_id: str,
        query_embedding: Optional[List[float]] = None,
        query_text: str = "",
    ) -> float:
        """嵌入向量余弦相似度。

        - 双方有有效 embedding → 余弦相似度
        - 任一方为空 → 降级到 0.5（等后续补充 embedding）
        """
        mem_emb = self._embeddings.get(memory_id, [])
        if not mem_emb or not query_embedding:
            return 0.5

        dot = sum(a * b for a, b in zip(mem_emb, query_embedding))
        norm_a = math.sqrt(sum(a * a for a in mem_emb))
        norm_b = math.sqrt(sum(b * b for b in query_embedding))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))

    def to_dict(self) -> dict:
        return {
            "backend": "embedding",
            "embeddings": dict(self._embeddings),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EmbeddingVectorStore":
        store = cls()
        store._embeddings = dict(data.get("embeddings", {}))
        return store


class TfidfVectorStore(BaseVectorStore):
    """基于 TF-IDF 词袋模型的向量库。

    零外部依赖，纯 Python。
    自动对中文文本做字符级 n-gram 分词 + TF-IDF 加权 → 余弦相似度。

    优点：开箱即用，"巫女"和"寺庙"在同一句中出现频率高 → 相关度上升
    局限：不捕捉语义关联（"巫女"和"献祭"在词袋层面不相关）
    """

    def __init__(self):
        self._documents: Dict[str, str] = {}       # memory_id → description
        self._vocabulary: Dict[str, int] = {}      # token → index
        self._idf: Dict[str, float] = {}           # token → idf
        self._tfidf_vectors: Dict[str, List[float]] = {}  # memory_id → tfidf vector
        self._dirty: bool = False                   # vocab / idf 是否需要重建

    def put(self, memory_id: str, embedding: Optional[List[float]] = None,
            description: str = "") -> None:
        self._documents[memory_id] = description
        self._dirty = True  # 标记需要重建

    def get(self, memory_id: str) -> Optional[List[float]]:
        if not self._documents.get(memory_id):
            return None
        if self._dirty:
            self._rebuild_vocab()
        return self._tfidf_vectors.get(memory_id)

    def remove(self, memory_id: str) -> bool:
        if memory_id in self._documents:
            del self._documents[memory_id]
            self._tfidf_vectors.pop(memory_id, None)
            self._dirty = True
            return True
        return False

    def count(self) -> int:
        return len(self._documents)

    def compute_similarity(
        self,
        memory_id: str,
        query_embedding: Optional[List[float]] = None,
        query_text: str = "",
    ) -> float:
        """TF-IDF 余弦相似度。

        - 优先用 query_embedding（如果传了真实 embedding）
        - 否则用 query_text 分词计算 TF-IDF 向量
        """
        if self._dirty:
            self._rebuild_vocab()

        # 如果有真实 embedding，走 embedding 逻辑
        if query_embedding and len(query_embedding) > 0:
            mem_vec = self._tfidf_vectors.get(memory_id)
            if not mem_vec:
                # 有 embedding 但没有 tfidf → 创建临时的
                return 0.5

        # TF-IDF 向量
        doc_vec = self._tfidf_vectors.get(memory_id)
        if not doc_vec:
            return 0.5  # 文档不存在

        if not query_text:
            return 0.5  # 无查询文本，返回默认值

        query_tokens = self._tokenize(query_text)
        if not query_tokens:
            return 0.5

        # 构建查询 TF-IDF 向量
        query_vec = self._compute_tfidf(query_tokens)

        # 余弦相似度
        return self._cosine(doc_vec, query_vec)

    # ── 内部方法 ──────────────────────────────────

    _CHINESE_STOP_WORDS = {
        "的", "了", "在", "是", "我", "和", "就", "都", "也",
        "不", "有", "要", "会", "能", "去", "到", "说", "来",
        "这", "那", "一", "个", "会", "着", "过", "被", "把",
    }

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中文分词：字符级 bigram + 单字。

        "巫女候选" → ["巫女", "女候", "候选"]
        过滤掉中文停用词和标点。
        """
        # 过滤非中文字符
        chars = [c for c in text if '一' <= c <= '鿿']
        if len(chars) <= 1:
            return chars

        tokens: List[str] = []
        for i in range(len(chars) - 1):
            bigram = chars[i] + chars[i + 1]
            tokens.append(bigram)
        return tokens

    def _rebuild_vocab(self) -> None:
        """重建词汇表和 TF-IDF 向量。"""
        self._vocabulary.clear()
        self._tfidf_vectors.clear()

        if not self._documents:
            self._dirty = False
            return

        # 第一遍：构建词汇表
        all_tokens: Dict[str, List[List[str]]] = {}  # memory_id → tokens
        doc_count = len(self._documents)

        for memory_id, text in self._documents.items():
            tokens = self._tokenize(text)
            all_tokens[memory_id] = tokens
            for token in set(tokens):
                self._vocabulary[token] = self._vocabulary.get(token, 0) + 1

        # 计算 IDF
        self._idf.clear()
        for token, df in self._vocabulary.items():
            self._idf[token] = math.log((doc_count + 1) / (df + 1)) + 1.0

        # 第二遍：构建 TF-IDF 向量
        for memory_id, tokens in all_tokens.items():
            self._tfidf_vectors[memory_id] = self._compute_tfidf(tokens)

        self._dirty = False

    def _compute_tfidf(self, tokens: List[str]) -> List[float]:
        """计算 tokens 的 TF-IDF 稀疏向量（密集表示）。"""
        if not self._vocabulary:
            return []

        # token 计数
        tf: Dict[str, float] = {}
        token_count = len(tokens)
        for t in tokens:
            tf[t] = tf.get(t, 0.0) + 1.0

        # 归一化 + IDF
        vec = [0.0] * len(self._vocabulary)
        for i, (token, idx) in enumerate(sorted(self._vocabulary.items(), key=lambda x: x[1])):
            # 用词表索引确保向量维度一致
            pass

        # 实际用字典存储，cosine 时按交集计算（稀疏）
        result: Dict[str, float] = {}
        for token, count in tf.items():
            if token in self._idf:
                result[token] = (count / token_count) * self._idf[token]

        # 转为与词表对齐的密集向量
        dense = [0.0] * len(self._vocabulary)
        for token, weight in result.items():
            idx = list(self._vocabulary.keys()).index(token)
            dense[idx] = weight

        return dense

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        """余弦相似度。"""
        if len(a) != len(b) or len(a) == 0:
            return 0.5
        dot = sum(ai * bi for ai, bi in zip(a, b))
        norm_a = math.sqrt(sum(ai * ai for ai in a))
        norm_b = math.sqrt(sum(bi * bi for bi in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))

    # ── 序列化 ────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "backend": "tfidf",
            "documents": dict(self._documents),
            "vocabulary": dict(self._vocabulary),
            "idf": dict(self._idf),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TfidfVectorStore":
        store = cls()
        store._documents = dict(data.get("documents", {}))
        store._vocabulary = dict(data.get("vocabulary", {}))
        store._idf = dict(data.get("idf", {}))
        store._dirty = True  # 从存档恢复后需要重建向量
        store._rebuild_vocab()
        return store


# 向后兼容别名
VectorMemoryStore = EmbeddingVectorStore


# ═══════════════════════════════════════════════════
# 向量库工厂
# ═══════════════════════════════════════════════════

def create_vector_store(backend: str = "tfidf") -> BaseVectorStore:
    """根据配置创建向量库实例。

    Args:
        backend: "tfidf" | "embedding"
    """
    if backend == "embedding":
        return EmbeddingVectorStore()
    return TfidfVectorStore()


# ═══════════════════════════════════════════════════
# 情景记忆检索
# ═══════════════════════════════════════════════════

@dataclass
class EpisodicHit:
    """检索命中项。"""
    memory_id: str
    entry: MemoryEntry
    vector_score: float          # 0~1
    recency_score: float         # 0~1
    base_relevance: float        # vec*0.8 + recency*0.2
    importance_weight: float     # 0.8 + norm_imp*0.4
    final_score: float           # base_relevance * importance_weight


class EpisodicRetrieval:
    """情景记忆检索器。

    公式（来自 NPCAgent记忆系统设计.md §3.3）：
        norm_imp = importance / 10
        S = base_decay * norm_imp
        recency_score = e^(-days_elapsed / S)
        base_relevance = vec_score * vec_weight + recency_score * recency_weight
        importance_weight = imp_weight_base + norm_imp * imp_weight_scale
        final_score = base_relevance * importance_weight
    """

    def __init__(self, config: Optional[dict] = None):
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.base_decay: float = cfg["base_decay"]
        self.vec_weight: float = cfg["vec_weight"]
        self.recency_weight: float = cfg["recency_weight"]
        self.imp_weight_base: float = cfg["imp_weight_base"]
        self.imp_weight_scale: float = cfg["imp_weight_scale"]
        self.threshold: float = cfg["threshold"]
        self.top_k: int = cfg["top_k"]

    def retrieve(
        self,
        struct_store: StructMemoryStore,
        vector_store: BaseVectorStore,
        current_day: int,
        query_embedding: Optional[List[float]] = None,
        query_text: str = "",
        location_filter: Optional[str] = None,
        participant_filter: Optional[str] = None,
    ) -> List[EpisodicHit]:
        """检索情景记忆。

        Args:
            struct_store: 结构库
            vector_store: 向量库
            current_day: 当前天数
            query_embedding: 查询向量（embedding 后端使用）
            query_text: 查询文本（TF-IDF 后端使用）
            location_filter: 地点筛选（可选）
            participant_filter: 参与者筛选（可选）

        Returns:
            按 final_score 降序排列的命中列表（已过滤低于阈值的）
        """
        hits: List[EpisodicHit] = []

        for entry in struct_store.all():
            # 可选的结构筛选
            if location_filter and entry.location != location_filter:
                continue
            if participant_filter and participant_filter not in entry.participants:
                continue

            # 向量相似度（embedding 或 TF-IDF）
            vec_score = vector_store.compute_similarity(
                entry.memory_id, query_embedding, query_text
            )

            # 时间近因性（艾宾浩斯遗忘）
            days_elapsed = max(0, current_day - entry.day)
            norm_imp = entry.importance / 10.0
            S = self.base_decay * norm_imp  # 记忆强度
            recency_score = math.exp(-days_elapsed / S) if S > 0 else 0.0

            # 基础相关度
            base_relevance = (
                vec_score * self.vec_weight + recency_score * self.recency_weight
            )

            # 重要性加权
            importance_weight = self.imp_weight_base + norm_imp * self.imp_weight_scale

            # 最终得分
            final_score = base_relevance * importance_weight

            hits.append(EpisodicHit(
                memory_id=entry.memory_id,
                entry=entry,
                vector_score=vec_score,
                recency_score=recency_score,
                base_relevance=base_relevance,
                importance_weight=importance_weight,
                final_score=final_score,
            ))

        # 阈值过滤
        hits = [h for h in hits if h.final_score >= self.threshold]

        # 降序排序
        hits.sort(key=lambda h: h.final_score, reverse=True)

        # Top K
        return hits[:self.top_k]


# ═══════════════════════════════════════════════════
# MemoryStore（兼容层 —— 封装双库 + 印象 + 溢出）
# ═══════════════════════════════════════════════════

class MemoryStore:
    """管理单个 NPC 的情景记忆。

    内部结构：
    - struct: StructMemoryStore（结构库）
    - vector: VectorMemoryStore（向量库）
    - impressions: 情感印象
    - summaries: 溢出压缩摘要
    - retrieval: EpisodicRetrieval（检索器）
    """

    def __init__(
        self,
        npc_id: str,
        memory: Optional[AgentMemory] = None,
        config: Optional[dict] = None,
    ):
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.npc_id = npc_id
        self.struct = StructMemoryStore()
        self.vector = create_vector_store(backend=cfg.get("vector_backend", "tfidf"))
        self.retrieval = EpisodicRetrieval(cfg)

        self._impressions: Dict[str, Impression] = {}
        self._summaries: List[MemorySummary] = []
        self._memory_overflow_count: int = 0

        # 如果有旧数据，迁移
        if memory is not None:
            self._load_from_legacy(memory)

    # ── 查询 ──────────────────────────────────────

    @property
    def event_count(self) -> int:
        return self.struct.count()

    @property
    def key_count(self) -> int:
        return len([
            e for e in self.struct.all()
            if e.importance >= IMPORTANCE_THRESHOLD
        ])

    @property
    def overflow_count(self) -> int:
        return self._memory_overflow_count

    def recent_events(self, n: int = 10) -> List[MemoryEntry]:
        """获取最近 n 条事件。"""
        sorted_entries = sorted(
            self.struct.all(), key=lambda e: (e.day, e.slot.value), reverse=True
        )
        return sorted_entries[:n]

    def top_key_memories(self, n: int = 5) -> List[MemoryEntry]:
        """获取最重要的 n 条关键记忆。"""
        key = [
            e for e in self.struct.all()
            if e.importance >= IMPORTANCE_THRESHOLD
        ]
        key.sort(key=lambda e: e.importance, reverse=True)
        return key[:n]

    def get_impression(self, npc_id: str) -> Optional[Impression]:
        return self._impressions.get(npc_id)

    def all_impressions(self) -> Dict[str, Impression]:
        return dict(self._impressions)

    # ── 事件记忆 ──────────────────────────────────

    def remember(
        self,
        day: int,
        slot: Slot,
        description: str,
        importance: int = 5,
        emotion: Emotion = Emotion.NEUTRAL,
        event_id: str = "",
        participants: Optional[List[str]] = None,
        location: str = "",
        embedding: Optional[List[float]] = None,
    ) -> MemoryEntry:
        """记录一条情景记忆 → 写入双库。

        自动判定：
        - event_chain 超过上限 → 触发溢出精简
        """
        entry = MemoryEntry(
            day=day,
            slot=slot,
            event_id=event_id,
            description=description,
            importance=importance,
            emotion=emotion,
            participants=participants or [],
            location=location,
        )

        # 写入结构库
        self.struct.put(entry)

        # 写入向量库（传入 description 给 TF-IDF 后端用）
        self.vector.put(entry.memory_id, embedding, description=description)

        # 溢出检查
        if self.struct.count() > MAX_EVENT_CHAIN:
            self._compact_event_chain(day, slot)

        return entry

    # ── 检索 ──────────────────────────────────────

    def retrieve(
        self,
        current_day: int,
        query_embedding: Optional[List[float]] = None,
        query_text: str = "",
        location_filter: Optional[str] = None,
        participant_filter: Optional[str] = None,
    ) -> List[EpisodicHit]:
        """使用检索公式检索情景记忆。"""
        return self.retrieval.retrieve(
            struct_store=self.struct,
            vector_store=self.vector,
            current_day=current_day,
            query_embedding=query_embedding,
            query_text=query_text,
            location_filter=location_filter,
            participant_filter=participant_filter,
        )

    # ── LLM 上下文 ────────────────────────────────

    def context_for_llm(
        self,
        current_day: int,
        max_events: int = 10,
        location_filter: Optional[str] = None,
        participant_filter: Optional[str] = None,
        query_text: str = "",
    ) -> str:
        """生成给 LLM 的记忆上下文——使用检索公式。

        Args:
            current_day: 当前天数
            max_events: 最多返回的条数
            location_filter: 地点筛选
            participant_filter: 参与者筛选
            query_text: 当前情境文本（给 TF-IDF 做语义匹配）
        """
        hits = self.retrieve(
            current_day=current_day,
            query_text=query_text,
            location_filter=location_filter,
            participant_filter=participant_filter,
        )
        hits = hits[:max_events]

        parts: List[str] = []

        # 检索结果
        if hits:
            parts.append("【最近经历】")
            for i, h in enumerate(hits):
                e = h.entry
                parts.append(
                    f"  Day{e.day} {e.slot.value}: {e.description}"
                    f"（重要性{e.importance}，{e.emotion.value}）"
                )

        # 关键印象
        if self._impressions:
            parts.append("【对他人印象】")
            for npc_id, imp in self._impressions.items():
                parts.append(
                    f"  {npc_id}: 好感{imp.affinity} 信任{imp.trust}"
                    + (f" ({imp.label})" if imp.label else "")
                )

        # 历史摘要
        if self._summaries:
            parts.append("【更早的回忆】")
            for s in self._summaries[-3:]:
                parts.append(f"  Day{s.compressed_at_day}: {s.text}")

        return "\n".join(parts) if parts else "（尚无记忆）"

    # ── 溢出处理 ──────────────────────────────────

    def _compact_event_chain(self, day: int, slot: Slot) -> None:
        """精简事件链：保留最近 20 + 最重要 10，其余合并为摘要。"""
        entries = self.struct.all()

        # 按重要性 Top 10
        by_importance = sorted(entries, key=lambda e: e.importance, reverse=True)
        top_10 = by_importance[:10]

        # 按时间最近 20
        by_time = sorted(entries, key=lambda e: (e.day, e.slot.value), reverse=True)
        recent_20 = by_time[:20]

        # 合并去重
        kept_ids = {e.memory_id for e in top_10} | {e.memory_id for e in recent_20}
        to_remove = [e for e in entries if e.memory_id not in kept_ids]

        # 构造摘要
        if to_remove:
            summary = MemorySummary(
                text=f"精简了 {len(to_remove)} 条记忆: "
                     + "; ".join(e.description[:20] for e in to_remove[:5])
                     + ("..." if len(to_remove) > 5 else ""),
                original_count=len(to_remove),
                compressed_at_day=day,
                compressed_at_slot=slot,
            )
            self._summaries.append(summary)

        # 双库同步删除
        for e in to_remove:
            self.struct.remove(e.memory_id)
            self.vector.remove(e.memory_id)

        self._memory_overflow_count += 1

    # ── 情感印象 ──────────────────────────────────

    def set_impression(self, npc_id: str, affinity: int = 50, trust: int = 50,
                       label: str = "") -> Impression:
        impression = Impression(
            npc_id=npc_id,
            affinity=affinity,
            trust=trust,
            label=label,
        )
        self._impressions[npc_id] = impression
        return impression

    def update_impression(
        self,
        npc_id: str,
        affinity_delta: int = 0,
        trust_delta: int = 0,
        label: Optional[str] = None,
    ) -> Optional[Impression]:
        existing = self._impressions.get(npc_id)
        if existing is None:
            affinity = max(0, min(100, 50 + affinity_delta))
            trust = max(0, min(100, 50 + trust_delta))
            return self.set_impression(npc_id, affinity, trust, label or "")

        existing.affinity = max(0, min(100, existing.affinity + affinity_delta))
        existing.trust = max(0, min(100, existing.trust + trust_delta))
        if label is not None:
            existing.label = label
        return existing

    # ── 序列化 ────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "npc_id": self.npc_id,
            "struct": self.struct.to_list(),
            "vector": self.vector.to_dict(),
            "impressions": {
                k: v.model_dump() for k, v in self._impressions.items()
            },
            "summaries": [
                {
                    "text": s.text,
                    "original_count": s.original_count,
                    "compressed_at_day": s.compressed_at_day,
                    "compressed_at_slot": s.compressed_at_slot.value,
                }
                for s in self._summaries
            ],
            "memory_overflow_count": self._memory_overflow_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryStore":
        store = cls(npc_id=data["npc_id"])
        store.struct = StructMemoryStore.from_list(data.get("struct", []))
        store.vector = VectorMemoryStore.from_dict(data.get("vector", {}))
        store._impressions = {
            k: Impression(**v) for k, v in data.get("impressions", {}).items()
        }
        for s in data.get("summaries", []):
            store._summaries.append(MemorySummary(
                text=s["text"],
                original_count=s["original_count"],
                compressed_at_day=s["compressed_at_day"],
                compressed_at_slot=Slot(s["compressed_at_slot"]),
            ))
        store._memory_overflow_count = data.get("memory_overflow_count", 0)
        return store

    # ── 旧数据迁移 ────────────────────────────────

    def _load_from_legacy(self, memory: AgentMemory) -> None:
        """从旧版 AgentMemory 迁移数据到双库。"""
        for entry in memory.event_chain:
            # 旧版没有 memory_id，创建时自动生成
            self.struct.put(entry)
            self.vector.put(entry.memory_id)

        self._impressions = {
            k: Impression(**v.model_dump() if hasattr(v, 'model_dump') else v)
            for k, v in memory.impressions.items()
        }
        self._memory_overflow_count = memory.memory_overflow_count
