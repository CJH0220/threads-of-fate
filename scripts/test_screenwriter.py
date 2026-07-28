"""测试编剧Agent —— 模拟时间推进，观察编剧编排 + 事件触发 + NPC决策。

用法：
    cd H:\Game\threads-of-fate
    python scripts/test_screenwriter.py          # 真实LLM（如果有的话）
    python scripts/test_screenwriter.py mock     # 模拟LLM响应

如果 LLM 不可用，编剧Agent 自动回退到 CSV 事件匹配（兼容模式）。
"""

import sys
import asyncio
import os
import json
import random

# 确保从项目根目录导入（无论从哪个目录运行此脚本）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from src.backend.server.state import init_session
from src.backend.engine.event import load_events, match_events, execute_events
from src.backend.engine.story import load_event_templates, load_story_outline
from src.backend.ai.screenwriter import screenwriter_think
from src.backend.ai.llm_client.interface import BaseLLMClient
from src.backend.models.npc import Slot

USE_MOCK = len(sys.argv) > 1 and sys.argv[1] == "mock"

# ── Mock LLM（模拟编剧Agent 的 JSON 响应）──

class MockScreenwriterLLM(BaseLLMClient):
    """返回预设 JSON 的模拟 LLM，用于测试编剧Agent 的完整流程。"""

    def __init__(self):
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        self.call_count += 1
        # 打印 user prompt 摘要
        user_msg = ""
        for m in messages:
            if m["role"] == "user":
                user_msg = m["content"]
                break
        print(f"\n  [MockLLM call #{self.call_count}] user_prompt 长度: {len(user_msg)} 字符")
        # 打印 prompt 前 500 字符
        print(f"  {'─'*60}")
        print(user_msg[:500])
        if len(user_msg) > 500:
            print(f"  ... (共 {len(user_msg)} 字符)")
        print(f"  {'─'*60}")

        # 根据时段生成不同的即兴事件（模拟编剧Agent的创作能力）
        slot_hint = ""
        for m in messages:
            if m["role"] == "user":
                # 从 user prompt 中提取当前时段
                if "noon" in m["content"].lower():
                    slot_hint = "noon"
                elif "night" in m["content"].lower():
                    slot_hint = "night"
                elif "morning" in m["content"].lower():
                    slot_hint = "morning"
                break

        spontaneous = []
        if slot_hint == "morning":
            spontaneous = [
                {"template_id": "solitude_reflection", "participants": ["lin_chaoyin"],
                 "location": "beach", "detail": "看着晨光洒在海面上，她深吸一口气，觉得今天应该是个好日子",
                 "outcome": {"happiness_delta": {"lin_chaoyin": 1}}, "reasoning": "早晨适合独处反思"},
                {"template_id": "chance_encounter", "participants": ["chen_yuanzhou", "su_wan"],
                 "location": "shopping_street", "detail": "母子两人在市场偶然相遇，苏婉塞给远舟一包他爱吃的鱼干",
                 "outcome": {"bond_delta": {"bond_chen_yuanzhou_su_wan": 1}}, "reasoning": "温暖的家庭偶遇"}
            ]
        elif slot_hint == "noon":
            spontaneous = [
                {"template_id": "idle_chat", "participants": ["lin_chaoyin", "chen_yuanzhou", "ye_keke"],
                 "location": "cafe", "detail": "聊起了最近岛上的流言——据说港口半夜有陌生船进出",
                 "outcome": {}, "reasoning": "午后的咖啡店信息流动"}
            ]
        elif slot_hint == "night":
            spontaneous = [
                {"template_id": "discovery", "participants": ["chen_haisheng"],
                 "location": "port", "detail": "发现何老三正在卸一批从未见过的木箱，箱子上没有任何标记",
                 "outcome": {}, "reasoning": "夜晚港口的悬疑线索"},
                {"template_id": "solitude_reflection", "participants": ["lin_chaoyin"],
                 "location": "temple", "detail": "月光下独自坐在庙前，感应到一阵奇异的灵力波动",
                 "outcome": {"happiness_delta": {"lin_chaoyin": -1}}, "reasoning": "夜晚的灵力感应让她不安"}
            ]

        return json.dumps({
            "narrator_insight": "小镇的日常在平静中暗藏涟漪。",
            "interventions": [
                {"npc_id": "lin_chaoyin", "decision": "pass", "reasoning": "行为与大纲一致"},
                {"npc_id": "chen_yuanzhou", "decision": "pass", "reasoning": "行为与大纲一致"},
            ],
            "triggered_beats": [],  # 模拟模式下不自动触发节拍，让 CSV 补充
            "spontaneous_events": spontaneous,
        }, ensure_ascii=False)

    async def chat_stream(self, messages, **kwargs):
        text = await self.chat(messages, **kwargs)
        yield text or ""

    async def is_available(self):
        return True


# ── 打印函数 ──

def print_header(title: str):
    print(f"\n{'█'*70}")
    print(f"  {title}")
    print(f"{'█'*70}")


def print_status(session):
    """紧凑打印当前状态。"""
    print(f"  Day{session.time.day:>2} {session.time.slot.value:7s} Week{session.time.week} | "
          f"香火={session.resource.incense:>3} 神力={session.resource.divine_power:>2}/{session.resource.divine_power_max:<2} "
          f"阳德={getattr(session.resource, 'yang_de', 0):>3} 阴德={getattr(session.resource, 'yin_de', 0):>3}")
    print(f"  StoryState: {len(session.story.triggered_beats)} beats triggered, "
          f"{len(session.story.arc_progress)} arcs tracked")
    if session.story.arc_progress:
        for aid, pct in session.story.arc_progress.items():
            bar = "█" * int(pct * 10) + "░" * (10 - int(pct * 10))
            print(f"    {aid}: {bar} {pct*100:.0f}%")


def print_npc_snapshot(session, npc_id: str):
    """打印单个 NPC 快照。"""
    ag = session.agents.get(npc_id)
    if not ag:
        return
    d = ag.dynamic.current
    m = ag.memory
    print(f"  {ag.name:6s} | {d.location.value:16s} | {d.emotion.value:8s} | "
          f"幸福{d.happiness:3d} 精力{d.energy:3d} | 记忆{m.event_count:2d}条")


def print_events(matched, settlement):
    """打印匹配到的事件和结算结果。"""
    if not matched:
        print("  [事件] 无")
        return
    for (evt, _outcome), r in zip(matched, settlement):
        risk = getattr(evt, "risk_level", "?")
        print(f"  [事件] [{evt.event_type}] {evt.name} (risk={risk})")
        print(f"         id={evt.id} → {r.outcome_name}")
        if evt.participants:
            print(f"         参与: {evt.participants}")
        if r.resource_changes:
            print(f"         资源: {r.resource_changes}")
        if r.bond_changes:
            print(f"         缘线: {r.bond_changes}")


# ── 单时段推进 ──

def advance_one_slot(session, outline, events, screenwriter_llm, templates=None):
    """推进一个时段，使用新的编剧Agent流程。"""
    if not session.time.can_advance():
        print(f"\n[终局] 已到达第60天！")
        return False

    result = session.time.advance()
    print_header(f"Day{result.day} {result.slot.value}  Week{result.week}  {result.phase_name}")

    if result.is_new_day:
        session.resource.apply_daily()

    # ── Step 1: NPC 思考（移到事件之前）──
    print("\n  [NPC 思考]")
    npc_intentions = []

    async def _think_all():
        tasks = []
        for aid in session.agents.npc_ids:
            ag = session.agents.get(aid)
            if ag and ag.static.tier.value in ("S", "A"):
                tasks.append(ag.think(result.day, result.slot))
        return await asyncio.gather(*tasks, return_exceptions=True)

    s_a_ids = [aid for aid in session.agents.npc_ids
               if session.agents.get(aid)
               and session.agents.get(aid).static.tier.value in ("S", "A")]
    actions = asyncio.run(_think_all())

    for aid, action in zip(s_a_ids, actions):
        ag = session.agents.get(aid)
        name = ag.name if ag else "?"
        loc = ag.dynamic.current.location.value if ag else "?"
        if isinstance(action, Exception):
            print(f"    {name} ({aid}): ERROR - {action}")
        else:
            print(f"    {name} ({aid}): {action or '(无)'}")
            npc_intentions.append((aid, name, action or "", loc))

    # ── Step 2: 编剧Agent 编排 ──
    print(f"\n  [编剧Agent] LLM={'Mock' if USE_MOCK else '真实'} "
          f"outline={'✓' if outline else '✗'}")

    sw_result = asyncio.run(
        screenwriter_think(
            session=session,
            story_outline=outline,
            day=result.day,
            slot=result.slot,
            week=result.week,
            phase_name=result.phase_name,
            npc_intentions=npc_intentions,
            llm=screenwriter_llm,
            templates=templates,
        )
    )

    beat_events = sw_result.events
    if sw_result.ok:
        # 区分节拍事件和即兴事件
        beat_only = [e for e in beat_events if not e[0].id.startswith("spontaneous_")]
        spon_only = [e for e in beat_events if e[0].id.startswith("spontaneous_")]
        print(f"    编剧编排成功 ✓  (节拍{len(beat_only)}个 + 即兴{len(spon_only)}个)")
        if spon_only:
            for t, o in spon_only:
                desc = (t.description or "")[:60]
                print(f"      🎭 {t.name}: {desc}")
        if beat_only:
            for t, o in beat_only:
                print(f"      ◆ {t.name} ({t.id}) outcome={o.id}")
    else:
        print(f"    编剧不可用，回退 CSV 匹配")

    # ── Step 3: CSV 事件补充 ──
    locs = {}
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag:
            locs[aid] = ag.dynamic.current.location.value
    locs.update({
        "heaven_messenger": "temple", "tudi_gong": "temple",
        "underworld_messenger": "temple", "town_representative": "plaza",
    })

    csv_matched = match_events(events, day=result.day, slot=result.slot,
                               week=result.week, participant_locations=locs)

    max_total = outline.global_constraints.max_events_per_slot if outline else 3
    beat_event_ids = {e[0].id for e in beat_events}
    if outline:
        for e, _ in beat_events:
            for beat in outline.all_beats():
                if beat.id == e.id and beat.event_id:
                    beat_event_ids.add(beat.event_id)
    all_matched = list(beat_events)

    for csv_pair in csv_matched:
        if len(all_matched) >= max_total:
            break
        if csv_pair[0].id not in beat_event_ids:
            all_matched.append(csv_pair)

    print(f"\n  [事件匹配] 编剧{len(beat_events)}个 + CSV{len(csv_matched)}个 "
          f"→ 合并{len(all_matched)}个 (上限{max_total})")

    # ── Step 4: 执行事件 ──
    if all_matched:
        settlement = execute_events(all_matched, session.resource, session.agents,
                                    day=result.day, slot=result.slot)
        print_events(all_matched, settlement)

        # 应用缘线和业线
        for (_e, _o), r in zip(all_matched, settlement):
            if r.bond_changes:
                parts = [f"bond_{k}:{v:+d}" for k, v in r.bond_changes.items()]
                session.bonds.apply_delta(";".join(parts))
            if r.karma_changes:
                parts = [f"{k}:{v:+d}" for k, v in r.karma_changes.items()]
                session.karma.apply_delta(";".join(parts))
    else:
        print("  [事件] 无")

    # ── Step 5: B/C 级 NPC 简单行动 ──
    print(f"\n  [B/C级NPC]")
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag and ag.static.tier.value in ("B", "C"):
            action = ag._default_action(result.day, result.slot)
            print(f"    {ag.name} ({aid}): {action}")

    return True


# ═══════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════

def main():
    print_header("编剧Agent 测试")
    print(f"  模式: {'Mock LLM (模拟)' if USE_MOCK else '真实 LLM'}")
    print(f"  Python: {sys.version}")

    # 初始化
    session = init_session()
    events = load_events()
    outline = load_story_outline()
    templates = load_event_templates()

    # 编剧Agent的 LLM（独立于 NPC agent 的 LLM）
    if USE_MOCK:
        screenwriter_llm = MockScreenwriterLLM()
    else:
        # 使用真实 LLM（第一个 S-tier agent 的 LLM 作为编剧 LLM）
        screenwriter_llm = None
        for aid in session.agents.npc_ids:
            ag = session.agents.get(aid)
            if ag and ag.static.tier.value == "S":
                screenwriter_llm = ag.llm
                break
        if screenwriter_llm is None:
            print("  ⚠ 无 S-tier agent，编剧Agent 将回退到 CSV 匹配")

    print(f"\n  Outline: {len(outline.arcs)} arcs, {len(outline.all_beats())} beats, "
          f"{len(outline.tone_rules)} tone rules")
    print(f"  Events:  {len(events)} CSV events loaded")
    print(f"  NPCs:    {session.agents.count} agents")

    # 初始状态
    print_header("初始状态")
    print_status(session)
    print(f"\n  活跃 NPC (S/A 级):")
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag and ag.static.tier.value in ("S", "A"):
            print_npc_snapshot(session, aid)

    # 推进 N 个时段
    slots_to_advance = 6  # Morning→Noon→Night→Day2 Morning→Noon→Night
    print(f"\n\n{'═'*70}")
    print(f"  模拟推进 {slots_to_advance} 个时段")
    print(f"{'═'*70}")

    for i in range(slots_to_advance):
        if not advance_one_slot(session, outline, events, screenwriter_llm, templates):
            break
        print_status(session)

    # 最终状态
    print_header("最终状态")
    print_status(session)
    print(f"\n  已触发节拍 ({len(session.story.triggered_beats)} 个):")
    for bid, tb in session.story.triggered_beats.items():
        print(f"    - {bid}: Day{tb.triggered_day} {tb.triggered_slot} → {tb.selected_outcome_id}")

    if USE_MOCK:
        print(f"\n  MockLLM 共调用 {llm.call_count} 次")


if __name__ == "__main__":
    main()
