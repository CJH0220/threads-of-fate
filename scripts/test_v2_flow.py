"""v2 架构端到端集成测试 —— 模拟完整时段推进 + 玩家介入流程。

覆盖 v2 关键链路：
  1. 时段推进 → NPC 思考 → 编剧编排（dramatic_score + slot_summary）
  2. 时段预告窗模拟 → 玩家赐福决策 → PlayerContext
  3. 冲突分分流（≥6 完整管线 / 3-5 轻量 / ≤2 只写记忆）
  4. 夜晚托梦（香火快照 + receive_dream + _build_dream_context）
  5. 事件结算 → event_triggered（含 dramatic_score + player_impact_flags）

用法：
    cd H:\Game\threads-of-fate
    python scripts/test_v2_flow.py           # 默认推进 3 个时段
    python scripts/test_v2_flow.py 5         # 推进 5 个时段
    python scripts/test_v2_flow.py 10 dream  # 10 个时段 + 夜晚模拟托梦
"""

import sys
import asyncio
import os
import json
import random
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from src.backend.server.state import init_session
from src.backend.engine.event import load_events, match_events, execute_events
from src.backend.engine.story import load_event_templates, load_story_outline
from src.backend.ai.screenwriter import screenwriter_think, ScreenwriterResult
from src.backend.ai.dialogue_designer.pipeline import run_dialogue_pipeline
from src.backend.ai.llm_client.interface import BaseLLMClient
from src.backend.models.npc import Slot, Emotion

# ── 配置 ──────────────────────────────────────────

SLOTS_TO_ADVANCE = int(sys.argv[1]) if len(sys.argv) > 1 else 3
SIMULATE_DREAM = len(sys.argv) > 2 and sys.argv[2] == "dream"
random.seed(42)

# ── 颜色（Windows 兼容） ─────────────────────────

COLS = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
    "blue": "\033[94m", "magenta": "\033[95m", "cyan": "\033[96m",
}


def c(color: str, text: str) -> str:
    return f"{COLS.get(color, '')}{text}{COLS['reset']}"


# ── Mock LLM（v2 增强版） ─────────────────────────

class MockScreenwriterLLM(BaseLLMClient):
    """模拟编剧 Agent，产出带 dramatic_score + slot_summary 的 JSON。"""

    RESPONSES = [
        # Day1 Morning — 高冲突事件
        {
            "narrator_insight": "旧神将熄，小镇的日常在平静中暗藏不安。",
            "slot_summary": "今晨的归潮镇笼罩着一层薄雾。林潮音独自去了海边，似乎昨晚的梦让她心绪不宁。陈远舟的渔船迟迟未出——你若留意，港口方向隐约有争执声。此刻或许正是轻拨命运一二的时机。",
            "interventions": [
                {"npc_id": "lin_chaoyin", "decision": "pass", "reasoning": "行为与大纲一致"},
                {"npc_id": "chen_yuanzhou", "decision": "pass", "reasoning": "行为与大纲一致"},
            ],
            "triggered_beats": [],
            "spontaneous_events": [
                {
                    "template_id": "solitude_reflection", "participants": ["lin_chaoyin"],
                    "location": "beach", "detail": "看着晨光洒在海面上，她深吸一口气，觉得今天应该是个好日子。",
                    "dramatic_score": 2,
                    "outcome": {"happiness_delta": {"lin_chaoyin": 1}},
                    "reasoning": "早晨独处反思，环境氛围",
                },
                {
                    "template_id": "chance_encounter", "participants": ["chen_yuanzhou", "chen_haisheng"],
                    "location": "port", "detail": "海生质问远舟为什么还不出发，两人在码头发生激烈争执。",
                    "dramatic_score": 8,
                    "dialogue_skeleton": {
                        "goal": "两人为出海时机争执，暗含对未来的不同看法",
                        "tone": "紧张激烈",
                        "line_steps": [
                            {"actor": "chen_haisheng", "intent": "质问对方拖延", "must_convey": "你不出发我们都没饭吃", "must_avoid": "动手"},
                            {"actor": "chen_yuanzhou", "intent": "解释但不愿屈服", "must_convey": "有自己的理由暂不出海", "must_avoid": "提到神明或梦境"},
                        ],
                    },
                    "outcome": {},
                    "reasoning": "关系紧张，海生情绪被压力推高，两人正面冲突",
                },
            ],
        },
        # Day1 Noon — 日常互动
        {
            "narrator_insight": "午后的咖啡店成为信息流动的枢纽。",
            "slot_summary": "午后的咖啡店里，几个年轻人聚在一起窃窃私语。你隐约听到他们在谈论港口夜间的异动——似乎有人看见了不该看见的东西。气氛轻松，但话题不轻。",
            "interventions": [
                {"npc_id": "lin_chaoyin", "decision": "pass", "reasoning": "自然社交"},
            ],
            "triggered_beats": [],
            "spontaneous_events": [
                {
                    "template_id": "idle_chat", "participants": ["lin_chaoyin", "chen_yuanzhou"],
                    "location": "cafe", "detail": "聊起了最近岛上的流言——据说港口半夜有陌生船进出，叶可可在一旁添油加醋。",
                    "dramatic_score": 4,
                    "outcome": {},
                    "reasoning": "轻松闲聊，信息传递",
                },
            ],
        },
        # Day1 Night — 悬疑氛围
        {
            "narrator_insight": "夜色下的港口藏着一丝不寻常。",
            "slot_summary": "夜幕降临后的港口比任何时候都安静。陈海生独自在码头徘徊，似乎在等什么人。何老三的身影在仓库间一闪而过。你若愿介入，此刻正是揭示秘密的良机。",
            "interventions": [
                {"npc_id": "chen_haisheng", "decision": "pass", "reasoning": "按大纲发展"},
            ],
            "triggered_beats": [],
            "spontaneous_events": [
                {
                    "template_id": "discovery", "participants": ["chen_haisheng"],
                    "location": "port", "detail": "发现何老三正在卸一批从未见过的木箱，上面没有任何标记。",
                    "dramatic_score": 7,
                    "dialogue_skeleton": {
                        "goal": "海生发现可疑货物，内心开始动摇",
                        "tone": "悬疑紧张",
                        "line_steps": [
                            {"actor": "chen_haisheng", "intent": "质问何老三", "must_convey": "你深夜在港口干什么", "must_avoid": "直接指控邪教"},
                        ],
                    },
                    "outcome": {},
                    "reasoning": "悬疑发现，可能触发邪教线",
                },
                {
                    "template_id": "solitude_reflection", "participants": ["lin_chaoyin"],
                    "location": "temple", "detail": "月光下独自坐在庙前，感应到一阵奇异的灵力波动。",
                    "dramatic_score": 3,
                    "outcome": {"happiness_delta": {"lin_chaoyin": -1}},
                    "reasoning": "夜晚的灵力感应",
                },
            ],
        },
        # Day2 Morning — 中等冲突
        {
            "narrator_insight": "新的一天，旧的裂痕。",
            "slot_summary": "第二天的晨光似乎没能驱散什么。林潮音在神社前遇到了慧圆——两人之间的空气比往常更冷。陈远舟的渔船依旧没有出港。你感觉到镇上有什么正在悄然改变。",
            "interventions": [
                {"npc_id": "lin_chaoyin", "decision": "pass", "reasoning": "自然发展"},
            ],
            "triggered_beats": [],
            "spontaneous_events": [
                {
                    "template_id": "minor_conflict", "participants": ["lin_chaoyin", "huiyuan"],
                    "location": "temple", "detail": "慧圆委婉地暗示潮音最近在神社待得太久，潮音回以沉默。",
                    "dramatic_score": 6,
                    "dialogue_skeleton": {
                        "goal": "慧圆试探潮音是否察觉寺庙财务问题",
                        "tone": "隐晦紧张",
                        "line_steps": [
                            {"actor": "huiyuan", "intent": "试探并警告", "must_convey": "暗示她少管闲事", "must_avoid": "直接威胁"},
                            {"actor": "lin_chaoyin", "intent": "沉默应对", "must_convey": "心里已有所察觉", "must_avoid": "当面揭穿"},
                        ],
                    },
                    "outcome": {},
                    "reasoning": "寺庙腐败线推进",
                },
            ],
        },
        # Day2 Noon — 日常
        {
            "narrator_insight": "日常在继续。",
            "slot_summary": "午后的归潮镇一切如常。人们各自忙碌，阳光洒在石板路上。看起来是个平静的午后，但你知道——平静之下总有暗流。",
            "interventions": [],
            "triggered_beats": [],
            "spontaneous_events": [
                {
                    "template_id": "chance_encounter", "participants": ["su_wan", "zhou_xingzhi"],
                    "location": "shopping_street", "detail": "苏婉在街上偶遇周行知，两人聊起孩子的学业。",
                    "dramatic_score": 3,
                    "outcome": {},
                    "reasoning": "日常偶遇，轻量互动",
                },
            ],
        },
        # Day2 Night — 氛围沉淀
        {
            "narrator_insight": "每个人都在自己的思绪里。",
            "slot_summary": "夜晚的归潮镇安静得让人不安。你能感觉到——每个人都在各自的角落里思考着什么。也许今夜适合托梦于某人，轻轻拨动命运的丝线。",
            "interventions": [],
            "triggered_beats": [],
            "spontaneous_events": [
                {
                    "template_id": "solitude_reflection", "participants": ["jiang_xueyi"],
                    "location": "inn", "detail": "在客栈房间里整理笔记，眉头紧锁。",
                    "dramatic_score": 1,
                    "outcome": {},
                    "reasoning": "侦探在整理线索，环境氛围",
                },
            ],
        },
    ]

    def __init__(self):
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        idx = self.call_count % len(self.RESPONSES)
        self.call_count += 1
        return json.dumps(self.RESPONSES[idx], ensure_ascii=False)

    async def chat_stream(self, messages, **kwargs):
        text = await self.chat(messages, **kwargs)
        yield text or ""

    async def is_available(self):
        return True


class MockNpcLLM(BaseLLMClient):
    """模拟 NPC LLM。think() 返回自然语言，fill_scene() 返回 JSON。"""

    NAMES = {
        "lin_chaoyin": "林潮音", "chen_yuanzhou": "陈远舟",
        "chen_haisheng": "陈海生", "huiyuan": "慧圆",
        "jiang_xueyi": "江雪仪",
    }

    async def chat(self, messages, **kwargs):
        content = ""
        for m in messages:
            content += m.get("content", "")

        # 判断是 think（行为决策）还是 fill_scene（台词补全）
        if "【完整剧本骨架】" in content or "骨架" in content:
            # fill_scene: 返回 JSON
            for nid, name in self.NAMES.items():
                if name in content:
                    return json.dumps({
                        "lines": [
                            {"step_ref": "s1", "type": "dialogue", "text": f"（{name}根据骨架意图说出台词）"},
                            {"step_ref": "s1", "type": "action", "text": f"{name}看了对方一眼。"},
                        ]
                    }, ensure_ascii=False)
            return json.dumps({"lines": [{"step_ref": "fallback", "type": "action", "text": "沉默着。"}]}, ensure_ascii=False)
        else:
            # think: 返回自然语言行动描述
            for nid, name in self.NAMES.items():
                if name in content:
                    actions = ["去海边散步，想一个人静静。", "到咖啡店找人聊聊天。",
                               "准备出门办事。", "留在原地思考着什么。"]
                    return actions[hash(name) % len(actions)]
            return "开始新的一天。"

    async def chat_stream(self, messages, **kwargs):
        text = await self.chat(messages, **kwargs)
        yield text or ""

    async def is_available(self):
        return True


# ── 打印函数 ──────────────────────────────────────

def sep(char="─", width=72):
    print(c("dim", char * width))


def header(title: str):
    print(f"\n{c('bold', '█' * 72)}")
    print(f"  {title}")
    print(f"{c('bold', '█' * 72)}")


def status(session):
    r = session.resource
    print(c("dim",
        f"  Day{session.time.day:>2} {session.time.slot.value:7s} Week{session.time.week} | "
        f"香火={r.incense:>3} 神力={r.divine_power:>2}/{r.divine_power_max:<2} "
        f"阳德={getattr(r, 'yang_de', 0):>3} 阴德={getattr(r, 'yin_de', 0):>3}"
    ))


def npc_list(session):
    for nid in session.agents.npc_ids:
        ag = session.agents.get(nid)
        if ag:
            d = ag.dynamic.current
            tier = ag.static.tier.value
            print(f"  {ag.name:6s} [{tier}] {d.location.value:16s} | "
                  f"情绪:{c('yellow', d.emotion.value):12s} | "
                  f"幸福:{d.happiness:3d} 精力:{d.energy:3d}")


def summarise_screenwriter(sw_result: ScreenwriterResult):
    """打印编剧产出摘要。"""
    if not sw_result.ok:
        print(f"  {c('red', '✗ 编剧不可用（将回退 CSV 匹配）')}")
        return

    events = sw_result.events
    high = sum(1 for e, _ in events if e.dramatic_score >= 6)
    mid = sum(1 for e, _ in events if 3 <= e.dramatic_score <= 5)
    low = sum(1 for e, _ in events if e.dramatic_score <= 2)

    print(f"\n  {c('cyan', '【时期预告摘要】')}")
    print(f"  {c('green', sw_result.slot_summary[:150])}")
    print(f"\n  {c('cyan', f'【事件产出】共 {len(events)} 个  ') + c('red', f'高{high} ') + c('yellow', f'中{mid} ') + c('dim', f'低{low}')}")

    for evt, outcome in events:
        score = evt.dramatic_score
        label = _score_label(score)
        print(f"    [{label}] {evt.name} (id={evt.id}) | {evt.location or '?'}")
        if evt.participants:
            names = _resolve_names(session, evt.participants)
            print(f"         参与: {', '.join(names)}")
        if evt.dialogue_skeleton:
            print(f"         骨架: ✓ (goal={evt.dialogue_skeleton.get('goal', '?')})")


def _score_label(score: int) -> str:
    if score <= 2:   return c("dim", f"ambient {score}")
    elif score <= 5: return c("yellow", f"light  {score}")
    elif score <= 8: return c("red", f"DRAMA  {score}")
    else:            return c("red", f"★★CRITICAL {score}★★")


def _resolve_names(session, pids):
    names = []
    for pid in pids:
        ag = session.agents.get(pid)
        names.append(ag.name if ag else pid)
    return names


def print_blessing_preview(sw_result: ScreenwriterResult):
    """模拟时段预告窗的赐福决策。"""
    blessing = sw_result.blessing_events
    if not blessing:
        print(f"  {c('dim', '(本时段无可赐福节点)')}")
        return {}

    print(f"\n  {c('magenta', '【时段预告窗 — 赐福决策】')}")
    for i, (evt, _) in enumerate(blessing):
        names = _resolve_names(session, evt.participants)
        diff = "困难" if evt.dramatic_score >= 9 else "中等"
        print(f"    [{i+1}] {c('bold', evt.name)} (score={evt.dramatic_score} {diff})")
        print(f"        地点:{evt.location or '?'}  参与:{', '.join(names)}")

    # 模拟玩家决策：赐福第一个高冲突事件
    chosen = blessing[0]
    print(f"\n  {c('green', '→ 玩家决定赐福')}: {c('bold', chosen[0].name)}")
    print(f"    消耗: 3 神力  |  硬币: 模拟抛掷...")

    return {
        "blessed_event_ids": [chosen[0].id],
        "blessed_targets": chosen[0].participants or [],
        "coin_result": {"success": random.random() > 0.35, "heads": random.randint(1, 3), "coins_thrown": 3},
    }


def print_dialogue_pipeline(event_dialogues: dict, all_events: list):
    """打印对白管线产出。"""
    if not event_dialogues:
        print(f"  {c('dim', '(本时段无对白管线输出)')}")
        return

    for evt, _ in all_events:
        dlg = event_dialogues.get(evt.id)
        if not dlg:
            continue
        lines = dlg.get("lines", [])
        print(f"\n  {c('cyan', f'【对白: {evt.name}】')}")
        for line in lines[:6]:
            actor = line.get("actor", "?")
            typ = line.get("type", "dialogue")
            text = line.get("text", "")
            prefix = {"action": " * ", "thought": " ~ "}.get(typ, "   ")
            print(f"    {prefix}{c('yellow', actor)}: {text}")


def print_event_settlement(all_events: list, settlement: list,
                           player_impact: dict, event_dialogues: dict):
    """打印事件结算和 event_triggered 推送。"""
    if not all_events:
        return

    for (evt, _), r in zip(all_events, settlement):
        if evt.dramatic_score <= 2:
            print(f"  {c('dim', f'[ambient] {evt.name} — 只写记忆，不推UI')}")
            continue

        dlg = event_dialogues.get(evt.id)
        impact = player_impact.get(evt.id, {})
        flags = []
        if impact.get("blessed"):       flags.append("赐福")
        if impact.get("coin_success"):  flags.append(c("green", "硬币✓"))
        else:                           flags.append(c("red", "硬币✗"))
        if impact.get("extra_investment"): flags.append("加大投入")

        print(f"  [{evt.event_type:6s}] {evt.name:12s} | "
              f"score={evt.dramatic_score} | "
              f"{', '.join(flags) if flags else '无介入'}")
        if r.resource_changes:
            print(f"    Δ资源: {r.resource_changes}")
        if r.bond_changes:
            print(f"    Δ缘线: {r.bond_changes}")
        if dlg:
            n_lines = len(dlg.get("lines", []))
            print(f"    对白管线: ✓ ({n_lines} 行定稿)")

    # Settlement complete
    resource = session.resource
    print(f"\n  {c('green', '✓ settlement_complete')} — "
          f"香火={resource.incense} 神力={resource.divine_power}/{resource.divine_power_max}")


def simulate_dream(session, day, slot):
    """模拟夜晚托梦流程。"""
    target_npc = None
    for nid in session.agents.npc_ids:
        ag = session.agents.get(nid)
        if ag and ag.static.tier.value in ("S", "A"):
            target_npc = ag
            break

    if target_npc is None:
        print(f"  {c('dim', '(无可托梦目标)')}")
        return

    dream_texts = [
        "港口今晚有危险，不要去。",
        "注意慧圆的一举一动，他在隐瞒什么。",
        "寺庙的方向有光，那是你的归处。",
    ]
    dream_text = random.choice(dream_texts)
    incense = session.resource.incense

    print(f"\n  {c('magenta', '【托梦】')}")
    print(f"    目标: {target_npc.name}")
    print(f"    内容: {dream_text}")
    print(f"    当前香火: {incense} → "
          f"{'杂念' if incense <= 40 else '暗示' if incense <= 100 else '低语' if incense <= 150 else '神谕'}")

    target_npc.receive_dream(
        dream_text=dream_text,
        incense_snapshot=incense,
        day=day, slot=slot,
    )

    # 验证记忆写入
    dreams = target_npc.memory.by_source("dream")
    assert len(dreams) > 0, "托梦记忆写入失败！"
    latest = dreams[-1]
    assert latest.dream_text == dream_text, f"dream_text 不匹配: {latest.dream_text} != {dream_text}"
    assert latest.dream_incense_snapshot == incense, f"snapshot 不匹配"

    # 验证上下文生成
    ctx = target_npc._build_dream_context()
    assert dream_text in ctx, f"托梦内容未出现在上下文中"
    assert str(incense) in ctx, f"香火快照未出现在上下文中"

    print(f"    {c('green', '✓ 记忆写入验证通过')}")
    print(f"    {c('green', '✓ 上下文生成验证通过')}")


# ── 主流程 ────────────────────────────────────────

async def advance_slot(session, mock_llm, templates) -> dict:
    """推进一个时段，模拟完整 v2 流程。"""
    if not session.time.can_advance():
        return None

    result = session.time.advance()
    header(f"Day{result.day} {result.slot.value}  Week{result.week}  {result.phase_name}")
    status(session)

    if result.is_new_day:
        session.resource.apply_daily()

    # NPC 思考
    print(f"\n  {c('cyan', '【NPC 思考】')}")
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
    actions = await _think_all()

    for aid, action in zip(s_a_ids, actions):
        ag = session.agents.get(aid)
        name = ag.name if ag else "?"
        loc = ag.dynamic.current.location.value if ag else "?"
        if isinstance(action, Exception):
            print(f"    {name}: {c('red', 'ERROR')} - {action}")
        else:
            short = (action or "(无)").strip().replace("\n", " ")[:40]
            print(f"    {name}: {short}")
            npc_intentions.append((aid, name, action or "", loc))

    # 编剧编排
    print(f"\n  {c('cyan', '【编剧编排】')}")
    sep()
    outline = load_story_outline()
    sw_result = await screenwriter_think(
        session=session, story_outline=outline,
        day=result.day, slot=result.slot, week=result.week,
        phase_name=result.phase_name,
        npc_intentions=npc_intentions,
        llm=mock_llm, templates=templates,
    )
    summarise_screenwriter(sw_result)

    # CSV 匹配（兜底）
    if not sw_result.ok:
        beat_events = []
    else:
        beat_events = sw_result.events

    locs = {}
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag:
            locs[aid] = ag.dynamic.current.location.value
    locs.update({
        "heaven_messenger": "temple", "tudi_gong": "temple",
        "underworld_messenger": "temple", "town_representative": "plaza",
    })

    events_csv = load_events()
    csv_matched = match_events(
        events_csv, day=result.day, slot=result.slot,
        week=result.week, participant_locations=locs,
    )

    max_total = outline.global_constraints.max_events_per_slot if outline else 3
    beat_ids = {e[0].id for e in beat_events}
    all_matched = list(beat_events)
    for csv_pair in csv_matched:
        if len(all_matched) >= max_total:
            break
        if csv_pair[0].id not in beat_ids:
            all_matched.append(csv_pair)

    # 时段预告窗 — 模拟玩家介入
    player_decision = print_blessing_preview(sw_result)
    blessed_ids = set(player_decision.get("blessed_event_ids", []))

    # Build per-event player_impact_flags (matches v2 event_triggered format)
    per_event_impact: dict = {}
    coin = player_decision.get("coin_result", {})
    for eid in blessed_ids:
        per_event_impact[eid] = {
            "blessed": True,
            "coin_success": coin.get("success", False),
            "extra_investment": player_decision.get("extra_investment", False),
        }
    # Add non-blessed events with neutral flags
    for evt, _ in all_matched:
        if evt.id not in per_event_impact:
            per_event_impact[evt.id] = {}

    # 对白管线（冲突分分流）
    event_dialogues = {}
    sep()
    print(f"\n  {c('cyan', '【对白管线 — 冲突分分流】')}")

    # v2: 在 think 之后才注入 Mock LLM，避免 think 阶段收到 JSON
    npc_llm = MockNpcLLM()
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag and ag.static.tier.value in ("S", "A"):
            ag.llm = npc_llm

    participants_map = {}
    for evt, _ in all_matched:
        participants_map[evt.id] = evt.participants or []

    pc_for_fill = {
        "blessed_event_ids": list(blessed_ids),
        "blessed_targets": player_decision.get("blessed_targets", []),
        "participants_map": participants_map,
    }

    for evt, _ in all_matched:
        score = evt.dramatic_score

        if score <= 2:
            print(f"  {c('dim', f'[ambient {score:2d}]')} {evt.name:16s} → 只写记忆")
            continue

        elif score <= 5:
            print(f"  {c('yellow', f'[light  {score:2d}]')} {evt.name:16s} → 轻量模板")
            continue

        else:
            skeleton = getattr(evt, "dialogue_skeleton", None)
            if not skeleton:
                print(f"  {c('red', f'[DRAMA  {score:2d}]')} {evt.name:16s} → 无骨架，跳过管线")
                continue

            participants = evt.participants or []
            s_a_count = sum(
                1 for pid in participants
                if session.agents.get(pid)
                and session.agents.get(pid).static.tier.value in ("S", "A")
            )
            if s_a_count < 2:
                print(f"  {c('red', f'[DRAMA  {score:2d}]')} {evt.name:16s} → S/A 参与者不足({s_a_count})，跳过")
                continue

            try:
                dialogue = await run_dialogue_pipeline(
                    evt, session, result.day, result.slot,
                    npc_llm, player_context=pc_for_fill,
                )
                if dialogue:
                    event_dialogues[evt.id] = dialogue
                    print(f"  {c('green', f'[DRAMA  {score:2d}]')} {evt.name:16s} → ✓ 对白管线完成 ({len(dialogue.get('lines', []))}行)")
                else:
                    print(f"  {c('red', f'[DRAMA  {score:2d}]')} {evt.name:16s} → ✗ 管线失败")
            except Exception as e:
                print(f"  {c('red', f'[DRAMA  {score:2d}]')} {evt.name:16s} → ERROR: {e}")

    # 事件执行 + 结算
    print(f"\n  {c('cyan', '【事件结算】')}")
    sep()

    executable = [(e, o) for e, o in all_matched if e.dramatic_score > 2]
    ambient = [(e, o) for e, o in all_matched if e.dramatic_score <= 2]

    for evt, _ in ambient:
        for pid in (evt.participants or []):
            ag = session.agents.get(pid)
            if ag:
                ag.remember(
                    day=result.day, slot=result.slot,
                    description=evt.description or "日常氛围。",
                    importance=1, source="ambient",
                    event_id=evt.id, participants=evt.participants or [],
                )

    settlement = []
    if executable:
        settlement = execute_events(
            executable, session.resource, session.agents,
            day=result.day, slot=result.slot,
        )
        for (evt, _), r in zip(executable, settlement):
            if r.bond_changes:
                parts = [f"bond_{k}:{v:+d}" for k, v in r.bond_changes.items()]
                session.bonds.apply_delta(";".join(parts))
            if r.karma_changes:
                parts = [f"{k}:{v:+d}" for k, v in r.karma_changes.items()]
                session.karma.apply_delta(";".join(parts))

            for pid in (evt.participants or []):
                ag = session.agents.get(pid)
                if ag:
                    ag.remember(
                        day=result.day, slot=result.slot,
                        description=evt.description or r.event_name,
                        importance=min(evt.dramatic_score, 10),
                        source="event",
                        event_id=evt.id, participants=evt.participants or [],
                    )

    print_event_settlement(all_matched, settlement, per_event_impact, event_dialogues)

    # 打印对白产出（如有）
    if event_dialogues:
        print_dialogue_pipeline(event_dialogues, all_matched)

    # 夜晚旁白 + 模拟托梦
    if result.slot.value == "night":
        sep()
        print(f"\n  {c('cyan', '【夜晚旁白】')}")
        beat_text = f"（第{result.day}天夜晚，归潮镇在月光下沉睡。）"
        print(f"    {beat_text}")

        if SIMULATE_DREAM:
            simulate_dream(session, result.day, result.slot)

    # NPC 快照（每隔2个时段打印一次，减少输出）
    if result.day % 2 == 1 or result.slot.value == "night":
        pass  # already printed enough

    return {
        "slot": result.slot.value,
        "day": result.day,
        "sw_result": sw_result,
        "events": len(all_matched),
        "dialogues": len(event_dialogues),
        "player_impact": per_event_impact,
    }


# ── 入口 ──────────────────────────────────────────

async def main():
    print(f"\n{c('bold', '═══ v2 架构端到端集成测试 ═══')}")
    print(f"  模拟 {SLOTS_TO_ADVANCE} 个时段推进")
    if SIMULATE_DREAM:
        print(f"  模拟夜晚托梦流程")
    print()

    # 初始化游戏
    global session
    session = init_session()
    outline = load_story_outline()
    templates = load_event_templates()
    mock_llm = MockScreenwriterLLM()

    npc_list(session)
    sep("=")
    header(f"初始状态: Day{session.time.day} {session.time.slot.value}")

    total_events = 0
    total_dialogues = 0
    slot_results = []

    for i in range(SLOTS_TO_ADVANCE):
        result = await advance_slot(session, mock_llm, templates)
        if result is None:
            print(f"\n{c('yellow', '游戏已结束')}")
            break
        slot_results.append(result)
        total_events += result["events"]
        total_dialogues += result["dialogues"]

    # 最终总结
    header("集成测试总结")
    print(f"\n  推进了 {len(slot_results)} 个时段")
    print(f"  触发了 {total_events} 个事件")
    print(f"  完成了 {total_dialogues} 条对白管线")

    # 汇总 conflict score 分布
    all_scores = []
    for r in slot_results:
        sw = r.get("sw_result")
        if sw and sw.ok:
            for evt, _ in sw.events:
                all_scores.append(evt.dramatic_score)

    if all_scores:
        high = sum(1 for s in all_scores if s >= 6)
        mid = sum(1 for s in all_scores if 3 <= s <= 5)
        low = sum(1 for s in all_scores if s <= 2)
        print(f"  冲突分分布: {c('red', f'高{high} ')}{c('yellow', f'中{mid} ')}{c('dim', f'低{low}')}")

    # 验证 MemoryStore.by_source
    print(f"\n  {c('cyan', '【最终验证】')}")
    for nid in session.agents.npc_ids:
        ag = session.agents.get(nid)
        if not ag:
            continue
        dreams = ag.memory.by_source("dream")
        events_mem = ag.memory.by_source("event")
        ambient_mem = ag.memory.by_source("ambient")
        if dreams or events_mem or ambient_mem:
            print(f"    {ag.name}: dream={len(dreams)} event_mem={len(events_mem)} ambient_mem={len(ambient_mem)}")

    # 验证 NPC 快照
    print(f"\n  {c('cyan', '【最终 NPC 状态】')}")
    npc_list(session)

    print(f"\n{c('bold', '═══ 测试完成 ═══')}\n")


if __name__ == "__main__":
    asyncio.run(main())
