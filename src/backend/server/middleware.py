"""全局中间件：异常捕获 + CORS + 请求日志。"""

import time
import traceback

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.backend.models.common import err


async def catch_all_exceptions(request: Request, call_next):
    """全局异常中间件 —— 将未捕获异常转为 ApiResponse 格式。"""
    try:
        return await call_next(request)
    except Exception:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=err("服务器内部错误，请重试"),
        )


def setup_middleware(app):
    """注册所有中间件。"""
    # CORS — 开发阶段允许所有来源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常捕获
    app.middleware("http")(catch_all_exceptions)
