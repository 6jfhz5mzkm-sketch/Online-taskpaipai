"""FastAPI 应用入口。

对齐 NestJS backend/src/main.ts:
- CORS、全局路由前缀 /api(/health 除外)、Swagger /docs + /redoc
- 统一响应 {code, message, data} + 全局异常处理(对齐 ResponseInterceptor / AllExceptionsFilter)
"""
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings, validate_startup_settings
from app.core.error_handlers import register_exception_handlers
from app.core.response import success

settings = get_settings()
logger = logging.getLogger("api")


# ---- 日志配置(#PB-23-R5):`api` 命名空间默认 INFO、幂等、只输出到标准错误 ----
# 背景:全仓此前无 basicConfig(0 命中)⇒ `api` 的 record 只落到 `logging.lastResort`(仅 WARNING 及以上),
# INFO 业务日志(验证码已下发 / 手机号登录成功 / 手机号自注册)在 dev(文件重定向)与 prod(systemd/journald)里都被丢弃。
LOG_HANDLER_MARKER = "_api_stream_handler"


def _configure_logging() -> None:
    """给 `api` logger 挂一个**幂等**的 StreamHandler;级别取 `LOG_LEVEL`(默认 INFO)。

    - **幂等**:handler 上带标记属性,已存在即跳过 —— 重复 import / 多 worker / 测试重复导入只挂一次;
    - **只动 `api`**:不碰 uvicorn 自身 logger(uvicorn/uvicorn.error/uvicorn.access)与第三方库,不开 DEBUG;
    - **落盘形态**:输出到 stderr —— dev 用重定向即落文件;prod 由 systemd 单元捕获进 journald(`journalctl -u <service>`);
    - **保留 propagate**(默认 True):pytest 的 `caplog` 依赖向 root 传播;当前 root 无 handler,故不会重复输出。
    """
    api_logger = logging.getLogger("api")
    level = getattr(logging, (settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
    api_logger.setLevel(level)
    if not any(getattr(handler, LOG_HANDLER_MARKER, False) for handler in api_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        setattr(handler, LOG_HANDLER_MARKER, True)
        api_logger.addHandler(handler)


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动期 fail-fast:非 dev 环境密钥/登录模式不合规立即拒绝启动(部署上线前必做清单 6b / SEC-06)。"""
    validate_startup_settings(settings)
    logger.info(f"启动校验通过: LOGIN_MODE={settings.LOGIN_MODE} DEBUG={settings.DEBUG} docs={'on' if settings.DEBUG else 'off'}")
    yield


def create_app() -> FastAPI:
    # 文档端点:生产(DEBUG=False)关闭,对齐 NestJS main.ts:47(仅非生产环境注册 Swagger),
    # 避免对外暴露完整接口清单;dev 保持 /docs + /redoc + /openapi.json 可访问。
    docs_enabled = settings.DEBUG
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        docs_url=settings.API_DOCS_URL if docs_enabled else None,
        redoc_url=settings.API_REDOC_URL if docs_enabled else None,
        openapi_url=settings.OPENAPI_URL if docs_enabled else None,
        lifespan=lifespan,
        description="京东拍拍二手 · 商家任务体系后端接口文档(Python/FastAPI,迁移自 NestJS)",
    )

    # ---- CORS(与 NestJS enableCors 对齐;生产收紧为具体域名) ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 业务路由(挂 /api 前缀) ----
    app.include_router(api_router)

    # ---- 统一错误出口(业务异常/参数校验/HTTP 异常/未知异常;见 app/core/error_handlers.py) ----
    register_exception_handlers(app)

    # ---- 健康检查(不带 /api 前缀,与 NestJS main.ts exclude 一致) ----
    @app.get("/health", tags=["系统"], summary="健康检查")
    def health() -> dict[str, Any]:
        return success({"status": "ok"})

    return app


app = create_app()
