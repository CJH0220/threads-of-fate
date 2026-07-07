"""后端冒烟测试脚本。

在 Godot 前端之外，独立验证后端 HTTP + WebSocket 通路是否正常。
用于排除"到底是前端问题还是后端问题"。

用法：
    1. 先启动后端：uvicorn src.backend.server.main:app --host 127.0.0.1 --port 8000
    2. 运行本脚本：python tools/smoke_test_ws.py

依赖：
    pip install websockets requests

预期输出（正常情况）：
    [1/3] health          → success=True
    [2/3] POST /new-game  → success=True, npc_total=N
    [3/3] WS advance_time → 收到 time_advanced / event_triggered / settlement_complete
    ✅ 后端 HTTP + WS 通路正常，前端卡死问题定位在 Godot 端。
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

try:
    import requests
    import websockets
except ImportError:
    print("缺少依赖，请先执行: pip install websockets requests")
    sys.exit(1)


BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/game"

# 单条 WS 消息最长等待时间（秒），防止脚本永远挂死
WS_RECV_TIMEOUT = 30.0
# advance_time 整体流程最长等待（秒）
ADVANCE_TIMEOUT = 60.0


def _print(step: str, msg: str) -> None:
    print(f"[{step}] {msg}", flush=True)


def check_health() -> bool:
    """健康检查 —— 复现前端 Bug A 的对照。"""
    _print("1/3", f"GET {BASE_URL}/health ...")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
    except requests.RequestException as e:
        _print("1/3", f"❌ 请求失败: {e}")
        return False

    if r.status_code != 200:
        _print("1/3", f"❌ HTTP {r.status_code}: {r.text}")
        return False

    payload = r.json()
    ok = bool(payload.get("success")) and payload.get("data", {}).get("status") == "ok"
    _print("1/3", f"响应: {payload}")
    _print("1/3", "✅ 健康检查通过" if ok else "❌ 健康检查返回值异常")
    return ok


def new_game() -> bool:
    """创建新游戏。"""
    _print("2/3", f"POST {BASE_URL}/new-game ...")
    try:
        r = requests.post(f"{BASE_URL}/new-game", timeout=30)
    except requests.RequestException as e:
        _print("2/3", f"❌ 请求失败: {e}")
        return False

    if r.status_code != 200:
        _print("2/3", f"❌ HTTP {r.status_code}: {r.text}")
        return False

    payload = r.json()
    success = bool(payload.get("success"))
    data = payload.get("data") or {}
    _print("2/3", f"success={success}, day={data.get('day')}, npc_total={data.get('npc_total')}")

    if not success:
        _print("2/3", f"❌ error: {payload.get('error')}")
        return False

    _print("2/3", "✅ 新游戏创建成功")
    return True


async def _recv_json(ws) -> dict:
    """限时接收一条 JSON 消息。"""
    raw = await asyncio.wait_for(ws.recv(), timeout=WS_RECV_TIMEOUT)
    return json.loads(raw)


async def advance_time_over_ws() -> bool:
    """通过 WebSocket 推进一个时段，验证 time_advanced → event_triggered → settlement_complete 全链路。"""
    _print("3/3", f"WS {WS_URL} 连接中 ...")
    try:
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            _print("3/3", "✅ WS 已连接，发送 advance_time")

            await ws.send(json.dumps({
                "type": "advance_time",
                "request_id": f"smoke_{int(time.time())}",
                "timestamp": time.time(),
            }))

            got_time_advanced = False
            got_settlement = False
            events_count = 0
            npc_actions_count = 0

            deadline = time.time() + ADVANCE_TIMEOUT
            while time.time() < deadline:
                try:
                    msg = await _recv_json(ws)
                except asyncio.TimeoutError:
                    _print("3/3", "❌ WS 接收超时 (单条 %.0fs 未到)" % WS_RECV_TIMEOUT)
                    return False

                mtype = msg.get("type", "?")
                payload = msg.get("payload", {})

                # 精简日志
                if mtype == "time_advanced":
                    got_time_advanced = True
                    _print("3/3", f"← time_advanced day={payload.get('day')} slot={payload.get('slot')} week={payload.get('week')}")
                elif mtype == "event_triggered":
                    events_count += 1
                    _print("3/3", f"← event_triggered #{events_count} name={payload.get('event_name')} outcome={payload.get('outcome_name')}")
                elif mtype == "npc_actions_start":
                    _print("3/3", "← npc_actions_start")
                elif mtype == "npc_action":
                    npc_actions_count += 1
                    if npc_actions_count <= 3:
                        _print("3/3", f"← npc_action {payload.get('npc_name')}")
                elif mtype == "settlement_complete":
                    got_settlement = True
                    _print("3/3", f"← settlement_complete resource={payload.get('resource')}")
                    break
                elif mtype == "error":
                    _print("3/3", f"❌ 后端错误: {payload}")
                    return False
                else:
                    _print("3/3", f"← 未识别类型: {mtype}")

            if not got_settlement:
                _print("3/3", f"❌ {ADVANCE_TIMEOUT:.0f}s 内未收到 settlement_complete")
                return False

            _print("3/3", f"✅ 全链路通过（events={events_count} npc_actions={npc_actions_count}）")
            return got_time_advanced and got_settlement

    except (websockets.WebSocketException, OSError) as e:
        _print("3/3", f"❌ WS 异常: {e}")
        return False


async def main() -> int:
    print("=" * 60)
    print("后端冒烟测试 —— HTTP + WebSocket 通路验证")
    print("=" * 60)

    if not check_health():
        print()
        print("❌ 健康检查失败：请确认后端已启动 (uvicorn src.backend.server.main:app)")
        return 1

    print()
    if not new_game():
        print()
        print("❌ 新游戏创建失败。")
        return 1

    print()
    if not await advance_time_over_ws():
        print()
        print("❌ WS 推进时段失败。")
        return 1

    print()
    print("=" * 60)
    print("✅ 后端 HTTP + WS 通路完全正常。")
    print("   如果 Godot 前端仍卡死，问题在前端 —— 请检查 Godot 编辑器 Output。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
