"""Friends router — friend requests, list, remove."""

import logging
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_current_user, get_user_manager
from src.api.schemas import (FriendInfo, FriendRequestCreate,
                             FriendRequestInfo, FriendRequestRespond,
                             MessageResponse)

logger = logging.getLogger(__name__)
router = APIRouter()


def _serialize_timestamp(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


@router.post("/request", response_model=MessageResponse)
async def send_friend_request(
    req: FriendRequestCreate,
    user_id: int = Depends(get_current_user),
):
    """Send a friend request to another user by public_id."""
    um = get_user_manager()
    result = um.send_friend_request(user_id, req.to_public_id)
    # Handle both str and dict return types for compatibility
    msg = result.get("message", "") if isinstance(result, dict) else str(result)
    if "error" in msg.lower() or "不能" in msg or "已经" in msg:
        raise HTTPException(status_code=400, detail=msg)
    return MessageResponse(message=msg)


@router.post("/respond", response_model=MessageResponse)
async def respond_to_friend_request(
    req: FriendRequestRespond,
    user_id: int = Depends(get_current_user),
):
    """Accept or reject a friend request."""
    um = get_user_manager()
    result = um.respond_to_friend_request(user_id, req.request_id, req.accept)
    # Handle both str and dict return types for compatibility
    msg = result.get("message", "") if isinstance(result, dict) else str(result)
    if "error" in msg.lower() or "无权" in msg:
        raise HTTPException(status_code=400, detail=msg)
    return MessageResponse(message=msg)


@router.get("", response_model=List[FriendInfo])
async def get_friends(user_id: int = Depends(get_current_user)):
    """Get current user's friend list."""
    um = get_user_manager()
    friends = um.get_friends(user_id)
    return [
        FriendInfo(
            user_id=f["user_id"],
            public_id=f["public_id"],
            display_name=f.get("display_name"),
        )
        for f in friends
    ]


@router.get("/requests", response_model=List[FriendRequestInfo])
async def get_pending_requests(user_id: int = Depends(get_current_user)):
    """Get pending friend requests for current user."""
    um = get_user_manager()
    requests = um.get_pending_friend_requests(user_id)
    return [
        FriendRequestInfo(
            request_id=r["request_id"],
            from_user=FriendInfo(
                user_id=r["from_user_id"],
                public_id=r["from_public_id"],
                display_name=r.get("from_display_name"),
            ),
            created_at=_serialize_timestamp(r.get("created_at")),
        )
        for r in requests
    ]


@router.delete("/{friend_user_id}", response_model=MessageResponse)
async def remove_friend(
    friend_user_id: int,
    user_id: int = Depends(get_current_user),
):
    """Remove a friend."""
    um = get_user_manager()
    success = um.remove_friend(user_id, friend_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Friend not found")
    return MessageResponse(message="Friend removed")
