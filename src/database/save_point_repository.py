"""Save point repository for time rewind save system."""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.database.models import Game, GameState, SessionLocal

if TYPE_CHECKING:
    from src.game.state import PlayerState

logger = logging.getLogger(__name__)


class SavePointRepository:
    """Repository for time rewind save point operations."""

    def create_save_point(
        self,
        game_id: int,
        user_id: int,
        player_state: "PlayerState",
        save_name: Optional[str] = None,
    ) -> Optional[int]:
        """
        ★ 创建存档点（手动存档）。

        与自动快照不同，存档点会被持久化展示，用户可以随时回溯。

        Args:
            game_id: 游戏ID
            user_id: 用户ID（验证权限）
            player_state: 当前玩家状态
            save_name: 存档名称（可选）

        Returns:
            存档点ID，失败返回None
        """
        db = SessionLocal()
        try:
            # 验证游戏属于该用户
            game = db.query(Game).filter(Game.game_id == game_id, Game.user_id == user_id).first()

            if not game:
                logger.warning(
                    f"create_save_point: Game {game_id} not found or not owned by user {user_id}"
                )
                return None

            # 创建存档点
            save_point = GameState(
                game_id=game_id,
                week=player_state.week,
                age=player_state.age,
                state_json=player_state.to_dict(),
                is_save_point=True,
                save_name=save_name,
            )
            db.add(save_point)

            # 更新 Game 表的 updated_at
            game.updated_at = datetime.utcnow()  # type: ignore[assignment]

            db.commit()
            db.refresh(save_point)

            logger.info(
                f"create_save_point: Created save_point {save_point.state_id} for game {game_id}"
            )
            return int(save_point.state_id)  # type: ignore[arg-type, return-value]
        except Exception as e:
            logger.error(f"create_save_point: Failed to create save point, error={e}")
            db.rollback()
            return None
        finally:
            db.close()

    def list_save_points(self, game_id: int, user_id: int) -> List[Dict[str, Any]]:
        """
        ★ 列出游戏的所有存档点。

        Args:
            game_id: 游戏ID
            user_id: 用户ID（验证权限）

        Returns:
            存档点列表
        """
        db = SessionLocal()
        try:
            # 验证游戏属于该用户
            game = db.query(Game).filter(Game.game_id == game_id, Game.user_id == user_id).first()

            if not game:
                return []

            # 查询所有存档点
            save_points = (
                db.query(GameState)
                .filter(GameState.game_id == game_id, GameState.is_save_point == True)
                .order_by(GameState.created_at.desc())
                .all()
            )

            result = []
            for sp in save_points:
                state: dict = sp.state_json or {}  # type: ignore[assignment]
                result.append(
                    {
                        "state_id": sp.state_id,
                        "game_id": sp.game_id,
                        "week": sp.week,
                        "age": sp.age,
                        "save_name": sp.save_name,
                        "created_at": sp.created_at,
                        "player_name": state.get("player_name", "未命名"),
                    }
                )

            return result
        finally:
            db.close()

    def load_save_point(self, state_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        ★ 加载特定存档点（时间回溯）。

        Args:
            state_id: 存档点ID
            user_id: 用户ID（验证权限）

        Returns:
            游戏状态字典
        """
        db = SessionLocal()
        try:
            # 查询存档点并验证权限
            save_point = db.query(GameState).filter(GameState.state_id == state_id).first()

            if not save_point:
                return None

            # 验证游戏属于该用户
            game = (
                db.query(Game)
                .filter(Game.game_id == save_point.game_id, Game.user_id == user_id)
                .first()
            )

            if not game:
                return None

            state_data = save_point.state_json
            if state_data:
                state_data["_game_id"] = save_point.game_id

            return state_data  # type: ignore[return-value]
        finally:
            db.close()

    def delete_save_point(self, state_id: int, user_id: int) -> bool:
        """
        ★ 删除存档点。

        Args:
            state_id: 存档点ID
            user_id: 用户ID（验证权限）

        Returns:
            是否成功
        """
        db = SessionLocal()
        try:
            # 查询存档点并验证权限
            save_point = (
                db.query(GameState)
                .filter(GameState.state_id == state_id, GameState.is_save_point == True)
                .first()
            )

            if not save_point:
                return False

            # 验证游戏属于该用户
            game = (
                db.query(Game)
                .filter(Game.game_id == save_point.game_id, Game.user_id == user_id)
                .first()
            )

            if not game:
                return False

            db.delete(save_point)
            db.commit()
            return True
        finally:
            db.close()

    def get_all_states_for_game(
        self, game_id: int, user_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        ★ 获取游戏的所有状态快照（用于时间线展示）。

        包括自动快照和手动存档点。

        Args:
            game_id: 游戏ID
            user_id: 用户ID（验证权限）
            limit: 最大返回数量

        Returns:
            状态快照列表
        """
        db = SessionLocal()
        try:
            # 验证游戏属于该用户
            game = db.query(Game).filter(Game.game_id == game_id, Game.user_id == user_id).first()

            if not game:
                return []

            # 查询所有状态快照
            states = (
                db.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.created_at.desc())
                .limit(limit)
                .all()
            )

            result = []
            for s in states:
                state: dict = s.state_json or {}  # type: ignore[assignment]
                result.append(
                    {
                        "state_id": s.state_id,
                        "game_id": s.game_id,
                        "week": s.week,
                        "age": s.age,
                        "is_save_point": s.is_save_point,
                        "save_name": s.save_name,
                        "created_at": s.created_at,
                        "player_name": state.get("player_name", "未命名"),
                    }
                )

            return result
        finally:
            db.close()
