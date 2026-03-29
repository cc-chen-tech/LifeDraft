"""Game repository for game CRUD operations."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import func

from src.database.models import Game, GameState, SessionLocal, get_db

logger = logging.getLogger(__name__)


class GameRepository:
    """Repository for game-related database operations."""

    def create_game(
        self,
        language: str = "en",
        initial_state: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> int:
        """
        Create a new game record.

        Args:
            language: Language code
            initial_state: Initial player state
            user_id: 用户ID(可选)

        Returns:
            Game ID
        """
        db = SessionLocal()
        try:
            game = Game(
                language=language, initial_state=initial_state or {}, user_id=user_id
            )
            db.add(game)
            db.commit()
            db.refresh(game)
            return int(game.game_id)  # type: ignore[return-value]
        finally:
            db.close()

    def get_game(self, game_id: int, user_id: Optional[int] = None) -> Optional[Game]:
        """
        Get game record.

        Args:
            game_id: Game ID
            user_id: 用户ID，如果提供则验证所有权

        Returns:
            Game object or None
        """
        db = SessionLocal()
        try:
            query = db.query(Game).filter(Game.game_id == game_id)
            # 如果提供了 user_id，验证所有权
            if user_id is not None:
                query = query.filter(Game.user_id == user_id)
            return query.first()
        finally:
            db.close()

    def list_games(self, limit: int = 50, user_id: Optional[int] = None) -> List[Game]:
        """
        List recent games.

        Args:
            limit: Maximum number of games to return
            user_id: 用户ID，如果提供则只返回该用户的游戏
        """
        db = SessionLocal()
        try:
            query = db.query(Game)
            if user_id is not None:
                query = query.filter(Game.user_id == user_id)
            return query.order_by(Game.created_at.desc()).limit(limit).all()
        finally:
            db.close()

    def list_saved_games(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取用户的已保存游戏列表（包含详细信息）。

        Args:
            user_id: 用户ID
            limit: 最大返回数量

        Returns:
            游戏详情列表
        """
        db = SessionLocal()
        try:
            # 子查询：找到每个游戏的最新 state_id
            latest_state_subquery = (
                db.query(
                    GameState.game_id,
                    func.max(GameState.state_id).label("max_state_id"),
                )
                .group_by(GameState.game_id)
                .subquery()
            )

            # 主查询：JOIN Game + 最新 GameState
            results = (
                db.query(Game, GameState)
                .outerjoin(
                    latest_state_subquery,
                    Game.game_id == latest_state_subquery.c.game_id,
                )
                .outerjoin(
                    GameState,
                    GameState.state_id == latest_state_subquery.c.max_state_id,
                )
                .filter(Game.user_id == user_id)
                .filter(Game.ending_type.is_(None))
                .order_by(Game.updated_at.desc())
                .limit(limit)
                .all()
            )

            # 转换为原有返回格式
            result = []
            for game, latest_state in results:
                # 从 initial_state 或 latest_state 获取信息
                state_data = (
                    latest_state.state_json if latest_state else game.initial_state
                )
                initial_data = game.initial_state or {}

                # player_name 优先从 initial_state 获取（因为旧的 game_states 可能没有这个字段）
                player_name = (
                    (
                        state_data.get("player_name")
                        or initial_data.get("player_name")
                        or ""  # ★ 返回空字符串，让前端决定显示什么
                    )
                    if state_data
                    else initial_data.get("player_name", "")
                )
                week = state_data.get("week", 1) if state_data else 1
                age = state_data.get("age", 22) if state_data else 22

                result.append(
                    {
                        "game_id": game.game_id,
                        "player_name": player_name,
                        "week": week,
                        "age": age,
                        "created_at": game.created_at,
                        "updated_at": game.updated_at,
                        "has_progress": latest_state is not None,
                    }
                )

            return result
        finally:
            db.close()

    def delete_saved_game(self, game_id: int, user_id: int) -> bool:
        """
        删除已保存的游戏（验证用户权限）。

        Args:
            game_id: 游戏ID
            user_id: 用户ID

        Returns:
            是否成功
        """
        db = SessionLocal()
        try:
            game = (
                db.query(Game)
                .filter(Game.game_id == game_id, Game.user_id == user_id)
                .first()
            )

            if game:
                db.delete(game)  # cascade 会自动删除关联的 states 和 decisions
                db.commit()
                return True
            return False
        finally:
            db.close()

    def save_ending(
        self,
        game_id: int,
        final_state: Dict[str, Any],
        ending_type: str,
        summary: str,
        achievements: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save game ending.

        Args:
            game_id: Game ID
            final_state: Final player state
            ending_type: Type of ending
            summary: Ending summary text
            achievements: Achievements dictionary
        """
        from src.database.models import Ending

        with get_db() as db:
            # Update game record
            game = db.query(Game).filter(Game.game_id == game_id).first()
            if game:
                game.final_state = final_state
                game.ending_type = ending_type
                game.ending_summary = summary

            # Create ending record
            ending = Ending(
                game_id=game_id,
                final_state=final_state,
                ending_type=ending_type,
                summary=summary,
                achievements=achievements or {},
            )
            db.add(ending)
            db.commit()
