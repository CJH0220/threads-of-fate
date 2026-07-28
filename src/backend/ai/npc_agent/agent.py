"""NPC Agent —— 组装静态层 + 动态层 + 记忆层 + LLM 客户端。

每个 NpcAgent 实例对应一个 NPC，拥有：
- 独立的静态属性（不可变）
- 独立的动态状态（每时段变化）
- 独立的记忆存储
- 独立的 LLM 对话历史

S 级 Agent 使用完整 LLM 交互；A/B 级可降级为规则决策。
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from src.backend.models.npc import (
    AgentTier,
    Emotion,
    Location,
    NpcSnapshot,
    NpcStatic,
    Slot,
)
from src.backend.ai.llm_client.interface import BaseLLMClient, StubLLMClient
from src.backend.ai.npc_agent.dynamic import DynamicState, create_initial_dynamic
from src.backend.ai.npc_agent.memory import MemoryStore
from src.backend.ai.npc_agent.retrieval import RetrievalPipeline, retrieval_result_to_context
from src.backend.ai.npc_agent.semantic import SemanticStore
from src.backend.ai.npc_agent.templates import build_decision_prompt, build_system_prompt


# ═══════════════════════════════════════════════════
# NpcAgent
# ═══════════════════════════════════════════════════

class NpcAgent:
    """单个 NPC 的 AI 代理。

    用法:
        static = demo_lin_chaoyin()
        agent = NpcAgent(static)
        agent.set_location(Location.SCHOOL)
        action = await agent.think(day=1, slot=Slot.MORNING)
    """

    def __init__(
        self,
        static: NpcStatic,
        dynamic: Optional[DynamicState] = None,
        memory: Optional[MemoryStore] = None,
        semantic: Optional[SemanticStore] = None,
        llm: Optional[BaseLLMClient] = None,
        bond_manager=None,
        name_map: dict = None,
    ):
        self.static = static
        self.dynamic = dynamic or create_initial_dynamic()
        self.memory = memory or MemoryStore(static.id)
        self.semantic = semantic or SemanticStore(static.id)
        self.llm = llm or StubLLMClient()
        self._bond_manager = bond_manager
        self._name_map = name_map or {}
        self._pipeline = RetrievalPipeline()

        # 对话历史（每次 think 时重建 system prompt）
        self._chat_history: List[Dict] = []
        self._current_conversation: List[Dict] = []

    # ── 属性查询 ──────────────────────────────────

    @property
    def npc_id(self) -> str:
        return self.static.id

    @property
    def name(self) -> str:
        return self.static.name

    @property
    def tier(self) -> AgentTier:
        return self.static.tier

    @property
    def location(self) -> Location:
        return self.dynamic.current.location

    @property
    def emotion(self) -> Emotion:
        return self.dynamic.current.emotion

    # ── 核心方法 ──────────────────────────────────

    async def think(self, day: int, slot: Slot) -> str:
        """NPC 行为决策。

        返回 NPC 在当前时段想做的行动描述。

        流程：
        1. 构建 system_prompt（含性格 + 记忆 + 当前状态）
        2. 调用 LLM（如不可用，走规则兜底）
        3. 更新动态状态和记忆
        """
        # 1. 当前状态 + 三层记忆检索
        state = self.dynamic.current
        retrieval_result = self._pipeline.retrieve(
            memory=self.memory,
            semantic=self.semantic,
            dynamic=state,
            day=day,
            slot=slot,
        )
        memory_context = retrieval_result_to_context(retrieval_result)

        # 2. 构建 prompt
        dream_context = self._build_dream_context()
        system_prompt = build_system_prompt(
            static=self.static,
            memory_context=memory_context,
            location=state.location.value,
            emotion=state.emotion.value,
            energy=state.energy,
            happiness=state.happiness,
            bond_manager=self._bond_manager,
            name_map=self._name_map,
            dream_context=dream_context,
        )
        decision_prompt = build_decision_prompt(
            static=self.static,
            memory_context=memory_context,
            location=state.location.value,
            emotion=state.emotion.value,
            energy=state.energy,
            happiness=state.happiness,
            bond_manager=self._bond_manager,
            name_map=self._name_map,
            dream_context=dream_context,
        )

        # 3. 调用 LLM（可能降级返回 None）
        messages = [
            {"role": "system", "content": decision_prompt},
        ]
        action = await self.llm.chat(messages)

        # 4. LLM 不可用 → 规则兜底
        if not action:
            action = self._default_action(day, slot)
        else:
            action = action.strip()

        return action

    async def respond(
        self, context: str, speaker_name: str = "某人",
        current_day: int = 1,
    ) -> str:
        """NPC 对话回应。

        Args:
            context: 对话上下文（刚才说了什么）
            speaker_name: 说话者名字
            current_day: 当前天数（用于记忆检索）
        """
        state = self.dynamic.current
        retrieval_result = self._pipeline.retrieve(
            memory=self.memory,
            semantic=self.semantic,
            dynamic=state,
            day=current_day,
            slot=Slot.MORNING,  # 对话默认为早晨时段
        )
        memory_context = retrieval_result_to_context(retrieval_result)

        system_prompt = build_system_prompt(
            static=self.static,
            memory_context=memory_context,
            location=state.location.value,
            emotion=state.emotion.value,
            energy=state.energy,
            happiness=state.happiness,
            bond_manager=self._bond_manager,
            name_map=self._name_map,
            dream_context=self._build_dream_context(),
        )

        user_message = f"{speaker_name}对你说：{context}\n\n请以{self.name}的身份回应。记住你的性格和当前情绪。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        response = await self.llm.chat(messages)
        if not response:
            response = self._default_response(context)
        return response.strip()

    def _default_action(self, day: int, slot: Slot) -> str:
        """规则兜底：按日常日程表返回默认行动。"""
        state = self.dynamic.current
        loc = state.location.value

        defaults = {
            Slot.MORNING: f"在{loc}开始新的一天。",
            Slot.NOON: f"在{loc}度过午后时光。",
            Slot.NIGHT: f"在{loc}休息，为明天做准备。",
        }
        return defaults.get(slot, f"在{loc}待着。")

    def _default_response(self, context: str) -> str:
        """规则兜底：默认对话回应。"""
        return "……（沉默）" if self.static.personality.sensibility < 0.4 else "嗯。"

    # ── JSON 解析 ──────────────────────────────────

    def _parse_decision_json(self, raw: str) -> Optional[dict]:
        """尝试从 LLM 原始输出中提取 JSON。兼容纯 JSON / markdown 代码块 / 前后带文字。"""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        md_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', raw)
        if md_match:
            try:
                return json.loads(md_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        brace_match = re.search(r'\{[\s\S]*\}', raw)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    # ── 场景补全 ──────────────────────────────────

    async def fill_scene(
        self, skeleton: dict, day: int, slot: Slot,
        player_context: dict = None,
    ) -> dict:
        """根据对话骨架补全自己的台词（v2：支持感知玩家介入）。

        Args:
            skeleton: 编剧产出的对话骨架 {goal, tone, line_steps: [{step_id, actor, ...}]}
            day: 当前天数
            slot: 当前时段
            player_context: v2 新增——玩家在时段预告窗的介入结果
                {"blessed_event_ids": [...], "blessed_targets": [...], "extra_investment_ids": [...]}

        Returns:
            {"actor": npc_id, "lines": [{"step_ref": "b1", "type": "dialogue", "text": "..."}]}
            失败时返回兜底模板
        """
        from src.backend.ai.npc_agent.templates import build_fill_scene_prompt

        state = self.dynamic.current

        retrieval_result = self._pipeline.retrieve(
            memory=self.memory,
            semantic=self.semantic,
            dynamic=state,
            day=day,
            slot=slot,
        )
        memory_context = retrieval_result_to_context(retrieval_result)

        # Build dream context (v2)
        dream_context = self._build_dream_context()

        # Determine if this NPC perceives blessing (v2)
        blessed_event_ids = (player_context or {}).get("blessed_event_ids", [])
        blessed_targets = (player_context or {}).get("blessed_targets", [])
        perceives_blessing = (
            self.npc_id in blessed_targets or
            any(eid for eid in blessed_event_ids if self.npc_id in str(eid))
        )
        blessing_perceived = any(
            self.npc_id in (player_context or {}).get("participants_map", {}).get(eid, [])
            for eid in blessed_event_ids
        ) or self.npc_id in blessed_targets

        prompt = build_fill_scene_prompt(
            static=self.static,
            skeleton=skeleton,
            location=state.location.value,
            emotion=state.emotion.value,
            energy=state.energy,
            happiness=state.happiness,
            memory_context=memory_context,
            bond_manager=self._bond_manager,
            name_map=self._name_map,
            dream_context=dream_context,
            perceives_blessing=blessing_perceived,
        )

        messages = [{"role": "system", "content": prompt}]
        reply = await self.llm.chat(messages, max_tokens=512, temperature=0.8)

        if reply:
            parsed = self._parse_decision_json(reply.strip())
            if parsed and "lines" in parsed:
                result = {"actor": self.npc_id, "lines": parsed["lines"]}
                if blessing_perceived:
                    result["perceived_blessing"] = True
                return result

        # 兜底：一条沉默 action（v2: 仍携带赐福感知标志）
        result = {
            "actor": self.npc_id,
            "lines": [
                {"step_ref": "fallback", "type": "action",
                 "text": f"{self.name}沉默着。"}
            ],
        }
        if blessing_perceived:
            result["perceived_blessing"] = True
        return result

    # ── 记忆 ──────────────────────────────────────

    def remember(self, day: int, slot: Slot, description: str,
                 importance: int = 5, emotion: Optional[Emotion] = None,
                 source: str = "event", event_id: str = "",
                 participants: list = None,
                 dream_incense_snapshot: int = 0, dream_text: str = "") -> None:
        """记录一条记忆。v2 扩展：支持 source 分类与托梦字段。"""
        self.memory.remember(
            day=day,
            slot=slot,
            description=description,
            importance=importance,
            emotion=emotion or self.dynamic.current.emotion,
            event_id=event_id,
            participants=participants or [],
            source=source,
            dream_incense_snapshot=dream_incense_snapshot,
            dream_text=dream_text,
        )

    def receive_dream(self, dream_text: str, incense_snapshot: int,
                      day: int, slot: Slot) -> None:
        """接收玩家托梦，写入一条 source=dream 的记忆。

        NPC 在后续 think/fill_scene 中通过 _build_dream_context 读取此记忆，
        由 prompt 自判分量。香火快照固定记录，事后不追溯。
        """
        importance = 5  # 默认重要度，NPC 可在读入时自评上调
        self.memory.remember(
            day=day,
            slot=slot,
            description=f"（梦中）土地公托梦：{dream_text}",
            importance=importance,
            emotion=Emotion.EXCITED,
            event_id="",
            participants=[],
            source="dream",
            dream_incense_snapshot=incense_snapshot,
            dream_text=dream_text,
        )
        print(f"[NpcAgent] {self.name} receive_dream: "
              f"incense={incense_snapshot}, dream={dream_text[:40]}...")

    def _build_dream_context(self) -> str:
        """构建托梦上下文文本（供 fill_scene / think 的 prompt 使用）。

        读取 source=dream 的近期记忆，附加香火分段语义锚点说明。
        """
        dream_mems = self.memory.by_source("dream")
        if not dream_mems:
            return ""

        # 取最近一条托梦
        latest = dream_mems[-1]
        incense = latest.dream_incense_snapshot
        text = latest.dream_text or latest.description

        # 香火分段语义锚点（§8.3）
        if incense <= 40:
            weight = "几乎被遗忘——梦像一次偶发的杂念"
        elif incense <= 100:
            weight = "一份心里挥之不去的暗示"
        elif incense <= 150:
            weight = "仿佛有人在耳边低语的确切感觉"
        else:
            weight = "神谕般的确信"

        return (
            f"【神明的托梦】\n"
            f"昨夜，你在梦中感知到土地公的低语：\"{text}\"\n"
            f"托梦时镇上香火为 {incense}，这份梦对你而言：{weight}。\n"
            f"请将此反映到你的动机、情绪、行动和台词中。"
        )

    # ── 状态更新 ──────────────────────────────────

    def set_location(self, location: Location, reason: str = "") -> None:
        self.dynamic.set_location(self.npc_id, location, reason)

    def set_happiness(self, delta: int, reason: str = "") -> None:
        self.dynamic.set_happiness(self.npc_id, delta, reason)

    def set_emotion(self, emotion: Emotion, reason: str = "") -> None:
        self.dynamic.set_emotion(self.npc_id, emotion, reason)

    # ── 快照 ──────────────────────────────────────

    def snapshot(self) -> NpcSnapshot:
        """生成当前快照（给前端）。"""
        return NpcSnapshot(
            static=self.static,
            dynamic=self.dynamic.current,
            memory_summary={
                "event_count": self.memory.event_count,
                "key_count": self.memory.key_count,
                "semantic_count": self.semantic.entry_count,
                "recent_events": [
                    {"day": e.day, "description": e.description[:30]}
                    for e in self.memory.recent_events(5)
                ],
                "top_impressions": {
                    npc_id: {
                        "affinity": imp.affinity,
                        "trust": imp.trust,
                        "label": imp.label,
                    }
                    for npc_id, imp in list(self.memory.all_impressions().items())[:5]
                },
            },
        )

    def to_dict(self) -> dict:
        """序列化（存档用）。"""
        return {
            "static_id": self.static.id,
            "dynamic": self.dynamic.to_dict(),
            "memory": self.memory.to_dict(),
            "semantic": self.semantic.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict, static: NpcStatic) -> "NpcAgent":
        """从存档反序列化。"""
        agent = cls(
            static=static,
            dynamic=DynamicState.from_dict(data["dynamic"]),
            memory=MemoryStore.from_dict(data["memory"]),
            semantic=(
                SemanticStore.from_dict(data["semantic"])
                if "semantic" in data else None
            ),
        )
        return agent
