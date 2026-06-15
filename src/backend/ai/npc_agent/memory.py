"""NPC 记忆系统 —— 事件链 + 关键记忆 + 情感印象 + 溢出处理。

提供：
- 事件记忆的添加与重要性排序
- 情感印象的读写
- 记忆溢出时的自动精简
- 记忆摘要生成（供 LLM 上下文使用）

设计约束（来自策划案 §8.6.6）：
- Memory 条数 > 50 → 按重要性排序，保留前 30，其余合并为摘要
- Memory 总 token > 10k → LLM 生成精简摘要
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

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

MAX_EVENT_CHAIN = 50       # 完整事件链上限
MAX_KEY_MEMORIES = 30      # 关键记忆上限
IMPORTANCE_THRESHOLD = 7   # 重要性 >= 此值自动进入关键记忆


# ═══════════════════════════════════════════════════
# 记忆摘要（溢出产物）
# ═══════════════════════════════════════════════════

@dataclass
class MemorySummary:
    """记忆被压缩后的摘要。"""
    text: str                           # 摘要文本
    original_count: int                 # 被压缩的原始条数
    compressed_at_day: int              # 压缩发生的天数
    compressed_at_slot: Slot            # 压缩发生的时段


# ═══════════════════════════════════════════════════
# Agent 记忆管理器
# ═══════════════════════════════════════════════════

class MemoryStore:
    """管理单个 NPC 的记忆。

    职责：
    - 记录事件记忆
    - 维护关键记忆 Top-N
    - 管理情感印象
    - 触发溢出精简
    """

    def __init__(self, npc_id: str, memory: AgentMemory | None = None):
        self._memory = memory or AgentMemory(npc_id=npc_id)
        self._summaries: list[MemorySummary] = []

    # ── 查询 ──────────────────────────────────────

    @property
    def event_count(self) -> int:
        return len(self._memory.event_chain)

    @property
    def key_count(self) -> int:
        return len(self._memory.key_memories)

    @property
    def overflow_count(self) -> int:
        return self._memory.memory_overflow_count

    def recent_events(self, n: int = 10) -> list[MemoryEntry]:
        """获取最近 n 条事件记忆。"""
        return self._memory.event_chain[-n:]

    def top_key_memories(self, n: int = 5) -> list[MemoryEntry]:
        """获取最重要的 n 条关键记忆。"""
        return self._memory.key_memories[:n]

    def get_impression(self, npc_id: str) -> Impression | None:
        """获取对某 NPC 的印象。"""
        return self._memory.impressions.get(npc_id)

    def all_impressions(self) -> dict[str, Impression]:
        """获取所有印象。"""
        return dict(self._memory.impressions)

    # ── 事件记忆 ──────────────────────────────────

    def remember(
        self,
        day: int,
        slot: Slot,
        description: str,
        importance: int = 5,
        emotion: Emotion = Emotion.NEUTRAL,
        event_id: str = "",
    ) -> MemoryEntry:
        """记录一条事件记忆。

        自动判定：
        - 重要性 >= IMPORTANCE_THRESHOLD → 同时加入关键记忆
        - 事件链超过上限 → 触发溢出处理
        """
        entry = MemoryEntry(
            day=day,
            slot=slot,
            event_id=event_id,
            description=description,
            importance=importance,
            emotion=emotion,
        )

        # 加入事件链
        self._memory.event_chain.append(entry)

        # 高重要性 → 自动进入关键记忆
        if importance >= IMPORTANCE_THRESHOLD:
            self._add_key_memory(entry)

        # 溢出检查
        if len(self._memory.event_chain) > MAX_EVENT_CHAIN:
            self._compact_event_chain(day, slot)

        return entry

    def _add_key_memory(self, entry: MemoryEntry) -> None:
        """按重要性排序插入关键记忆列表。"""
        self._memory.key_memories.append(entry)
        self._memory.key_memories.sort(key=lambda m: m.importance, reverse=True)

        # 截断
        if len(self._memory.key_memories) > MAX_KEY_MEMORIES:
            self._memory.key_memories = self._memory.key_memories[:MAX_KEY_MEMORIES]

    # ── 溢出处理 ──────────────────────────────────

    def _compact_event_chain(self, day: int, slot: Slot) -> None:
        """精简事件链：保留最近 20 条 + 最重要 10 条，其余合并为摘要。"""
        chain = self._memory.event_chain

        # 按重要性排序，保留 Top 10 + 最近 20
        by_importance = sorted(chain, key=lambda m: m.importance, reverse=True)
        top_10 = by_importance[:10]
        recent_20 = chain[-20:]

        # 合并去重
        kept_ids = {id(e) for e in top_10} | {id(e) for e in recent_20}
        removed = [e for e in chain if id(e) not in kept_ids]

        # 构造摘要
        if removed:
            summary = MemorySummary(
                text=f"精简了 {len(removed)} 条记忆: "
                     + "; ".join(e.description[:20] for e in removed[:5])
                     + ("..." if len(removed) > 5 else ""),
                original_count=len(removed),
                compressed_at_day=day,
                compressed_at_slot=slot,
            )
            self._summaries.append(summary)

        # 重建事件链
        merged = {id(e): e for e in top_10 + recent_20}
        # 保持原有时间顺序
        self._memory.event_chain = [
            e for e in chain if id(e) in merged
        ]
        self._memory.memory_overflow_count += 1

    # ── 情感印象 ──────────────────────────────────

    def set_impression(self, npc_id: str, affinity: int = 50, trust: int = 50,
                       label: str = "") -> Impression:
        """设置或更新对某 NPC 的印象。"""
        impression = Impression(
            npc_id=npc_id,
            affinity=affinity,
            trust=trust,
            label=label,
        )
        self._memory.impressions[npc_id] = impression
        return impression

    def update_impression(
        self,
        npc_id: str,
        affinity_delta: int = 0,
        trust_delta: int = 0,
        label: str | None = None,
    ) -> Impression | None:
        """增量更新印象。NPC 不存在时创建默认印象。"""
        existing = self._memory.impressions.get(npc_id)
        if existing is None:
            # 首次印象
            affinity = max(0, min(100, 50 + affinity_delta))
            trust = max(0, min(100, 50 + trust_delta))
            return self.set_impression(npc_id, affinity, trust, label or "")

        existing.affinity = max(0, min(100, existing.affinity + affinity_delta))
        existing.trust = max(0, min(100, existing.trust + trust_delta))
        if label is not None:
            existing.label = label
        return existing

    # ── LLM 上下文 ────────────────────────────────

    def context_for_llm(self, max_events: int = 10) -> str:
        """生成给 LLM 的记忆上下文文本。

        包含：最近事件 + 关键人物印象 + 旧记忆摘要。
        """
        parts: list[str] = []

        # 最近事件
        recent = self.recent_events(max_events)
        if recent:
            parts.append("【最近经历】")
            for e in recent:
                parts.append(
                    f"  Day{e.day} {e.slot.value}: {e.description}"
                    f"（重要性{e.importance}，{e.emotion.value}）"
                )

        # 关键印象
        if self._memory.impressions:
            parts.append("【对他人印象】")
            for npc_id, imp in self._memory.impressions.items():
                parts.append(
                    f"  {npc_id}: 好感{imp.affinity} 信任{imp.trust}"
                    + (f" ({imp.label})" if imp.label else "")
                )

        # 历史摘要
        if self._summaries:
            parts.append("【更早的回忆】")
            for s in self._summaries[-3:]:   # 最近 3 次压缩摘要
                parts.append(f"  Day{s.compressed_at_day}: {s.text}")

        return "\n".join(parts) if parts else "（尚无记忆）"

    # ── 序列化 ────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "memory": self._memory.model_dump(),
            "summaries": [
                {
                    "text": s.text,
                    "original_count": s.original_count,
                    "compressed_at_day": s.compressed_at_day,
                    "compressed_at_slot": s.compressed_at_slot.value,
                }
                for s in self._summaries
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryStore":
        store = cls(
            npc_id=data["memory"]["npc_id"],
            memory=AgentMemory(**data["memory"]),
        )
        for s in data.get("summaries", []):
            store._summaries.append(MemorySummary(
                text=s["text"],
                original_count=s["original_count"],
                compressed_at_day=s["compressed_at_day"],
                compressed_at_slot=Slot(s["compressed_at_slot"]),
            ))
        return store
