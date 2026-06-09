"""Games router — CRUD for game sessions (create, list, load, save, delete).

Includes narrative-style endpoints for style browsing and per-game style updates.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.ai.narrative.style_manifest import get_default_loader, get_style
from src.api.deps import get_current_user, get_current_user_optional, get_db
from src.api.schemas import CreateGameRequest  # 时间回溯存档系统
from src.api.schemas import (CreateSavePointRequest, GameListItem,
                             GameStateResponse, MessageResponse,
                             SaveGameResponse, SavePointItem,
                             SavePointListResponse, StateSnapshotItem,
                             StateTimelineResponse, UpdateCharacterSettingsRequest,
                             UpdateGameSettingsRequest)
from src.api.services.session_service import session_service
from src.api.session_store import session_store
from src.database.models import Game, SessionLocal
from src.game.game_initializer import GameInitializer
from src.game.game_loop import GameLoop
from src.game.state import PlayerState
from src.utils.language import detect_language_from_state

logger = logging.getLogger(__name__)
router = APIRouter()


def _deep_merge_dicts(existing: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Merge nested character settings without dropping unrelated existing fields."""
    merged = dict(existing)
    for key, value in updates.items():
        current_value = merged.get(key)
        if isinstance(current_value, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(current_value, value)
        else:
            merged[key] = value
    return merged


def _extract_generated_initial_wealth(character_settings: Dict[str, Any]) -> Optional[int]:
    wealth_setting = character_settings.get("wealth")
    if not isinstance(wealth_setting, dict):
        return None

    wealth = wealth_setting.get("wealth")
    if not isinstance(wealth, (int, float)):
        return None

    return max(0, min(1_000_000, int(wealth)))


def _is_before_first_played_round(state_data: Dict[str, Any]) -> bool:
    week = state_data.get("week", 0)
    current_round = state_data.get("current_round", 0)
    round_history = state_data.get("round_history") or []
    return int(week or 0) <= 0 and int(current_round or 0) <= 0 and not round_history


@router.post("", response_model=GameStateResponse, status_code=201)
async def create_game(
    req: CreateGameRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """Create a new game from character settings."""
    db = get_db()
    try:
        # 将 constraint_level 注入 character_settings
        character_settings = dict(req.character_settings)
        character_settings["constraint_level"] = req.constraint_level

        initializer = GameInitializer(game_db=db, language=req.language)
        game_loop, game_id = initializer.initialize_game_from_settings(
            character_settings=character_settings,
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
        current_event=(game_loop.current_event.model_dump() if game_loop.current_event else None),
        constraint_level=req.constraint_level,
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
    request: Request,
    user_id: int = Depends(get_current_user),
):
    """
    ★ 获取用户当前活跃的游戏并自动恢复。

    用于iPad等设备上localStorage失效时的会话恢复。
    如果用户有活跃游戏，自动加载并返回游戏状态。
    如果没有活跃游戏，返回404。
    """
    # ★ 调试日志：检查认证信息
    cookie_token = request.cookies.get("auth_token")
    logger.info(f"[get_active_game] user_id={user_id}, has_auth_token={cookie_token is not None}")

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

    logger.info(f"[get_active_game] Loaded state_data for game_id={active_game_id}")

    # 确定语言
    language = detect_language_from_state(state_data)

    # 创建 GameLoop 并加载状态
    try:
        constraint_level = state_data.get("constraint_level", "expert") if state_data else "expert"
        game_loop = GameLoop(language=language, quality_level=constraint_level)
        game_loop.load_game(state_data)
        logger.info("[get_active_game] GameLoop loaded successfully")
    except Exception as e:
        logger.exception(f"[get_active_game] Failed to load game: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load game state: {str(e)}")

    # 存储到会话
    session_store.put(active_game_id, game_loop, user_id=user_id, language=language)

    try:
        state = game_loop.get_state()
        player_state_dict = state.to_dict() if state else {}
        logger.info("[get_active_game] State converted to dict successfully")
    except Exception as e:
        logger.exception(f"[get_active_game] Failed to convert state to dict: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serialize game state: {str(e)}")

    return GameStateResponse(
        game_id=active_game_id,
        player_state=player_state_dict,
        progress=game_loop.get_progress(),
        round_info=game_loop.get_round_info(),
        current_event=(game_loop.current_event.model_dump() if game_loop.current_event else None),
        constraint_level=constraint_level,
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
    constraint_level = state_data.get("constraint_level", "expert") if state_data else "expert"
    game_loop = GameLoop(language=language, quality_level=constraint_level)
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
        current_event=(game_loop.current_event.model_dump() if game_loop.current_event else None),
        constraint_level=constraint_level,
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
                created_at=(sp["created_at"].isoformat() if sp.get("created_at") else None),
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
    constraint_level = state_data.get("constraint_level", "expert") if state_data else "expert"
    game_loop = GameLoop(language=language, quality_level=constraint_level)
    game_loop.load_game(state_data)

    # 存储到会话
    session_store.put(game_id, game_loop, user_id=user_id, language=language)  # type: ignore[arg-type]

    # 更新活跃游戏
    db.set_active_game(user_id, game_id)  # type: ignore[arg-type]

    state = game_loop.get_state()
    return GameStateResponse(
        game_id=game_id,  # type: ignore[arg-type]
        player_state=state.to_dict() if state else {},
        progress=game_loop.get_progress(),
        round_info=game_loop.get_round_info(),
        current_event=(game_loop.current_event.model_dump() if game_loop.current_event else None),
        constraint_level=constraint_level,
    )


@router.patch("/{game_id}/character-settings", response_model=MessageResponse)
async def update_character_settings(
    game_id: int,
    req: UpdateCharacterSettingsRequest,
    user_id: int = Depends(get_current_user),
):
    """
    Persist late character creation settings for an existing game.

    The create flow may add generated family, relationship, trait, and wealth
    settings after the initial game record exists. This endpoint preserves the
    manually selected settings and merges the generated settings into the saved
    player state before opening story generation starts.
    """
    db = get_db()
    state_data = db.load_saved_game(game_id, user_id)
    if state_data is None:
        raise HTTPException(status_code=404, detail="Game not found or not owned by user")

    existing_settings = state_data.get("character_settings") or {}
    if not isinstance(existing_settings, dict):
        existing_settings = {}
    merged_settings = _deep_merge_dicts(existing_settings, req.character_settings)

    updated_state = dict(state_data)
    updated_state["character_settings"] = merged_settings
    late_initial_wealth = _extract_generated_initial_wealth(req.character_settings)
    should_sync_late_wealth = (
        late_initial_wealth is not None and _is_before_first_played_round(state_data)
    )
    if should_sync_late_wealth:
        updated_state["wealth"] = late_initial_wealth
    player_state = PlayerState.from_dict(updated_state)

    if not db.save_game_progress(game_id, player_state):
        raise HTTPException(status_code=500, detail="Failed to save character settings")

    game_session = session_store.get(game_id, user_id)
    if game_session and game_session.game_loop and game_session.game_loop.player_state:
        game_session.game_loop.player_state.character_settings = merged_settings
        if should_sync_late_wealth:
            game_session.game_loop.player_state.wealth = late_initial_wealth

    return MessageResponse(success=True, message="Character settings updated")


@router.patch("/{game_id}/settings", response_model=MessageResponse)
async def update_game_settings(
    game_id: int,
    req: UpdateGameSettingsRequest,
    user_id: int = Depends(get_current_user),
):
    """
    ★ 更新游戏设置（如 constraint_level）。
    """
    db = get_db()
    state_data = db.load_saved_game(game_id, user_id)
    if state_data is None:
        raise HTTPException(status_code=404, detail="Game not found or not owned by user")

    if req.constraint_level is not None:
        # 持久化到 Game 表
        db_session = SessionLocal()
        try:
            game = (
                db_session.query(Game)
                .filter(Game.game_id == game_id, Game.user_id == user_id)
                .first()
            )
            if game:
                setattr(game, "constraint_level", req.constraint_level)
                db_session.commit()
        finally:
            db_session.close()

        # 同步更新会话中的 GameLoop
        game_session = session_store.get(game_id)
        if game_session and game_session.game_loop:
            game_session.game_loop.quality_level = req.constraint_level
            from src.ai.generator import EventGenerator
            from src.game.character_creator import CharacterCreator
            from src.game.story_service import StoryService
            from src.game.yearly_summary import YearlySummaryGenerator

            game_session.game_loop.ai_generator = EventGenerator(quality_level=req.constraint_level)
            # 重新创建依赖 ai_generator 的服务
            game_session.game_loop.yearly_summary_gen = YearlySummaryGenerator(
                game_session.game_loop.ai_generator, game_session.game_loop.language
            )
            game_session.game_loop.character_creator = CharacterCreator(
                ai_generator=game_session.game_loop.ai_generator,
                language=game_session.game_loop.language,
            )
            game_session.game_loop.story_service = StoryService(
                game_session.game_loop.ai_generator, game_session.game_loop.language
            )

    return MessageResponse(success=True, message="Settings updated")


# ==================== 叙事风格设置 ====================


class NarrativeStyleOption(BaseModel):
    style_id: str
    style_name: str
    description: str = ""


class NarrativeStyleResponse(BaseModel):
    style_id: str
    style_name: str


class UpdateNarrativeStyleRequest(BaseModel):
    style_id: str


@router.get("/{game_id}/narrative-style-options")
async def list_narrative_style_options(
    game_id: int,
    user_id: int = Depends(get_current_user),
):
    """返回所有可用的叙事风格列表。"""
    loader = get_default_loader()
    style_ids = loader.get_all_style_ids()
    options = []
    for sid in sorted(style_ids):
        manifest = loader.get_style(sid)
        if manifest:
            options.append(
                NarrativeStyleOption(
                    style_id=manifest.style_id,
                    style_name=manifest.style_name,
                    description=manifest.description,
                )
            )
    return options


@router.get("/{game_id}/narrative-style", response_model=NarrativeStyleResponse)
async def get_narrative_style(
    game_id: int,
    user_id: int = Depends(get_current_user),
):
    """获取当前游戏的叙事风格。"""
    db_session = SessionLocal()
    try:
        game = (
            db_session.query(Game).filter(Game.game_id == game_id, Game.user_id == user_id).first()
        )
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        style_id = str(game.narrative_style_id or "chinese_classic_saga")
        style_name = style_id
        manifest = get_style(style_id)
        if manifest:
            style_name = manifest.style_name

        return NarrativeStyleResponse(style_id=style_id, style_name=style_name)
    finally:
        db_session.close()


@router.put("/{game_id}/narrative-style", response_model=MessageResponse)
async def update_narrative_style(
    game_id: int,
    req: UpdateNarrativeStyleRequest,
    user_id: int = Depends(get_current_user),
):
    """更新游戏的叙事风格。"""
    # 验证 style_id 有效
    manifest = get_style(req.style_id)
    if not manifest:
        raise HTTPException(status_code=400, detail=f"Unknown style_id: {req.style_id}")

    db_session = SessionLocal()
    try:
        game = (
            db_session.query(Game).filter(Game.game_id == game_id, Game.user_id == user_id).first()
        )
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")

        game.narrative_style_id = req.style_id  # type: ignore[assignment]
        db_session.commit()
    finally:
        db_session.close()

    # 同步更新会话中的 style
    game_session = session_store.get(game_id)
    if game_session and game_session.game_loop:
        game_session.game_loop.narrative_style_id = req.style_id  # type: ignore[attr-defined]

    return MessageResponse(success=True, message="Narrative style updated")


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
