"""WebSocket 游戏主通道。

双向实时通信：
    客户端 → 服务端: advance_time / chat / get_state
    服务端 → 客户端: 时间、事件、资源、NPC行动（流式）

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
from src.backend.ai.screenwriter import screenwriter_think
from src.backend.ai.narrator.narrator import generate_narrator_beat

router = APIRouter()

# 单连接（单局游戏）
_active_ws: Optional[WebSocket] = None


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
    """推进一个时段：时间 → NPC思考 → 编剧编排 → 事件结算 → 旁白。"""
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

    # 3. NPC 行为决策（S/A 级并发）—— 移到事件匹配之前
    await _send(ws, "npc_actions_start", {}, request_id)

    npc_intentions: list = []  # [(npc_id, name, action_text, location), ...]

    async def _think_and_collect(agent):
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
    screenwriter_llm = None
    for aid in session.agents.npc_ids:
        agent = session.agents.get(aid)
        if agent and agent.static.tier.value == "S":
            screenwriter_llm = agent.llm
            break

    screenwriter_ok, beat_events = await screenwriter_think(
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

    # 5. CSV 事件匹配（补充/兜底）
    locs = {}
    for aid in session.agents.npc_ids:
        agent = session.agents.get(aid)
        if agent:
            locs[aid] = agent.dynamic.current.location.value
    locs.update({
        "heaven_messenger": "temple", "tudi_gong": "temple",
        "underworld_messenger": "temple", "town_representative": "plaza",
    })

    csv_matched = match_events(events, day=result.day, slot=result.slot,
                               week=result.week, participant_locations=locs)

    # Merge: screenwriter beat events first, then CSV events (deduped by event_id)
    max_total = outline.global_constraints.max_events_per_slot if outline else 3
    # Build dedup set: both beat_id and any CSV event_id the beat references
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

    # 6. 执行事件
    if all_matched:
        id_name_map: dict = {}
        for aid in session.agents.npc_ids:
            ag = session.agents.get(aid)
            if ag:
                id_name_map[aid] = ag.name

        settlement = execute_events(all_matched, session.resource, session.agents,
                                    day=result.day, slot=result.slot)
        for (evt_template, _outcome), r in zip(all_matched, settlement):
            participants_ids = list(evt_template.participants or [])
            participants_names = [id_name_map.get(pid, pid) for pid in participants_ids]
            location_id = getattr(evt_template, "location", "") or ""
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
            }, request_id)

            if r.bond_changes:
                delta_parts = [f"bond_{k}:{v:+d}" for k, v in r.bond_changes.items()]
                session.bonds.apply_delta(";".join(delta_parts))

            if r.karma_changes:
                delta_parts = [f"{k}:{v:+d}" for k, v in r.karma_changes.items()]
                session.karma.apply_delta(";".join(delta_parts))

    await _send(ws, "settlement_complete", {
        "day": result.day,
        "slot": result.slot.value,
        "resource": {
            "incense": session.resource.incense,
            "divine_power": session.resource.divine_power,
            "divine_power_max": session.resource.divine_power_max,
        },
    }, request_id)

    # 7. 夜间旁白（土地公视角）
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
    """处理神力干预：把托梦/赐福写入相关 NPC 的记忆库。

    前端已在本地做过命运硬币结算（可复现的确定性程序）。
    后端只负责：
    - 记录托梦文字到目标 NPC 的记忆（importance=8，emotion=hopeful）
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

    from src.backend.models.npc import Emotion

    affected: list = []
    for npc_id in target_npc_ids:
        agent = session.agents.get(npc_id)
        if agent is None:
            continue

        if intervention_id == "dream_hint" and dream_text:
            desc = f"（梦中）土地公托梦：{dream_text}"
            agent.remember(
                day=day, slot=slot, description=desc,
                importance=8, emotion=Emotion.EXCITED,
            )
        elif intervention_id == "blessing":
            outcome_flag = "感受到" if coin_result.get("success", False) else "隐约察觉"
            desc = f"{outcome_flag}一股温暖的护佑降临身上，仿佛神明的赐福。"
            agent.remember(
                day=day, slot=slot, description=desc,
                importance=7, emotion=Emotion.HAPPY,
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
