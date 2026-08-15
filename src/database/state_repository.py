"""State repository for game state persistence."""

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import or_

from src.database.models import (Game, GameState, Image,
                                 PortraitImageGenerationJob, SessionLocal,
                                 get_db)
from src.game.story_origin import (StoryOriginLocked,
                                   StoryOriginRevisionConflict,
                                   story_origin_is_locked)

if TYPE_CHECKING:
    from src.game.state import PlayerState

logger = logging.getLogger(__name__)


class StateRepository:
    """Repository for game state read/write operations."""

    # P3-存储优化：自动快照保留上限。
    # 时间线（get_all_states_for_game）展示最近 50 个快照，保留最近 30 个
    # 自动快照既维持时间线体验，又阻止 game_states 无界膨胀
    # （此前每局数百行 × 单行数百KB~3.4MB）。手动存档点永不删除。
    AUTO_SNAPSHOT_KEEP_COUNT: int = int(
        os.getenv("GAME_STATE_AUTO_SNAPSHOT_KEEP", "30")
    )

    def save_state(self, game_id: int, player_state: "PlayerState") -> None:
        """
        Save a game state snapshot.

        Args:
            game_id: Game ID
            player_state: Current player state
        """
        with get_db() as db:
            state = GameState(
                game_id=game_id,
                week=player_state.week,
                age=player_state.age,
                state_json=player_state.to_dict(),
            )
            db.add(state)
            db.commit()

    def load_game_state(self, game_id: int) -> Optional[Dict[str, Any]]:
        """
        Load the latest game state.

        Args:
            game_id: Game ID

        Returns:
            Latest state dictionary or None
        """
        with get_db() as db:
            # First try to get the latest snapshot from GameState
            state = (
                db.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.week.desc())
                .first()
            )

            if state:
                return state.state_json  # type: ignore[no-any-return]

            # If no snapshots found, fallback to the initial state in the Game record
            game = db.query(Game).filter(Game.game_id == game_id).first()
            if game:
                return game.initial_state  # type: ignore[no-any-return]

            return None

    def save_game_progress(self, game_id: int, player_state: "PlayerState") -> bool:
        """
        保存游戏进度（更新最新状态）。

        Args:
            game_id: 游戏ID
            player_state: 当前玩家状态

        Returns:
            是否成功
        """
        if not player_state:
            logger.error(f"save_game_progress: player_state is None for game_id={game_id}")
            return False

        # ★ 显示用周数（人类可读，从1开始）
        week_display = f"第{player_state.week + 1}周" if player_state.week is not None else "未知周"
        logger.info(
            f"save_game_progress: Saving game_id={game_id}, {week_display}, age={player_state.age}"
        )

        # ★ Bug #29/#16 修复：不再清除 current_event_data。
        # current_event_data 保存玩家当前看到的事件，即使该轮已在 round_history 中，
        # 它也是正常状态（下一事件可能尚未生成）。清除它会导致刷新后章节重新生成。
        db = SessionLocal()
        try:
            # 保存新的状态快照
            state = GameState(
                game_id=game_id,
                week=player_state.week,
                age=player_state.age,
                state_json=player_state.to_dict(),
            )
            db.add(state)

            # 更新 Game 表的 updated_at
            game = db.query(Game).filter(Game.game_id == game_id).first()
            if game:
                game.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
                logger.info(f"save_game_progress: Updated game {game_id} updated_at")
            else:
                logger.warning(f"save_game_progress: Game {game_id} not found in database")

            db.commit()
            logger.info(f"save_game_progress: Successfully saved game_id={game_id}")

            # P3-存储优化：清理超出保留上限的旧自动快照。
            # 清理失败只记日志，绝不影响本次保存的结果。
            try:
                pruned = self._prune_old_auto_snapshots(db, game_id)
                if pruned:
                    logger.info(
                        f"save_game_progress: pruned {pruned} old auto snapshots for game_id={game_id}"
                    )
            except Exception:
                logger.warning(
                    f"save_game_progress: failed to prune old snapshots for game_id={game_id}",
                    exc_info=True,
                )

            return True
        except Exception as e:
            logger.error(f"save_game_progress: Failed to save game_id={game_id}, error={e}")
            db.rollback()
            return False
        finally:
            db.close()

    def _prune_old_auto_snapshots(self, db, game_id: int) -> int:
        """删除超出保留上限的旧自动快照，手动存档点（is_save_point=True）永不删除。

        自动快照判断：is_save_point 为 False 或 NULL（旧数据兼容）。
        返回删除的行数；调用方负责事务边界。
        """
        auto_filter = or_(
            GameState.is_save_point.is_(False),
            GameState.is_save_point.is_(None),
        )
        keep_rows = (
            db.query(GameState.state_id)
            .filter(GameState.game_id == game_id, auto_filter)
            .order_by(GameState.state_id.desc())
            .limit(self.AUTO_SNAPSHOT_KEEP_COUNT)
            .all()
        )
        keep_ids = {row[0] for row in keep_rows}
        if not keep_ids:
            return 0
        deleted = (
            db.query(GameState)
            .filter(
                GameState.game_id == game_id,
                auto_filter,
                GameState.state_id.notin_(keep_ids),
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return int(deleted)

    @staticmethod
    def save_story_origin_progress_in_session(
        db,
        game_id: int,
        user_id: int,
        player_state: "PlayerState",
        expected_revision: Optional[int] = None,
    ) -> None:
        """Commit an origin snapshot and invalidate all old-origin assets together."""
        game = (
            db.query(Game)
            .filter(Game.game_id == game_id, Game.user_id == user_id)
            .with_for_update()
            .one_or_none()
        )
        if game is None:
            raise ValueError("game_not_found")

        latest = (
            db.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        current_state = latest.state_json if latest is not None else game.initial_state
        if not isinstance(current_state, dict):
            current_state = {}
        if story_origin_is_locked(current_state):
            raise StoryOriginLocked("story_origin_locked")

        if expected_revision is not None:
            from src.game.story_origin import normalize_legacy_story_origin

            current_settings = (
                current_state.get("character_settings", {})
                if isinstance(current_state, dict)
                else {}
            )
            current_origin, _ = normalize_legacy_story_origin(current_settings)
            if current_origin["revision"] != expected_revision:
                raise StoryOriginRevisionConflict("story_origin_revision_conflict")

        db.add(
            GameState(
                game_id=game_id,
                week=player_state.week,
                age=player_state.age,
                state_json=player_state.to_dict(),
            )
        )
        game.updated_at = datetime.now(timezone.utc)
        game.narrative_style_id = None
        db.query(Image).filter(
            Image.game_id == game_id,
            Image.image_type == "character",
            Image.entity_key == "player_main",
            Image.is_active.is_(True),
        ).update({"is_active": False}, synchronize_session=False)
        db.query(PortraitImageGenerationJob).filter(
            PortraitImageGenerationJob.game_id == game_id,
            PortraitImageGenerationJob.user_id == user_id,
            PortraitImageGenerationJob.status.in_(("queued", "running")),
        ).update(
            {
                "status": "failed",
                "error_code": "story_origin_superseded",
                "error_message": "故事起点已更新，旧人物形象任务已作废",
            },
            synchronize_session=False,
        )
        db.commit()

    def save_story_origin_progress(
        self,
        game_id: int,
        user_id: int,
        player_state: "PlayerState",
        expected_revision: Optional[int] = None,
    ) -> bool:
        db = SessionLocal()
        try:
            self.save_story_origin_progress_in_session(
                db,
                game_id,
                user_id,
                player_state,
                expected_revision=expected_revision,
            )
            return True
        except (StoryOriginLocked, StoryOriginRevisionConflict):
            db.rollback()
            raise
        except Exception as exc:
            logger.error("Failed to save story origin for game_id=%s: %s", game_id, exc)
            db.rollback()
            return False
        finally:
            db.close()

    def load_saved_game(self, game_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        加载已保存的游戏（验证用户权限）。

        Args:
            game_id: 游戏ID
            user_id: 用户ID（用于验证权限）

        Returns:
            游戏状态字典，包含 game_id
        """
        db = SessionLocal()
        try:
            # 验证游戏属于该用户
            game = db.query(Game).filter(Game.game_id == game_id, Game.user_id == user_id).first()

            if not game:
                return None

            # 获取最新状态（按创建时间降序，确保返回最新的记录）
            latest_state = (
                db.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.created_at.desc())
                .first()
            )

            state_data = latest_state.state_json if latest_state else game.initial_state
            initial_data: dict = game.initial_state or {}  # type: ignore[assignment]

            if state_data:
                state_data["_game_id"] = game_id  # 添加 game_id 以便后续保存
                # 注入 constraint_level，优先从 game 记录获取
                state_data["constraint_level"] = (
                    getattr(game, "constraint_level", "expert") or "expert"
                )

                # 注入 narrative_style_id，优先从 game 记录获取
                style_id = getattr(game, "narrative_style_id", None)
                if style_id:
                    state_data["narrative_style_id"] = style_id
                elif initial_data.get("narrative_style_id"):
                    state_data["narrative_style_id"] = initial_data["narrative_style_id"]

                # 从 initial_state 补充 player_name 和 life_vision（旧存档可能没有这些字段）
                if not state_data.get("player_name") and initial_data.get("player_name"):
                    state_data["player_name"] = initial_data["player_name"]
                if not state_data.get("life_vision") and initial_data.get("life_vision"):
                    state_data["life_vision"] = initial_data["life_vision"]

            return state_data  # type: ignore[return-value]
        finally:
            db.close()
