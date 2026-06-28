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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.backend.server.state import (
    get_session, init_session, load_session, is_initialized,
)
from src.backend.engine.event import load_events, match_events, execute_events

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
    """推进一个时段：时间 → 事件 → 结算 → NPC行动。"""
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

    # 3. 周结算（由编排器根据 is_new_week 处理，这里先跳过）

    # 4. 事件匹配 + 执行
    locs = {}
    for aid in session.agents.npc_ids:
        agent = session.agents.get(aid)
        if agent:
            locs[aid] = agent.dynamic.current.location.value
    # C 级 NPC
    locs.update({
        "heaven_messenger": "temple", "tudi_gong": "temple",
        "underworld_messenger": "temple", "town_representative": "plaza",
    })

    matched = match_events(events, day=result.day, slot=result.slot,
                           week=result.week, participant_locations=locs)

    if matched:
        settlement = execute_events(matched, session.resource, session.agents,
                                    day=result.day, slot=result.slot)
        for r in settlement:
            await _send(ws, "event_triggered", {
                "event_id": r.event_id,
                "event_name": r.event_name,
                "outcome_name": r.outcome_name,
                "resource_changes": r.resource_changes,
                "npc_changes": r.npc_changes,
                "bonds_queued": r.bond_changes,
                "karma_queued": r.karma_changes,
            }, request_id)

            # 应用缘线
            if r.bond_changes:
                delta_parts = [f"bond_{k}:{v:+d}" for k, v in r.bond_changes.items()]
                session.bonds.apply_delta(";".join(delta_parts))

            # 应用业线
            if r.karma_changes:
                delta_parts = [f"{k}:{v:+d}" for k, v in r.karma_changes.items()]
                session.karma.apply_delta(";".join(delta_parts))

    # 5. NPC 行为决策（S/A 级并发，流式返回）
    await _send(ws, "npc_actions_start", {}, request_id)

    async def _think_and_send(agent):
        if agent.static.tier.value in ("S", "A"):
            action = await agent.think(result.day, result.slot)
            return (agent.npc_id, agent.name, action)
        return None

    tasks = [_think_and_send(session.agents.get(aid))
             for aid in session.agents.npc_ids]
    completed = await asyncio.gather(*tasks)

    for item in completed:
        if item is None:
            continue
        npc_id, name, action = item
        await _send(ws, "npc_action", {
            "npc_id": npc_id,
            "npc_name": name,
            "action": action,
        }, request_id)

    await _send(ws, "settlement_complete", {
        "day": result.day,
        "slot": result.slot.value,
        "resource": {
            "incense": session.resource.incense,
            "divine_power": session.resource.divine_power,
            "divine_power_max": session.resource.divine_power_max,
        },
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
