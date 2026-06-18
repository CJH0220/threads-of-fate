"""三层记忆检索流水线。

每次 agent.think() / agent.respond() 调用时，按顺序执行：
  ① 工作记忆（临时拼装）
  ② 情景记忆（双库检索 + 艾宾浩斯公式）
  ③ 语义记忆（向量 + 图谱并行检索）

将所有结果拼接为 system_prompt 的记忆段落。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from src.backend.models.npc import (
    RetrievalContext,
    RetrievalResult,
    ScoredEntry,
    Slot,
)
from src.backend.ai.npc_agent.memory import EpisodicHit, MemoryStore
from src.backend.ai.npc_agent.semantic import SemanticStore


# ═══════════════════════════════════════════════════
# RetrievalPipeline
# ═══════════════════════════════════════════════════

class RetrievalPipeline:
    """三层记忆检索流水线。

    用法:
        pipeline = RetrievalPipeline()
        result = pipeline.retrieve(
            memory=agent.memory,
            semantic=agent.semantic,
            dynamic=agent.dynamic.current,
            day=15, slot=Slot.NOON,
        )
    """

    def retrieve(
        self,
        memory: MemoryStore,
        semantic: Optional[SemanticStore],
        dynamic,           # NpcDynamic
        day: int,
        slot: Slot,
        query_embedding: Optional[List[float]] = None,
        participant_filter: Optional[str] = None,
    ) -> RetrievalResult:
        """执行三层检索。

        Args:
            memory: 情景记忆存储
            semantic: 语义记忆存储（可为 None）
            dynamic: 当前动态状态
            day: 当前天数
            slot: 当前时段
            query_embedding: 查询向量（来自 embedding 模型，可选）
            participant_filter: 参与者筛选（可选）

        Returns:
            RetrievalResult（三层结果汇总）
        """
        # ── ① 工作记忆 ──────────────────────────────
        working = self._assemble_working_memory(
            dynamic=dynamic,
            memory=memory,
            day=day,
            slot=slot,
        )

        # ── ② 情景记忆 ──────────────────────────────
        query_text = self._build_query_text(dynamic)
        location_filter = dynamic.location.value if dynamic.location else None

        episodic_hits = memory.retrieve(
            current_day=day,
            query_text=query_text,
            location_filter=location_filter,
            participant_filter=participant_filter,
        )
        episodic_entries = [
            ScoredEntry(
                memory_id=h.memory_id,
                description=h.entry.description,
                vector_score=h.vector_score,
                graph_score=0.0,   # 情景记忆无图谱
                final_score=h.final_score,
                source="episodic",
            )
            for h in episodic_hits
        ]

        # ── ③ 语义记忆 ──────────────────────────────
        semantic_entries: List[ScoredEntry] = []
        if semantic is not None and semantic.entry_count > 0:
            context_entities = self._extract_context_entities(
                dynamic=dynamic, memory=memory, day=day
            )
            context = RetrievalContext(
                location=dynamic.location.value if dynamic.location else "",
                emotion=dynamic.emotion.value if dynamic.emotion else "",
                current_goal=dynamic.current_goal or "",
                day=day,
                slot=slot.value,
                context_entities=context_entities,
                query_text=query_text,
                query_embedding=query_embedding,
            )
            semantic_entries = semantic.retrieve(
                context=context,
                query_embedding=query_embedding,
            )

        return RetrievalResult(
            working_memory=working,
            episodic_entries=episodic_entries,
            semantic_entries=semantic_entries,
        )

    # ── 工作记忆组装 ──────────────────────────────

    def _assemble_working_memory(
        self,
        dynamic,
        memory: MemoryStore,
        day: int,
        slot: Slot,
    ) -> dict:
        """从各层临时拼装工作记忆。"""
        return {
            "location": dynamic.location.value if dynamic.location else "",
            "emotion": dynamic.emotion.value if dynamic.emotion else "",
            "current_goal": dynamic.current_goal or "",
            "current_time": f"Day {day} {slot.value}",
            "today_events": [
                e.description
                for e in memory.recent_events(20)
                if e.day == day
            ],
        }

    # ── 辅助 ──────────────────────────────────────

    @staticmethod
    def _build_query_text(dynamic) -> str:
        """从动态状态构建查询文本。"""
        parts = [
            dynamic.location.value if dynamic.location else "",
            dynamic.emotion.value if dynamic.emotion else "",
            dynamic.current_goal or "",
        ]
        return " ".join(filter(None, parts))

    @staticmethod
    def _extract_context_entities(
        dynamic,
        memory: MemoryStore,
        day: int,
    ) -> List[str]:
        """从当前情境中提取实体（规则匹配）。"""
        entities: List[str] = []

        # 地点名
        if dynamic.location:
            entities.append(dynamic.location.value)

        # 当前目标中的关键词
        if dynamic.current_goal:
            entities.append(dynamic.current_goal[:10])

        # 最近事件中的 NPC 参与者
        for entry in memory.recent_events(5):
            for p in entry.participants:
                if p not in entities:
                    entities.append(p)

        return entities


# ═══════════════════════════════════════════════════
# 便捷函数：检索结果 → LLM 上下文文本
# ═══════════════════════════════════════════════════

def retrieval_result_to_context(result: RetrievalResult) -> str:
    """将检索结果转为 LLM system_prompt 中的记忆段落。"""
    parts: List[str] = []

    # 工作记忆
    wm = result.working_memory
    parts.append(
        f"【当前状态】你身处{wm.get('location', '未知')}，"
        f"情绪{wm.get('emotion', '平静')}。"
        f"当前目标：{wm.get('current_goal', '无特定目标')}。"
        f"时间：{wm.get('current_time', '')}。"
    )

    # 情景记忆
    if result.episodic_entries:
        parts.append("【最近经历】")
        for e in result.episodic_entries[:10]:
            parts.append(f"  {e.description}")

    # 语义记忆
    if result.semantic_entries:
        parts.append("【你学到的】")
        for e in result.semantic_entries[:8]:
            parts.append(f"  — {e.description}")

    return "\n".join(parts)
