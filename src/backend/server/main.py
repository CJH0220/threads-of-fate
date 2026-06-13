"""FastAPI 应用入口。

启动方式：
    uvicorn src.backend.server.main:app --reload --host 0.0.0.0 --port 8000

访问：
    http://localhost:8000/docs      — OpenAPI 自动文档
    http://localhost:8000/health    — 健康检查
"""

from fastapi import FastAPI

from .middleware import setup_middleware
from .routes.health import router as health_router
from .routes.game import router as game_router


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    app = FastAPI(
        title="命运的织线 — 后端 API",
        description="归潮镇 NPC 命运编织引擎",
        version="0.1.0",
    )

    # 注册中间件
    setup_middleware(app)

    # 注册路由
    app.include_router(health_router)
    app.include_router(game_router)

    return app


app = create_app()
