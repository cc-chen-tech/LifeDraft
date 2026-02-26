"""Games router — CRUD for game sessions (create, list, load, save, delete)."""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException

from src.game.game_loop import GameLoop
from src.api.deps import (
    get_db, get_current_user, get_current_user_optional,
)
from src.api.session_store import session_store
from src.api.services.session_service import session_service
from src.utils.language import detect_language_from_state
from src.api.schemas import (
    CreateGameRequest, GameListItem, GameStateResponse,
    SaveGameResponse, MessageResponse,
    # 时间回溯存档系统
    CreateSavePointRequest, SavePointItem, SavePointListResponse,
    StateSnapshotItem, StateTimelineResponse,
)
from src.game.game_initializer import GameInitializer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=GameStateResponse, status_code=201)
async def create_game(
    req: CreateGameRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Create a new game from character settings."""
    db = get_db()
    try:
        initializer = GameInitializer(game_db=db, language=req.language)
        game_loop, game_id = initializer.initialize_game_from_settings(
            character_settings=req.character_settings,
            player_name=req.player_name,
            life_vision=req.life_vision,
            user_id=user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Store in session
    session_store.put(game_id, game_loop, user_id=user_id, language=req.language)

    # ★ 服务端会话管理：记录活跃游戏
    if user_id:
        db.set_active_game(user_id, game_id)

    state = game_loop.get_state()
    return GameStateResponse(
        game_id=game_id,
        player_state=state.to_dict() if state else {},
        progress=game_loop.get_progress(),
        round_info=game_loop.get_round_info(),
        current_event=game_loop.current_event.model_dump() if game_loop.current_event else None,
    )


@router.get("", response_model=List[GameListItem])
async def list_games(
    limit: int = 50,
    user_id: int = Depends(get_current_user),
):
    """List saved games for the current user."""
    db = get_db()
    games = db.list_saved_games(user_id, limit=limit)
    return [
        GameListItem(
            game_id=g["game_id"],
            player_name=g.get("player_name", ""),
            week=g.get("week", 0),
            age=g.get("age", 22),
            created_at=g["created_at"].isoformat() if g.get("created_at") else None,
            updated_at=g["updated_at"].isoformat() if g.get("updated_at") else None,
            has_progress=g.get("has_progress", False),
        )
        for g in games
    ]


@router.get("/active", response_model=GameStateResponse)
async def get_active_game(
    user_id: int = Depends(get_current_user),
):
    """
    ★ 获取用户当前活跃的游戏并自动恢复。
    
    用于iPad等设备上localStorage失效时的会话恢复。
    如果用户有活跃游戏，自动加载并返回游戏状态。
    如果没有活跃游戏，返回404。
    """
    db = get_db()
    active_game_id = db.get_active_game(user_id)
    
    if not active_game_id:
        raise HTTPException(status_code=404, detail="No active game found")
    
    logger.info(f"[get_active_game] Found active game for user {user_id}: game_id={active_game_id}")
    
    # 加载游戏状态
    state_data = db.load_saved_game(active_game_id, user_id)
    if state_data is None:
        # 游戏已被删除，清除活跃引用
        db.clear_active_game(user_id)
        raise HTTPException(status_code=404, detail="Active game no longer exists")
    
    # 确定语言
    language = detect_language_from_state(state_data)
    
    # 创建 GameLoop 并加载状态
    game_loop = GameLoop(language=language)
    game_loop.load_game(state_data)
    
    # 存储到会话
    session_store.put(active_game_id, game_loop, user_id=user_id, language=language)
    
    state = game_loop.get_state()
    return GameStateResponse(
        game_id=active_game_id,
        player_state=state.to_dict() if state else {},
        progress=game_loop.get_progress(),
        round_info=game_loop.get_round_info(),
        current_event=game_loop.current_event.model_dump() if game_loop.current_event else None,
    )


@router.get("/{game_id}", response_model=GameStateResponse)
async def load_game(
    game_id: int,
    user_id: int = Depends(get_current_user),
):
    """Load a saved game and create a GameLoop session."""
    db = get_db()
    state_data = db.load_saved_game(game_id, user_id)
    if state_data is None:
        raise HTTPException(status_code=404, detail="Game not found or not owned by user")

    # Determine language from state
    language = detect_language_from_state(state_data)

    # Create GameLoop and load state
    game_loop = GameLoop(language=language)
    game_loop.load_game(state_data)

    # Store in session
    session_store.put(game_id, game_loop, user_id=user_id, language=language)

    # ★ 服务端会话管理：记录活跃游戏
    db.set_active_game(user_id, game_id)

    state = game_loop.get_state()
    return GameStateResponse(
        game_id=game_id,
        player_state=state.to_dict() if state else {},
        progress=game_loop.get_progress(),
        round_info=game_loop.get_round_info(),
        current_event=game_loop.current_event.model_dump() if game_loop.current_event else None,
    )


@router.post("/{game_id}/save", response_model=SaveGameResponse)
async def save_game(
    game_id: int,
    user_id: int = Depends(get_current_user),
):
    """Save current game progress to database.
    
    使用 SessionService 统一处理 session 获取和恢复逻辑。
    """
    session = session_service.get_or_restore(game_id, user_id)
    
    db = get_db()
    state = session.game_loop.get_state()
    if state is None:
        raise HTTPException(status_code=400, detail="No game state to save")

    success = db.save_game_progress(game_id, state)
    return SaveGameResponse(
        success=success,
        message="Game saved" if success else "Failed to save game",
    )


@router.delete("/{game_id}", response_model=MessageResponse)
async def delete_game(
    game_id: int,
    user_id: int = Depends(get_current_user),
):
    """Delete a saved game."""
    db = get_db()
    
    # 检查是否是当前活跃游戏
    active_game_id = db.get_active_game(user_id)
    
    success = db.delete_saved_game(game_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Game not found or not owned by user")

    # Also remove from session store
    session_store.remove(game_id, user_id)
    
    # 如果删除的是活跃游戏，清除活跃引用
    if active_game_id == game_id:
        db.clear_active_game(user_id)

    return MessageResponse(message="Game deleted")


@router.post("/{game_id}/clear-cache", response_model=MessageResponse)
async def clear_game_cache(
    game_id: int,
    user_id: int = Depends(get_current_user),
):
    """Clear session cache for a game (useful after database restoration)."""
    # Remove from session store to force reload from database
    removed = session_store.remove(game_id, user_id)
    
    if removed:
        logger.info(f"Cleared session cache for game {game_id}, user {user_id}")
        return MessageResponse(message="Session cache cleared")
    else:
        return MessageResponse(message="No active session found for this game")


# ==================== 时间回溯存档系统 ====================

@router.post("/{game_id}/save-point", response_model=SaveGameResponse)
async def create_save_point(
    game_id: int,
    req: Optional[CreateSavePointRequest] = None,
    user_id: int = Depends(get_current_user),
):
    """
    ★ 创建存档点（手动存档）。
    
    与自动保存不同，存档点会被持久化展示，用户可以随时回溯到这个时间点。
    """
    session = session_service.get_or_restore(game_id, user_id)
    
    db = get_db()
    state = session.game_loop.get_state()
    if state is None:
        raise HTTPException(status_code=400, detail="No game state to save")
    
    save_name = req.save_name if req else None
    state_id = db.create_save_point(game_id, user_id, state, save_name)
    
    if state_id:
        return SaveGameResponse(
            success=True,
            message=f"存档点已创建 (ID: {state_id})",
        )
    else:
        raise HTTPException(status_code=500, detail="Failed to create save point")


@router.get("/{game_id}/save-points", response_model=SavePointListResponse)
async def list_save_points(
    game_id: int,
    user_id: int = Depends(get_current_user),
):
    """
    ★ 列出游戏的所有存档点。
    """
    db = get_db()
    save_points = db.list_save_points(game_id, user_id)
    
    # 获取玩家名称
    player_name = "未命名"
    if save_points:
        player_name = save_points[0].get("player_name", "未命名")
    
    return SavePointListResponse(
        game_id=game_id,
        player_name=player_name,
        save_points=[
            SavePointItem(
                state_id=sp["state_id"],
                game_id=sp["game_id"],
                week=sp["week"],
                age=sp["age"],
                save_name=sp.get("save_name"),
                created_at=sp["created_at"].isoformat() if sp.get("created_at") else None,
                player_name=sp.get("player_name", "未命名"),
            )
            for sp in save_points
        ],
        total=len(save_points),
    )


@router.get("/{game_id}/timeline", response_model=StateTimelineResponse)
async def get_state_timeline(
    game_id: int,
    limit: int = 50,
    user_id: int = Depends(get_current_user),
):
    """
    ★ 获取游戏状态时间线（包括自动快照和手动存档）。
    
    用于展示完整的时间回溯历史。
    """
    db = get_db()
    snapshots = db.get_all_states_for_game(game_id, user_id, limit=limit)
    
    # 获取玩家名称
    player_name = "未命名"
    if snapshots:
        player_name = snapshots[0].get("player_name", "未命名")
    
    return StateTimelineResponse(
        game_id=game_id,
        player_name=player_name,
        snapshots=[
            StateSnapshotItem(
                state_id=s["state_id"],
                game_id=s["game_id"],
                week=s["week"],
                age=s["age"],
                is_save_point=s["is_save_point"],
                save_name=s.get("save_name"),
                created_at=s["created_at"].isoformat() if s.get("created_at") else None,
                player_name=s.get("player_name", "未命名"),
            )
            for s in snapshots
        ],
        total=len(snapshots),
    )


@router.get("/load-save-point/{state_id}", response_model=GameStateResponse)
async def load_save_point(
    state_id: int,
    user_id: int = Depends(get_current_user),
):
    """
    ★ 加载特定存档点（时间回溯）。
    
    恢复到指定存档点的游戏状态。
    """
    db = get_db()
    state_data = db.load_save_point(state_id, user_id)
    
    if state_data is None:
        raise HTTPException(status_code=404, detail="Save point not found or not owned by user")
    
    game_id = state_data.get("_game_id")
    
    # 确定语言
    language = detect_language_from_state(state_data)
    
    # 创建 GameLoop 并加载状态
    game_loop = GameLoop(language=language)
    game_loop.load_game(state_data)
    
    # 存储到会话
    session_store.put(game_id, game_loop, user_id=user_id, language=language)
    
    # 更新活跃游戏
    db.set_active_game(user_id, game_id)
    
    state = game_loop.get_state()
    return GameStateResponse(
        game_id=game_id,
        player_state=state.to_dict() if state else {},
        progress=game_loop.get_progress(),
        round_info=game_loop.get_round_info(),
        current_event=game_loop.current_event.model_dump() if game_loop.current_event else None,
    )


@router.delete("/save-point/{state_id}", response_model=MessageResponse)
async def delete_save_point(
    state_id: int,
    user_id: int = Depends(get_current_user),
):
    """
    ★ 删除存档点。
    """
    db = get_db()
    success = db.delete_save_point(state_id, user_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Save point not found or not owned by user")
    
    return MessageResponse(message="Save point deleted")
