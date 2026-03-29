"""FastAPI application entry point."""

import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response

from src.database.models import init_db

load_dotenv()

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
    yield
    logger.info("FastAPI server shutting down...")


app = FastAPI(
    title="人生草稿本 API",
    description="Life Draft Book — Interactive narrative game API",
    version="1.0.0",
    lifespan=lifespan,
)

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
from src.api.routers import (auth, character, collection, friends, gameplay,
                             games, images, music, presets, story)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(friends.router, prefix="/api/friends", tags=["Friends"])
app.include_router(games.router, prefix="/api/games", tags=["Games"])
app.include_router(character.router, prefix="/api/character", tags=["Character"])
app.include_router(presets.router, prefix="/api/presets", tags=["Presets"])
app.include_router(gameplay.router, prefix="/api/games", tags=["Gameplay"])
app.include_router(story.router, prefix="/api/games", tags=["Story"])
app.include_router(images.router, prefix="/api/images", tags=["Images"])
app.include_router(collection.router, prefix="/api/collection", tags=["Collection"])
app.include_router(music.router, prefix="/api", tags=["Music"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    from src.api.session_store import session_store

    return {
        "status": "ok",
        "active_sessions": session_store.active_count,
    }


from typing import Optional

# ---- Client-side log collector ----
from pydantic import BaseModel

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
