from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.envelope import fail
from api.routes import router as api_router
from api.web_socket import router as ws_router
from core.config import config
from core.module_registry import discover_modules
from core.scheduler import Scheduler
from storage.db import db

logging.basicConfig(
    level=getattr(logging, config.app.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("main")

_registry: dict = {}
_scheduler: Scheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Registry module (chạy 1 lần khi khởi động)
    global _registry, _scheduler
    _registry = discover_modules()

    # 2. DB: tạo bảng chung + bảng riêng module (module đã được import bởi registry)
    db.create_all()

    # 3. Token nội bộ (sinh ngẫu nhiên lúc cài đặt nếu chưa có)
    token = config.ensure_local_token()
    logger.info("Local token: %s", token[:8] + "..." if token else "(none)")

    # 4. Scheduler tự động theo manifest.default_schedule
    _scheduler = Scheduler(_registry)
    _scheduler.start()
    logger.info("Backend sẵn sàng: %d module đã đăng ký", len(_registry))

    yield

    if _scheduler:
        _scheduler.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="Security Audit Tool", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.app.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(ws_router)

    # Gắn router riêng từng module (nếu module khai báo)
    discovered = discover_modules()
    for manifest in discovered.values():
        if manifest.router is not None:
            app.include_router(manifest.router)

    register_error_handlers(app)
    return app


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and ("code" in detail and "message" in detail):
            return JSONResponse(status_code=exc.status_code, content=fail(detail["code"], detail["message"]))
        return JSONResponse(
            status_code=exc.status_code or 500,
            content=fail("HTTP_ERROR", str(detail) if detail else "Đã có lỗi xảy ra."),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=fail("VALIDATION_ERROR", "Dữ liệu gửi lên không hợp lệ."),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Lỗi không được xử lý: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=fail("INTERNAL_ERROR", "Lỗi máy chủ nội bộ."),
        )


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host=config.app.host, port=config.app.port, log_level=config.app.log_level)