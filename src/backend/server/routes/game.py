"""游戏核心端点：新游戏、状态查询。"""

from fastapi import APIRouter

from src.backend.models.common import GameStateResponse, ok, err
from src.backend.server.state import get_manager, init_manager, is_initialized, reset

router = APIRouter()


@router.post("/new-game", tags=["游戏"])
async def new_game():
    """创建新游戏，加载 Demo NPC，返回初始状态。"""
    if is_initialized():
        # 已有游戏在运行，先重置
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
