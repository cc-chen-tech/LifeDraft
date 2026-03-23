"""Auth router — register, login, me, logout."""

import logging
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse

from src.api.deps import (
    JWT_EXPIRE_HOURS,
    create_token,
    get_current_user,
    get_user_manager,
)
from src.api.schemas import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Cookie配置
COOKIE_NAME = "auth_token"
COOKIE_MAX_AGE = JWT_EXPIRE_HOURS * 3600  # 转换为秒
COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "false").lower() == "true"
)  # 生产环境设为true
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # lax/strict/none


def _set_auth_cookie(response: Response, token: str) -> None:
    """设置认证Cookie"""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,  # 防止XSS攻击
        secure=COOKIE_SECURE,  # HTTPS only in production
        samesite=COOKIE_SAMESITE,  # CSRF protection
        path="/",  # 全站可用
    )


def _clear_auth_cookie(response: Response) -> None:
    """清除认证Cookie"""
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
    )


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    """Register a new user and return JWT token (both in body and Cookie)."""
    um = get_user_manager()
    try:
        user, private_id = um.create_user(req.display_name)
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    token = create_token(user.user_id)

    # 创建响应并设置Cookie
    response = JSONResponse(
        content=AuthResponse(
            token=token,
            user=UserInfo(
                user_id=user.user_id,
                public_id=user.public_id,
                display_name=user.display_name,
                private_id=private_id,  # Only returned on register!
            ),
        ).model_dump()
    )
    _set_auth_cookie(response, token)

    return response


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Login with private_id and return JWT token (both in body and Cookie)."""
    um = get_user_manager()
    user = um.login_by_private_id(req.private_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid private ID",
        )

    token = create_token(user.user_id)

    # 创建响应并设置Cookie
    response = JSONResponse(
        content=AuthResponse(
            token=token,
            user=UserInfo(
                user_id=user.user_id,
                public_id=user.public_id,
                display_name=user.display_name,
            ),
        ).model_dump()
    )
    _set_auth_cookie(response, token)

    return response


@router.get("/me", response_model=UserInfo)
async def get_me(user_id: int = Depends(get_current_user)):
    """Get current user info from JWT token."""
    um = get_user_manager()
    user = um.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserInfo(
        user_id=user.user_id,
        public_id=user.public_id,
        display_name=user.display_name,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    current_user: int = Depends(get_current_user),  # H-05: 登出需认证
):
    """
    Logout — clear the auth Cookie and instruct client to discard token.

    ★ 同时清除Cookie和提示客户端清除localStorage
    ★ 需要认证才能登出
    """
    _clear_auth_cookie(response)
    return MessageResponse(message="Logged out successfully")
