"""WebSocket 游戏主通道。

双向实时通信：
    客户端 → 服务端: advance_time / chat / get_state / slot_preview_response
    服务端 → 客户端: 时间、事件、资源、NPC行动（流式）、slot_preview

消息格式（架构文档 §2.4）：
    {"type": "advance_time", "payload": {...}, "timestamp": 0, "request_id": "..."}
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.backend.server.state import (
    get_session, init_session, load_session, is_initialized,
)
from src.backend.engine.event import load_events, match_events, execute_events
from src.backend.engine.story import load_event_templates, load_story_outline
from src.backend.ai.screenwriter import screenwriter_think, ScreenwriterResult
from src.backend.ai.narrator.narrator import generate_narrator_beat
from src.backend.ai.dialogue_designer.pipeline import run_dialogue_pipeline
from src.backend.models.npc import Emotion

router = APIRouter()

# 单连接（单局游戏）
_active_ws: Optional[WebSocket] = None

# v2: slot_preview 回合的响应 Future
_slot_response_future: Optional[asyncio.Future] = None


def _msg(msg_type: str, payload: dict = None, request_id: str = None) -> dict:
    return {
        "type": msg_type,
        "payload": payload or {},
        "timestamp": time.time(),
        "request_id": request_id or "",
    }


async def _send(ws: WebSocket, msg_type: str, payload: dict = None, request_id: str = None):
    await ws.send_json(_msg(msg_type, payload, request_id))


# ═══════════════════════════════════════════════════
# WebSocket 端点
# ═══════════════════════════════════════════════════

@router.websocket("/ws/game")
async def ws_game(ws: WebSocket):
    global _active_ws

    await ws.accept()
    _active_ws = ws

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, "error", {"message": "无效的 JSON"})
                continue

            msg_type = data.get("type", "")
            payload = data.get("payload", {})
            request_id = data.get("request_id", str(uuid.uuid4().hex[:8]))

            if msg_type == "advance_time":
                await _handle_advance_time(ws, request_id)
            elif msg_type == "chat":
                await _handle_chat(ws, payload, request_id)
            elif msg_type == "get_state":
                await _handle_get_state(ws, request_id)
            elif msg_type == "new_game":
                await _handle_new_game(ws, request_id)
            elif msg_type == "load_game":
                await _handle_load_game(ws, payload, request_id)
            elif msg_type == "save_game":
                await _handle_save_game(ws, payload, request_id)
            elif msg_type == "apply_intervention":
                await _handle_apply_intervention(ws, payload, request_id)
            elif msg_type == "slot_preview_response":
                await _handle_slot_preview_response(ws, payload, request_id)
            else:
                await _send(ws, "error", {"message": f"未知的消息类型: {msg_type}"}, request_id)

    except WebSocketDisconnect:
        pass
    finally:
        _active_ws = None


# ═══════════════════════════════════════════════════
# 消息处理
# ═══════════════════════════════════════════════════

async def _handle_advance_time(ws: WebSocket, request_id: str):
    """推进一个时段（v2：时段预告窗 + 冲突分分流）。

    流程: 时间推进 → NPC思考 → 编剧编排 → 时段预告窗 → 对白管线(按冲突分分流) → 事件结算
    """
    if not is_initialized():
        await _send(ws, "error", {"message": "游戏未初始化"}, request_id)
        return

    session = get_session()
    events = load_events()

    # 1. 推进时间
    if not session.time.can_advance():
        await _send(ws, "game_over", {"message": "已到达第60天终局"}, request_id)
        return

    result = session.time.advance()
    await _send(ws, "time_advanced", {
        "day": result.day,
        "slot": result.slot.value,
        "week": result.week,
        "is_new_day": result.is_new_day,
        "is_new_week": result.is_new_week,
        "phase_name": result.phase_name,
    }, request_id)

    # 2. 每日结算
    if result.is_new_day:
        session.resource.apply_daily()

    # 3. NPC 行为决策（S/A 级并发）
    await _send(ws, "npc_actions_start", {}, request_id)

    npc_intentions: list = []

    async def _think_and_collect(agent):
        if agent is None:
            return None
        if agent.static.tier.value in ("S", "A"):
            action = await agent.think(result.day, result.slot)
            return (agent.npc_id, agent.name, action,
                    agent.dynamic.current.location.value)
        return None

    tasks = [_think_and_collect(session.agents.get(aid))
             for aid in session.agents.npc_ids]
    completed = await asyncio.gather(*tasks)

    for item in completed:
        if item is None:
            continue
        npc_id, name, action, loc = item
        npc_intentions.append((npc_id, name, action or "", loc))
        await _send(ws, "npc_action", {
            "npc_id": npc_id, "npc_name": name, "action": action,
        }, request_id)

    # 4. 编剧 Agent：大纲驱动的叙事编排
    outline = load_story_outline()
    templates = load_event_templates()
    screenwriter_llm = _get_llm(session)

    sw_result = await screenwriter_think(
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

    _print_screenwriter_log(sw_result, result)

    if not sw_result.ok:
        print(f"[编剧] Day{result.day} {result.slot.value} | 不可用，回退CSV匹配")
        beat_events = []
    else:
        beat_events = sw_result.events

    # 5. CSV 事件匹配（补充/兜底）
    locs = _build_location_map(session)
    csv_matched = match_events(events, day=result.day, slot=result.slot,
                               week=result.week, participant_locations=locs)

    max_total = outline.global_constraints.max_events_per_slot if outline else 3
    beat_event_ids: set = {e[0].id for e in beat_events}
    if outline:
        for e, _ in beat_events:
            for beat in outline.all_beats():
                if beat.id == e.id and beat.event_id:
                    beat_event_ids.add(beat.event_id)
    all_matched: list = list(beat_events)

    for csv_pair in csv_matched:
        if len(all_matched) >= max_total:
            break
        if csv_pair[0].id not in beat_event_ids:
            all_matched.append(csv_pair)

    # ─── v2: 时段预告窗 ───────────────────────────────────

    player_context = None
    player_impact_flags: dict = {}

    if sw_result.ok:
        # Build blessing slots from high-drama events
        blessing_slots = _build_blessing_slots(sw_result, session)
        if blessing_slots:
            await _send(ws, "slot_preview", {
                "day": result.day,
                "slot": result.slot.value,
                "summary": sw_result.slot_summary,
                "blessing_slots": blessing_slots,
                "timeout_sec": 30,
            }, request_id)

            # Wait for player response (30s timeout)
            player_context = await _wait_for_slot_response(timeout=30.0)
            if player_context is None:
                print(f"[slot_preview] timeout or no response for day={result.day} slot={result.slot.value}")

            # Build player_impact_flags for event_triggered messages
            if player_context:
                for decision in player_context.get("decisions", []):
                    eid = decision.get("event_id", "")
                    if decision.get("action") == "bless":
                        player_impact_flags[eid] = {
                            "blessed": True,
                            "coin_success": decision.get("coin_result", {}).get("success", False),
                            "extra_investment": decision.get("extra_investment", False),
                        }

    # ─── v2: 冲突分分流 — 对白管线 ────────────────────────

    event_dialogues: dict = {}
    dialogue_llm = _get_llm(session)

    # Build participants map for blessing context
    participants_map: dict = {}
    for evt, _ in all_matched:
        participants_map[evt.id] = evt.participants or []

    pc_for_fill = {
        "blessed_event_ids": list(player_impact_flags.keys()),
        "blessed_targets": [],
        "participants_map": participants_map,
    }

    if dialogue_llm:
        for (evt_template, _) in all_matched:
            score = evt_template.dramatic_score

            if score <= 2:
                # 环境氛围：只写记忆，不发 event_triggered
                _write_ambient_memory(session, evt_template, result.day, result.slot)
                continue

            elif score <= 5:
                # 日常互动：轻量模板 — 只用 description，不走管线
                continue

            else:
                # 显著戏剧 (6+)：完整对白管线
                skeleton = getattr(evt_template, "dialogue_skeleton", None)
                if not skeleton:
                    continue
                participants = evt_template.participants or []
                s_a_count = sum(
                    1 for pid in participants
                    if session.agents.get(pid) and
                    session.agents.get(pid).static.tier.value in ("S", "A")
                )
                if s_a_count < 2:
                    continue

                try:
                    dialogue = await run_dialogue_pipeline(
                        evt_template, session, result.day, result.slot,
                        dialogue_llm, player_context=pc_for_fill,
                    )
                    if dialogue:
                        event_dialogues[evt_template.id] = dialogue
                        from src.backend.ai.dialogue_designer.pipeline import dialogue_to_description
                        desc = dialogue_to_description(dialogue)
                        if desc:
                            evt_template.description = desc
                except Exception as e:
                    print(f"[对白管线] event={evt_template.id} 失败: {type(e).__name__}: {e}")

    # 7. 执行事件 + 推送（v2：跳过 score ≤ 2 的事件）
    if all_matched:
        id_name_map = _build_name_map(session)

        # Filter out ambient events (score <= 2) for execution
        executable = [(e, o) for e, o in all_matched if e.dramatic_score > 2]
        ambient = [(e, o) for e, o in all_matched if e.dramatic_score <= 2]

        # Execute ambient events silently (memory already written above)
        for evt, _ in ambient:
            for pid in (evt.participants or []):
                agent = session.agents.get(pid)
                if agent:
                    agent.remember(
                        day=result.day, slot=result.slot,
                        description=evt.description or "日常氛围。",
                        importance=2, source="ambient",
                        event_id=evt.id, participants=evt.participants or [],
                    )

        # Execute drama events normally
        if executable:
            settlement = execute_events(executable, session.resource, session.agents,
                                        day=result.day, slot=result.slot)
            for (evt_template, _outcome), r in zip(executable, settlement):
                participants_ids = list(evt_template.participants or [])
                participants_names = [id_name_map.get(pid, pid) for pid in participants_ids]
                location_id = getattr(evt_template, "location", "") or ""
                dialogue = event_dialogues.get(evt_template.id)
                impact = player_impact_flags.get(evt_template.id, {})

                await _send(ws, "event_triggered", {
                    "event_id": r.event_id,
                    "event_name": r.event_name,
                    "outcome_name": r.outcome_name,
                    "resource_changes": r.resource_changes,
                    "npc_changes": r.npc_changes,
                    "bonds_queued": r.bond_changes,
                    "karma_queued": r.karma_changes,
                    "participant_ids": participants_ids,
                    "participant_names": participants_names,
                    "location_id": location_id,
                    "risk_level": getattr(evt_template, "risk_level", "Low"),
                    "description": getattr(evt_template, "description", ""),
                    "dialogue": dialogue,
                    "dramatic_score": evt_template.dramatic_score,
                    "player_impact_flags": impact,
                }, request_id)

                if r.bond_changes:
                    delta_parts = [f"bond_{k}:{v:+d}" for k, v in r.bond_changes.items()]
                    session.bonds.apply_delta(";".join(delta_parts))

                if r.karma_changes:
                    delta_parts = [f"{k}:{v:+d}" for k, v in r.karma_changes.items()]
                    session.karma.apply_delta(";".join(delta_parts))

                # Write event memory for participants
                for pid in participants_ids:
                    agent = session.agents.get(pid)
                    if agent:
                        agent.remember(
                            day=result.day, slot=result.slot,
                            description=evt_template.description or r.event_name,
                            importance=min(evt_template.dramatic_score, 10),
                            source="event",
                            event_id=evt_template.id,
                            participants=participants_ids,
                        )

    await _send(ws, "settlement_complete", {
        "day": result.day,
        "slot": result.slot.value,
        "resource": {
            "incense": session.resource.incense,
            "divine_power": session.resource.divine_power,
            "divine_power_max": session.resource.divine_power_max,
        },
    }, request_id)

    # 8. 夜间旁白（土地公视角）
    if result.slot.value == "night":
        try:
            recent_actions = [it for it in completed if it]
            beat = await generate_narrator_beat(
                session=session,
                day=result.day,
                slot=result.slot.value,
                recent_actions=recent_actions,
                llm=screenwriter_llm,
            )
            if beat:
                await _send(ws, "narrator_beat", {
                    "day": result.day,
                    "slot": result.slot.value,
                    "text": beat,
                }, request_id)
        except Exception as e:
            print(f"[ws_game] narrator_beat 生成失败：{type(e).__name__}: {e}")


async def _handle_apply_intervention(ws: WebSocket, payload: dict, request_id: str):
    """处理神力干预（v2：托梦携带香火快照，NPC self-receive）。

    前端已在本地做过命运硬币结算（可复现的确定性程序）。
    后端负责：
    - 读取当前香火值作为 incense_snapshot
    - 调用目标 NPC 的 receive_dream() 写入 source=dream 的记忆
    - 记录赐福护佑感应到目标 NPC 的记忆（importance=7）
    - 广播 intervention_applied 供 UI 追加日志
    """
    if not is_initialized():
        await _send(ws, "error", {"message": "游戏未初始化"}, request_id)
        return

    event_id: str = payload.get("event_id", "")
    intervention_id: str = payload.get("intervention_id", "")
    dream_text: str = payload.get("dream_text", "") or ""
    target_npc_ids: list = payload.get("target_npc_ids", []) or []
    coin_result: dict = payload.get("coin_result", {}) or {}

    session = get_session()
    day = session.time.day
    slot = session.time.slot
    incense_snapshot = session.resource.incense  # v2: 香火快照

    affected: list = []
    for npc_id in target_npc_ids:
        agent = session.agents.get(npc_id)
        if agent is None:
            continue

        if intervention_id == "dream_hint" and dream_text:
            # v2: 使用 receive_dream，携带香火快照
            agent.receive_dream(
                dream_text=dream_text,
                incense_snapshot=incense_snapshot,
                day=day,
                slot=slot,
            )
        elif intervention_id == "blessing":
            outcome_flag = "感受到" if coin_result.get("success", False) else "隐约察觉"
            desc = f"{outcome_flag}一股温暖的护佑降临身上，仿佛神明的赐福。"
            agent.remember(
                day=day, slot=slot, description=desc,
                importance=7, emotion=Emotion.HAPPY,
                source="blessing_felt",
            )
        else:
            desc = f"命运的织线似乎被无形之手轻轻拨动了一下（{intervention_id}）。"
            agent.remember(
                day=day, slot=slot, description=desc,
                importance=5, emotion=Emotion.NEUTRAL,
            )
        affected.append(npc_id)

    await _send(ws, "intervention_applied", {
        "event_id": event_id,
        "intervention_id": intervention_id,
        "dream_text": dream_text,
        "coin_result": coin_result,
        "affected_npc_ids": affected,
        "incense_snapshot": incense_snapshot,
    }, request_id)


async def _handle_chat(ws: WebSocket, payload: dict, request_id: str):
    """NPC 对话。"""
    if not is_initialized():
        await _send(ws, "error", {"message": "游戏未初始化"}, request_id)
        return

    npc_id = payload.get("npc_id", "")
    message = payload.get("message", "")
    day = payload.get("day", 1)

    session = get_session()
    agent = session.agents.get(npc_id)
    if agent is None:
        await _send(ws, "error", {"message": f"NPC 不存在: {npc_id}"}, request_id)
        return

    reply = await agent.respond(message, speaker_name="土地公", current_day=day)
    await _send(ws, "npc_response", {
        "npc_id": agent.npc_id,
        "npc_name": agent.name,
        "response": reply,
    }, request_id)


async def _handle_get_state(ws: WebSocket, request_id: str):
    """查询完整游戏状态。"""
    if not is_initialized():
        await _send(ws, "error", {"message": "游戏未初始化"}, request_id)
        return

    session = get_session()
    snapshots = session.agents.all_snapshots()
    await _send(ws, "game_state", {
        "day": session.time.day,
        "slot": session.time.slot.value,
        "week": session.time.week,
        "phase_name": session.time.phase_name,
        "incense": session.resource.incense,
        "divine_power": session.resource.divine_power,
        "divine_power_max": session.resource.divine_power_max,
        "yin_de": session.resource.yin_de,
        "yang_de": session.resource.yang_de,
        "npc_total": snapshots.total,
    }, request_id)


async def _handle_new_game(ws: WebSocket, request_id: str):
    """通过 WS 创建新游戏。"""
    session = init_session()
    await _send(ws, "game_created", {
        "npc_total": session.agents.all_snapshots().total,
    }, request_id)


async def _handle_load_game(ws: WebSocket, payload: dict, request_id: str):
    """通过 WS 加载存档。"""
    slot = payload.get("slot", 1)
    from src.backend.storage import JsonStorage
    from src.backend.engine.game_session import GameSession

    storage = JsonStorage()
    try:
        data = await storage.load(slot)
    except FileNotFoundError:
        await _send(ws, "error", {"message": f"存档槽位 {slot} 为空"}, request_id)
        return

    session = GameSession.from_dict(data)
    load_session(session)
    await _send(ws, "game_loaded", {
        "day": session.time.day,
        "npc_total": session.agents.all_snapshots().total,
    }, request_id)


async def _handle_save_game(ws: WebSocket, payload: dict, request_id: str):
    """通过 WS 保存游戏。"""
    if not is_initialized():
        await _send(ws, "error", {"message": "游戏未初始化"}, request_id)
        return

    slot = payload.get("slot", 1)
    from src.backend.storage import JsonStorage
    storage = JsonStorage()
    session = get_session()
    await storage.save(slot, session.to_dict())
    await _send(ws, "game_saved", {"slot": slot, "day": session.time.day}, request_id)


# ═══════════════════════════════════════════════════
# v2: slot_preview 回合处理
# ═══════════════════════════════════════════════════

async def _handle_slot_preview_response(ws: WebSocket, payload: dict, request_id: str):
    """接收玩家在时段预告窗的决策，解挂 _slot_response_future。"""
    global _slot_response_future
    if _slot_response_future and not _slot_response_future.done():
        _slot_response_future.set_result(payload)
    await _send(ws, "slot_preview_ack", {"status": "received"}, request_id)


async def _wait_for_slot_response(timeout: float = 30.0) -> Optional[dict]:
    """等待前端 slot_preview_response，超时返回 None。"""
    global _slot_response_future
    _slot_response_future = asyncio.get_event_loop().create_future()
    try:
        result = await asyncio.wait_for(_slot_response_future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        return None
    finally:
        _slot_response_future = None


# ═══════════════════════════════════════════════════
# v2: 辅助函数
# ═══════════════════════════════════════════════════

def _get_llm(session) -> Optional[object]:
    """获取任意 S 级 NPC 的 LLM 客户端。"""
    for aid in session.agents.npc_ids:
        agent = session.agents.get(aid)
        if agent and agent.static.tier.value == "S":
            return agent.llm
    # Fallback: any S/A
    for aid in session.agents.npc_ids:
        agent = session.agents.get(aid)
        if agent and agent.static.tier.value in ("S", "A"):
            return agent.llm
    return None


def _build_location_map(session) -> dict:
    """构建 NPC 当前位置映射。"""
    locs = {}
    for aid in session.agents.npc_ids:
        agent = session.agents.get(aid)
        if agent:
            locs[aid] = agent.dynamic.current.location.value
    locs.update({
        "heaven_messenger": "temple", "tudi_gong": "temple",
        "underworld_messenger": "temple", "town_representative": "plaza",
    })
    return locs


def _build_name_map(session) -> dict:
    """构建 NPC ID → 中文名映射。"""
    name_map = {}
    for aid in session.agents.npc_ids:
        ag = session.agents.get(aid)
        if ag:
            name_map[aid] = ag.name
    return name_map


def _build_blessing_slots(sw_result: ScreenwriterResult, session) -> list:
    """从编剧产出构建赐福节点列表（推送给前端时段预告窗）。"""
    slots = []
    for evt, outcome in sw_result.blessing_events:
        participants = evt.participants or []
        id_map = _build_name_map(session)
        names = [id_map.get(pid, pid) for pid in participants]
        difficulty = "困难" if evt.dramatic_score >= 9 else "中等"
        slots.append({
            "event_id": evt.id,
            "event_name": evt.name,
            "location_id": evt.location or "",
            "location_label": evt.location or "某处",
            "participants": participants,
            "participant_names": names,
            "difficulty_hint": difficulty,
            "base_cost": 3,
            "dramatic_score": evt.dramatic_score,
            "hint_text": f"你或可在他们的相遇处轻拨命运一二。" if evt.dramatic_score >= 9 else "",
        })
    return slots


def _write_ambient_memory(session, evt, day, slot) -> None:
    """为 score ≤ 2 的 ambient 事件写入低重要度记忆。"""
    for pid in (evt.participants or []):
        agent = session.agents.get(pid)
        if agent:
            agent.remember(
                day=day, slot=slot,
                description=evt.description or "日常氛围。",
                importance=1,
                source="ambient",
                event_id=evt.id,
                participants=evt.participants or [],
            )


def _print_screenwriter_log(sw_result: ScreenwriterResult, time_result) -> None:
    """打印编剧产出日志。"""
    if not sw_result.ok:
        return
    events = sw_result.events
    if not events:
        return

    spon = [e for e in events if e[0].id.startswith("spontaneous_")]
    beat = [e for e in events if not e[0].id.startswith("spontaneous_")]
    high = sum(1 for e, _ in events if e.dramatic_score >= 6)
    mid = sum(1 for e, _ in events if 3 <= e.dramatic_score <= 5)
    low = sum(1 for e, _ in events if e.dramatic_score <= 2)

    print(f"\n{'='*60}")
    print(f"[编剧] Day{time_result.day} {time_result.slot.value} | "
          f"节拍{len(beat)} + 即兴{len(spon)} "
          f"→ {len(events)} total (高{high} 中{mid} 低{low})")
    print(f"[预告] {sw_result.slot_summary[:120]}")
    for t, o in beat:
        print(f"  ◆ 节拍(score={t.dramatic_score}): {t.name} ({t.id}) → {o.id}")
    for t, o in spon:
        delta_info = []
        if o.bond_delta:
            delta_info.append(f"缘线:{o.bond_delta}")
        if o.npc_state_delta:
            delta_info.append(f"NPC:{o.npc_state_delta}")
        delta_str = " | ".join(delta_info) if delta_info else "无delta"
        print(f"  🎭 即兴(score={t.dramatic_score}): {t.name} | {t.location or '?'} | {t.participants}")
        print(f"     {(t.description or '')[:120]}")
        print(f"     delta: {delta_str}")
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════
# v2: 预留扩展点（§12.3）
# ═══════════════════════════════════════════════════

async def _maybe_reorchestrate(player_context: dict, events: list, session) -> list:
    """应急二次编排钩子（首版暂不启用，预留接口）。

    当玩家做出强干预（例：赐福 3 个节点全部加大投入）后，
    编剧可以二次调用微调事件走向。首版不做——多一次 LLM 调用
    带来的收益 vs. 成本不明。
    """
    # TODO: 未来实现
    return events
