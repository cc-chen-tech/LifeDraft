"""Session repository for active game session management."""

import logging
from typing import Optional

from src.database.models import Game, SessionLocal, User

logger = logging.getLogger(__name__)


class SessionRepository:
    """Repository for active game session management."""

    def set_active_game(self, user_id: int, game_id: int) -> bool:
        """
        ★ 设置用户当前活跃的游戏ID。

        用于服务端会话恢复：当用户重新访问时，可以从这里获取最近的游戏ID。

        Args:
            user_id: 用户ID
            game_id: 游戏ID

        Returns:
            是否成功
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                user.last_active_game_id = game_id  # type: ignore[assignment]
                db.commit()
                logger.info(f"Set active game for user {user_id}: game_id={game_id}")
                return True
            return False
        finally:
            db.close()

    def get_active_game(self, user_id: int) -> Optional[int]:
        """
        ★ 获取用户当前活跃的游戏ID。

        用于服务端会话恢复：当localStorage失效时，可以从这里获取最近的游戏ID。

        Args:
            user_id: 用户ID

        Returns:
            游戏ID，如果没有则返回 None
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user and user.last_active_game_id:
                # 验证游戏是否仍然存在且属于该用户
                game = (
                    db.query(Game)
                    .filter(
                        Game.game_id == user.last_active_game_id,
                        Game.user_id == user_id,
                    )
                    .first()
                )
                if game:
                    return int(user.last_active_game_id)  # type: ignore[arg-type, return-value]
                else:
                    # 游戏已被删除，清除引用
                    user.last_active_game_id = None  # type: ignore[assignment]
                    db.commit()
            return None
        finally:
            db.close()

    def clear_active_game(self, user_id: int) -> bool:
        """
        ★ 清除用户的活跃游戏ID。

        在游戏结束或用户主动退出时调用。

        Args:
            user_id: 用户ID

        Returns:
            是否成功
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                user.last_active_game_id = None  # type: ignore[assignment]
                db.commit()
                return True
            return False
        finally:
            db.close()
