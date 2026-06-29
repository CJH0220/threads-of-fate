"""游戏核心端点：新游戏、状态查询、NPC 对话、存读档。"""

from pydantic import BaseModel, Field
from fastapi import APIRouter

from src.backend.models.common import GameStateResponse, ok, err
from src.backend.server.state import (
    get_session, get_manager, init_session, load_session,
    is_initialized, reset,
)

router = APIRouter()


# ── 请求模型 ──

class ChatRequest(BaseModel):
    message: str = Field(..., description="玩家说的话", min_length=1)
    day: int = Field(default=1, ge=1, le=60, description="当前天数")


# ── 游戏端点 ──

@router.post("/new-game", tags=["游戏"])
async def new_game():
    """创建新游戏，从 CSV 加载 NPC，返回初始状态。"""
    if is_initialized():
        reset()

    session = init_session()
    snapshots = session.agents.all_snapshots()

    state = GameStateResponse(
        day=session.time.day,
        slot=session.time.slot.value,
        incense=session.resource.incense,
        divine_power=session.resource.divine_power_max,
        yin_de=session.resource.yin_de,
        yang_de=session.resource.yang_de,
        npcs=snapshots.npcs,
        npc_total=snapshots.total,
    )
    return ok(state.model_dump())


@router.get("/state", tags=["游戏"])
async def get_state():
    """查询当前游戏完整状态。"""
    if not is_initialized():
        return err("尚未初始化游戏，请先调用 POST /new-game")

    session = get_session()
    snapshots = session.agents.all_snapshots()

    state = GameStateResponse(
        day=session.time.day,
        slot=session.time.slot.value,
        incense=session.resource.incense,
        divine_power=session.resource.divine_power_max,
        yin_de=session.resource.yin_de,
        yang_de=session.resource.yang_de,
        npcs=snapshots.npcs,
        npc_total=snapshots.total,
    )
    return ok(state.model_dump())


@router.post("/chat/{npc_id}", tags=["游戏"])
async def chat_with_npc(npc_id: str, req: ChatRequest):
    """与指定 NPC 对话。"""
    if not is_initialized():
        return err("尚未初始化游戏，请先调用 POST /new-game")

    manager = get_manager()
    agent = manager.get(npc_id)
    if agent is None:
        return err(f"NPC 不存在: {npc_id}")

    reply = await agent.respond(
        context=req.message,
        speaker_name="土地公",
        current_day=req.day,
    )
    return ok({
        "npc_id": agent.npc_id,
        "npc_name": agent.name,
        "response": reply,
    })


# ── 存读档端点 ──

@router.post("/save/{slot}", tags=["存档"])
async def save_game(slot: int):
    """保存游戏到指定槽位（0=自动档, 1-3=手动档）。"""
    if not is_initialized():
        return err("尚未初始化游戏")
    if slot not in (0, 1, 2, 3):
        return err(f"无效的槽位: {slot}，应为 0-3")

    from src.backend.storage import JsonStorage
    storage = JsonStorage()
    session = get_session()
    await storage.save(slot, session.to_dict())
    return ok({"slot": slot, "day": session.time.day})


@router.post("/load/{slot}", tags=["存档"])
async def load_game(slot: int):
    """从指定槽位加载游戏。"""
    if slot not in (0, 1, 2, 3):
        return err(f"无效的槽位: {slot}，应为 0-3")

    from src.backend.storage import JsonStorage
    from src.backend.engine.game_session import GameSession

    storage = JsonStorage()
    try:
        data = await storage.load(slot)
    except FileNotFoundError:
        return err(f"存档槽位 {slot} 为空")

    session = GameSession.from_dict(data)
    load_session(session)

    snapshots = session.agents.all_snapshots()
    state = GameStateResponse(
        day=session.time.day,
        slot=session.time.slot.value,
        incense=session.resource.incense,
        divine_power=session.resource.divine_power_max,
        yin_de=session.resource.yin_de,
        yang_de=session.resource.yang_de,
        npcs=snapshots.npcs,
        npc_total=snapshots.total,
    )
    return ok(state.model_dump())


@router.get("/saves", tags=["存档"])
async def list_saves():
    """列出所有存档。"""
    from src.backend.storage import JsonStorage
    storage = JsonStorage()
    saves = await storage.list_saves()
    return ok([{
        "slot": s.slot,
        "day": s.day,
        "timestamp": s.timestamp,
        "exists": s.exists,
    } for s in saves])


@router.delete("/saves/{slot}", tags=["存档"])
async def delete_save(slot: int):
    """删除指定存档。"""
    if slot not in (0, 1, 2, 3):
        return err(f"无效的槽位: {slot}，应为 0-3")

    from src.backend.storage import JsonStorage
    storage = JsonStorage()
    await storage.delete(slot)
    return ok({"slot": slot, "deleted": True})
