"""Dependency injection for FastAPI endpoints."""

import logging
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.api.services.session_service import session_service
from src.api.session_store import GameLoopSession
from src.database.singletons import get_game_db, get_user_manager

logger = logging.getLogger(__name__)

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
# H-04: Token 有效期从 30 天改为 60 分钟
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 60 分钟
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 新增 refresh token 过期时间
JWT_EXPIRE_HOURS = ACCESS_TOKEN_EXPIRE_MINUTES / 60  # 保持向后兼容

# Security scheme (optional bearer token)
_bearer = HTTPBearer(auto_error=False)

# Re-export singletons for backward compatibility
# These functions are now defined in src.database.singletons
# to break the circular dependency with session_service

# Alias for backward compatibility - external code may use get_db()
get_db = get_game_db


# ---- JWT helpers ----


def create_token(user_id: int) -> str:
    """Create a JWT token for a user."""
    from datetime import datetime, timedelta

    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)  # type: ignore[no-any-return]


def decode_token(token: str) -> Optional[int]:
    """Decode a JWT token and return user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        return int(user_id_str)
    except (JWTError, ValueError):
        return None


# ---- FastAPI dependencies ----


def _extract_token(
    request: Optional[Request], credentials: Optional[HTTPAuthorizationCredentials]
) -> Optional[str]:
    """
    从Cookie或Authorization header中提取token。

    ★ 优先级：Cookie > Authorization header
    这样可以支持iPad Safari等设备上的持久化认证。
    """
    # 1. 优先从Cookie读取
    if request is not None:
        cookie_token = request.cookies.get("auth_token")
        if cookie_token:
            return cookie_token

    # 2. 如果Cookie没有，从Authorization header读取
    if credentials is not None:
        return credentials.credentials

    return None


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[int]:
    """
    Extract user_id from Bearer token or Cookie.
    Returns None if no token or invalid token (non-throwing).

    ★ 优先从Cookie读取token，支持iPad Safari等设备上的持久化
    """
    token = _extract_token(request, credentials)
    if token is None:
        return None
    user_id = decode_token(token)
    return user_id


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> int:
    """
    Extract user_id from Bearer token or Cookie. Raises 401 if missing or invalid.

    ★ 优先从Cookie读取token，支持iPad Safari等设备上的持久化
    """
    token = _extract_token(request, credentials)

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


def get_game_session(
    game_id: int,
    user_id: Optional[int] = None,
) -> GameLoopSession:
    """
    Get an active GameLoop session for the given game.
    Auto-restores from database if not in memory.
    Raises 404 if game not found.
    """
    return session_service.get_or_restore(game_id, user_id)
