"""游戏核心端点：新游戏、状态查询、NPC 对话。"""

from pydantic import BaseModel, Field
from fastapi import APIRouter

from src.backend.models.common import GameStateResponse, ok, err
from src.backend.server.state import get_manager, init_manager, is_initialized, reset

router = APIRouter()


# ── 请求模型 ──

class ChatRequest(BaseModel):
    message: str = Field(..., description="玩家说的话", min_length=1)
    day: int = Field(default=1, ge=1, le=60, description="当前天数")


# ── 端点 ──

@router.post("/new-game", tags=["游戏"])
async def new_game():
    """创建新游戏，从 CSV 加载 NPC，返回初始状态。"""
    if is_initialized():
        reset()

    manager = init_manager()
    snapshots = manager.all_snapshots()

    state = GameStateResponse(
        day=1,
        slot="morning",
        incense=50,
        divine_power=10,
        yin_de=0,
        yang_de=0,
        npcs=snapshots.npcs,
        npc_total=snapshots.total,
    )
    return ok(state.model_dump())


@router.get("/state", tags=["游戏"])
async def get_state():
    """查询当前游戏完整状态。"""
    if not is_initialized():
        return err("尚未初始化游戏，请先调用 POST /new-game")

    manager = get_manager()
    snapshots = manager.all_snapshots()

    state = GameStateResponse(
        day=1,
        slot="morning",
        incense=50,
        divine_power=10,
        yin_de=0,
        yang_de=0,
        npcs=snapshots.npcs,
        npc_total=snapshots.total,
    )
    return ok(state.model_dump())


@router.post("/chat/{npc_id}", tags=["游戏"])
async def chat_with_npc(npc_id: str, req: ChatRequest):
    """与指定 NPC 对话。

    Args:
        npc_id: NPC 标识，如 lin_chaoyin
        req: 玩家消息和当前天数

    Returns:
        NPC 的 LLM 生成回应
    """
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
