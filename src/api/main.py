"""FastAPI application entry point."""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

from config.settings import (SENTRY_DSN, SENTRY_ENVIRONMENT,
                             SENTRY_TRACES_SAMPLE_RATE)
from src.api.routers import (auth, character, collection, gameplay, games,
                             images, presets, story,
                             voice_reading)
from src.database.models import init_db
from src.api.input_limits import PUBLIC_INPUT_LIMITS

load_dotenv()

# Initialize Sentry (before app creation)
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,  # 不发送用户隐私数据
    )

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("=" * 50)
    logger.info("FastAPI server starting...")
    init_db()
    logger.info("Database initialized")

    from src.services.portrait_image_jobs import recover_pending_portrait_image_jobs

    recovered_portrait_job_ids = recover_pending_portrait_image_jobs()
    if recovered_portrait_job_ids:
        logger.info("Scheduled durable portrait jobs count=%s", len(recovered_portrait_job_ids))

    import asyncio

    drain_task: Optional[asyncio.Task[None]] = None
    try:
        from src.api.routers.images import _drain_pending_events

        drain_task = asyncio.create_task(_drain_pending_events())
    except ImportError:
        logger.info("Scene image SSE drain task is not configured")

    yield

    if drain_task:
        drain_task.cancel()
    logger.info("FastAPI server shutting down...")

    # B-01/B-02: 关闭全局线程池，防止资源泄漏
    from src.api.routers.gameplay.sse_helpers import shutdown_sse_thread_pool
    from src.services.image_service import shutdown_image_thread_pool

    shutdown_sse_thread_pool(wait=False, prevent_new_background_jobs=True)
    shutdown_image_thread_pool(wait=False)
    logger.info("Global thread pools shut down")


app = FastAPI(
    title="人生草稿本 API",
    description="Life Draft Book — Interactive narrative game API",
    version="1.0.0",
    lifespan=lifespan,
)


def custom_openapi():
    """Publish input limits beside ordinary JSON Schema field constraints."""

    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["x-input-limits"] = dict(PUBLIC_INPUT_LIMITS)
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

# CORS — allow Next.js dev server, Streamlit, and LAN access
# ★ 必须使用 allow_credentials=True 来支持 Cookie 认证
# ★ 不能使用 allow_origins=["*"]，必须明确指定 origin


def get_allowed_origins():
    """获取允许的CORS origin列表"""
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]
    # 从环境变量添加额外的origin（用于局域网访问）
    extra_origins = os.getenv("CORS_ORIGINS", "")
    if extra_origins:
        origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])
    return origins


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,  # ★ 必须为 True 才能发送 Cookie
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # H-01: 收紧 methods
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
    ],  # H-01: 收紧 headers
)


# M-05: HTTP 安全头中间件
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws: wss:"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# M-06: 操作审计日志中间件
class AuditLogMiddleware(BaseHTTPMiddleware):
    """记录所有 API 请求的审计日志"""

    async def dispatch(self, request: StarletteRequest, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # 跳过健康检查和静态资源的日志
        path = request.url.path
        if not path.startswith("/api/health") and not path.startswith("/_next"):
            logger.info(
                "API Request",
                extra={
                    "method": request.method,
                    "path": path,
                    "status": response.status_code,
                    "duration_ms": round(duration * 1000, 2),
                    "client_ip": request.client.host if request.client else "unknown",
                },
            )
        return response


app.add_middleware(AuditLogMiddleware)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Add actionable measurements to request length failures without echoing text."""

    details = []
    for raw_error in exc.errors():
        error_type = raw_error.get("type")
        ctx = dict(raw_error.get("ctx") or {})
        if error_type in {"string_too_long", "json_too_large"}:
            error = {
                key: value
                for key, value in raw_error.items()
                if key not in {"input", "url"}
            }
        else:
            error = dict(raw_error)
        if error_type == "string_too_long":
            input_value = raw_error.get("input")
            error.update(
                {
                    "field": str(raw_error.get("loc", ("",))[-1]),
                    "limit": int(ctx["max_length"]),
                    "actual_length": len(input_value) if isinstance(input_value, str) else None,
                    "unit": "characters",
                }
            )
        elif error_type == "json_too_large":
            error.update(
                {
                    "field": str(raw_error.get("loc", ("",))[-1]),
                    "limit": int(ctx["limit"]),
                    "actual_length": int(ctx["actual_length"]),
                    "unit": str(ctx.get("unit", "bytes")),
                }
            )
        details.append(error)
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": details}))


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # H-02: 异常信息隐藏
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    if os.getenv("ENVIRONMENT", "production") == "development":
        detail = str(exc)
    else:
        detail = "Internal server error. Please try again later."
    return JSONResponse(
        status_code=500,
        content={"detail": detail},
    )


# ---- Register routers ----
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(games.router, prefix="/api/games", tags=["Games"])
app.include_router(character.router, prefix="/api/character", tags=["Character"])
app.include_router(presets.router, prefix="/api/presets", tags=["Presets"])
app.include_router(gameplay.router, prefix="/api/games", tags=["Gameplay"])
app.include_router(story.router, prefix="/api/games", tags=["Story"])
app.include_router(images.router, prefix="/api/images", tags=["Images"])
app.include_router(collection.router, prefix="/api/collection", tags=["Collection"])
app.include_router(voice_reading.router, prefix="/api/voice-reading", tags=["VoiceReading"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from config.feature_flags import get_feature
    from src.api.session_store import session_store
    from src.services.story_tts_provider import build_story_tts_provider

    tts_metadata = build_story_tts_provider().metadata()

    return {
        "status": "ok",
        "active_sessions": session_store.active_count,
        "capabilities": {
            "daily_timeline_v2": get_feature("daily_timeline_v2"),
            "daily_recommended_prefetch": get_feature(
                "daily_recommended_prefetch"
            ),
            "daily_recommended_tts_prefetch": get_feature(
                "daily_recommended_tts_prefetch"
            ),
            "tts_provider": tts_metadata.provider,
            "tts_provider_available": tts_metadata.backend_audio_enabled,
            "tts_audio_transport": "range_v2",
            "music_runtime_enabled": False,
        },
    }


client_logger = logging.getLogger("client")


class ClientLogEntry(BaseModel):
    level: str = "error"  # error / warn / info
    message: str
    context: Optional[str] = None  # e.g. "sse", "api", "global"
    url: Optional[str] = None  # page URL on client
    ua: Optional[str] = None  # User-Agent (auto-filled from header)


@app.post("/api/client-log")
async def client_log(entry: ClientLogEntry, request: Request):
    """Receive and log client-side errors — useful for debugging mobile issues."""
    ua = entry.ua or request.headers.get("user-agent", "unknown")
    ip = request.client.host if request.client else "unknown"
    tag = f"[{entry.context or 'client'}]" if entry.context else "[client]"
    log_line = f"{tag} {entry.message}  | page={entry.url} ip={ip} ua={ua}"

    lvl = entry.level.lower()
    if lvl == "warn":
        client_logger.warning(log_line)
    elif lvl == "info":
        client_logger.info(log_line)
    else:
        client_logger.error(log_line)

    return {"ok": True}
