"""扮演土地公走一遍游戏流程。

通过 WebSocket 连接游戏服务端，模拟完整的一天：
    观察 → 对话 → 推进时间 → 观看事件和 NPC 行动

用法：
    python scripts/play_as_tudi.py
"""

import asyncio
import json
import random
import sys
import os
import uuid

# 确保项目根在 path 里
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "backend"))


WS_URL = "ws://localhost:8001/ws/game"


async def recv_until(ws, target_types: set, timeout=120.0):
    """持续接收消息，直到收到目标类型之一。返回所有收到的消息。"""
    messages = []
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            messages.append(msg)
            if msg["type"] in target_types:
                return messages
        except asyncio.TimeoutError:
            return messages


async def send_and_recv(ws, msg_type: str, payload: dict = None, target_type: str = None):
    """发一条消息，等一条回复。"""
    req_id = uuid.uuid4().hex[:8]
    await ws.send(json.dumps({
        "type": msg_type,
        "payload": payload or {},
        "request_id": req_id,
    }))
    msgs = await recv_until(ws, {target_type} if target_type else {"settlement_complete", "npc_response", "game_state", "game_created", "game_loaded", "game_saved", "error"}, timeout=120.0)
    return msgs


def print_divider(char="─", width=60):
    print(char * width)


def print_npc_says(name: str, text: str):
    print(f"\n  [{name}] {text}")


async def main():
    import websockets

    print_divider("═")
    print("  归潮镇 · 土地公视角")
    print("  第 5 天 · 早晨")
    print_divider("═")

    async with websockets.connect(WS_URL) as ws:

        # ═══ 1. 创建游戏 ═══
        msgs = await send_and_recv(ws, "new_game", target_type="game_created")
        print(f"\n  ▸ 开局：{msgs[0]['payload']['npc_total']} 个 NPC 已在归潮镇就位。")

        # ═══ 2. 查看状态 ═══
        msgs = await send_and_recv(ws, "get_state", target_type="game_state")
        state = msgs[0]["payload"]
        print(f"  ▸ 第 {state['day']} 天 · 早晨 ｜ 第 {state['week']} 周「{state['phase_name']}」")
        print(f"  ▸ 香火 {state['incense']} ｜ 神力 {state['divine_power']}/{state['divine_power_max']}")
        print(f"  ▸ 阴德 {state['yin_de']} ｜ 阳德 {state['yang_de']}")

        # ═══ 3. 巡视小镇 — 对话 ═══
        print_divider()
        print("  土地公巡视小镇...")
        print_divider()

        # 3a. 找林潮音
        msgs = await send_and_recv(ws, "chat", {
            "npc_id": "lin_chaoyin",
            "message": "潮音，早上好。我看你今天有点心不在焉，又做那些梦了吗？",
            "day": 5,
        }, target_type="npc_response")
        print_npc_says("林潮音", msgs[0]["payload"]["response"])

        # 3b. 找陈海生
        msgs = await send_and_recv(ws, "chat", {
            "npc_id": "chen_haisheng",
            "message": "陈老板，最近渔获怎样？有什么需要帮忙的吗？",
            "day": 5,
        }, target_type="npc_response")
        print_npc_says("陈海生", msgs[0]["payload"]["response"])

        # 3c. 消耗神力 — 赐福
        print()
        print("  ▸ 土地公默默消耗 2 点神力，赐福给陈海生今天的渔获...")

        # ═══ 4. 推进时间 — 早晨 → 正午 ═══
        print_divider()
        print("  时间推进 — 早晨 → 正午")
        print_divider()

        await ws.send(json.dumps({"type": "advance_time"}))
        advancing = True
        npc_count = 0
        while advancing:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
                msg = json.loads(raw)
                t, p = msg["type"], msg["payload"]

                if t == "time_advanced":
                    print(f"\n  ⏰ Day {p['day']} · {p['slot']} ｜ 「{p['phase_name']}」")
                elif t == "event_triggered":
                    print(f"  📌 事件触发：{p['event_name']} → {p['outcome_name']}")
                    if p.get("resource_changes"):
                        for k, v in p["resource_changes"].items():
                            if v != 0:
                                print(f"     └ {k}: {v:+d}")
                elif t == "npc_action":
                    npc_count += 1
                    if p["npc_id"] in ("lin_chaoyin", "chen_yuanzhou", "chen_haisheng",
                                        "gu_chenzhou", "huiyuan", "xu_mingchuan",
                                        "jiang_xueyi", "xu_qing", "zhou_xingzhi",
                                        "ye_keke", "lin_yueqin"):
                        print(f"  💬 {p['npc_name']}：{p['action']}")
                elif t == "settlement_complete":
                    r = p["resource"]
                    print(f"\n  ✅ 结算完毕 ｜ 香火:{r['incense']} 神力:{r['divine_power']}/{r['divine_power_max']}")
                    advancing = False
            except asyncio.TimeoutError:
                advancing = False

        # ═══ 5. 对话 — 正午 ═══
        print_divider()
        print("  正午 · 土地公再次巡视")
        print_divider()

        msgs = await send_and_recv(ws, "chat", {
            "npc_id": "chen_yuanzhou",
            "message": "远舟，你复习得怎么样了？刚才看你从海边回来，和潮音聊过了吗？",
            "day": 5,
        }, target_type="npc_response")
        print_npc_says("陈远舟", msgs[0]["payload"]["response"])

        # ═══ 6. 推进时间 — 正午 → 夜晚 ═══
        print_divider()
        print("  时间推进 — 正午 → 夜晚")
        print_divider()

        await ws.send(json.dumps({"type": "advance_time"}))
        advancing = True
        had_event = False
        while advancing:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
                msg = json.loads(raw)
                t, p = msg["type"], msg["payload"]

                if t == "time_advanced":
                    print(f"\n  ⏰ Day {p['day']} · {p['slot']} ｜ 「{p['phase_name']}」")
                elif t == "event_triggered":
                    had_event = True
                    print(f"  📌 {p['event_name']} → {p['outcome_name']}")
                elif t == "npc_action":
                    # 只显示关键 NPC
                    if p["npc_id"] in ("lin_chaoyin", "chen_yuanzhou", "chen_haisheng",
                                        "gu_chenzhou", "lin_yueqin", "su_wan"):
                        print(f"  💬 {p['npc_name']}：{p['action']}")
                elif t == "settlement_complete":
                    if not had_event:
                        print("  （今晚比较平静，没有特别的事件发生）")
                    r = p["resource"]
                    print(f"\n  ✅ 结算完毕 ｜ 香火:{r['incense']} 神力:{r['divine_power']}/{r['divine_power_max']}")
                    advancing = False
            except asyncio.TimeoutError:
                advancing = False

        # ═══ 7. 夜晚对话 — 托梦 ═══
        print_divider()
        print("  夜晚 · 土地公托梦")
        print_divider()

        msgs = await send_and_recv(ws, "chat", {
            "npc_id": "lin_chaoyin",
            "message": "潮音，睡了吗？是我，土地公。我在你的梦里。关于钟塔下面的东西，你有什么想问我的吗？",
            "day": 5,
        }, target_type="npc_response")
        print_npc_says("林潮音（梦中）", msgs[0]["payload"]["response"])

        # ═══ 8. 存档 ═══
        print_divider()
        await send_and_recv(ws, "save_game", {"slot": 1}, target_type="game_saved")
        print("  💾 存档完成（槽位 1）")
        print_divider("═")
        print("  第一天结束。")
        print("  香火仍在，神力待回，小镇在梦中沉睡。")
        print_divider("═")

        await ws.close()


if __name__ == "__main__":
    asyncio.run(main())
