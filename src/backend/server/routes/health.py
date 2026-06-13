"""健康检查端点。"""

from fastapi import APIRouter

from src.backend.models.common import ok

router = APIRouter()


@router.get("/health", tags=["系统"])
async def health_check():
    """服务健康检查。"""
    return ok({"status": "ok", "service": "threads-of-fate"})
