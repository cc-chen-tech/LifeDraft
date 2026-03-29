"""Session management service - unified session get/restore logic.

This module consolidates the duplicated session restoration logic that was
previously scattered across gameplay.py and games.py.

Usage:
    from src.api.services.session_service import session_service

    session = session_service.get_or_restore(game_id, user_id)
"""

import logging
import threading
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from src.api.session_store import GameLoopSession, session_store
from src.database.models import SessionLocal  # ★ 添加 SessionLocal 导入
from src.database.singletons import get_game_db
from src.game.game_loop import GameLoop
from src.utils.language import detect_language_from_state

logger = logging.getLogger(__name__)


class SessionService:
    """统一的会话管理服务。

    提供：
    - 获取内存中的 session
    - 自动从数据库恢复已过期的 session
    - 创建新 session

    Example:
        session = session_service.get_or_restore(game_id=1, user_id=1)
        game_loop = session.game_loop
    """

    def get(
        self, game_id: int, user_id: Optional[int] = None
    ) -> Optional[GameLoopSession]:
        """获取内存中的 session，不自动恢复。

        Args:
            game_id: 游戏 ID
            user_id: 用户 ID（可选）

        Returns:
            GameLoopSession 或 None（如果不存在或已过期）
        """
        return session_store.get(game_id, user_id)

    def get_or_restore(
        self, game_id: int, user_id: Optional[int] = None
    ) -> GameLoopSession:
        """获取 session，如果不存在则从数据库恢复。

        Args:
            game_id: 游戏 ID
            user_id: 用户 ID（可选）

        Returns:
            GameLoopSession

        Raises:
            HTTPException: 404 如果游戏不存在
        """
        session = session_store.get(game_id, user_id)
        if session is not None:
            return session

        # 内存中没有 session，尝试从数据库恢复
        logger.info(
            f"Session not in memory for game_id={game_id}, attempting auto-restore from database..."
        )
        return self._restore_from_database(game_id, user_id)

    def _restore_from_database(
        self, game_id: int, user_id: Optional[int]
    ) -> GameLoopSession:
        """从数据库恢复游戏状态到内存 session。

        Args:
            game_id: 游戏 ID
            user_id: 用户 ID（可选）

        Returns:
            GameLoopSession

        Raises:
            HTTPException: 404 如果游戏不存在
        """
        try:
            db = get_game_db()
            state_data = db.load_saved_game(game_id, user_id)  # type: ignore[arg-type]

            if state_data is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Game not found or not owned by user: game_id={game_id}",
                )

            # Determine language from state
            language = detect_language_from_state(state_data)

            # Create GameLoop and load state
            game_loop = GameLoop(language=language)
            game_loop.load_game(state_data)

            # Store in session
            session = session_store.put(
                game_id, game_loop, user_id=user_id, language=language
            )
            logger.info(
                f"Auto-restored session from database: game_id={game_id}, has_current_event={game_loop.current_event is not None}"
            )

            # ★ 检查并补充缺失的场景插画
            self._check_and_generate_missing_illustrations(
                game_id, game_loop, state_data
            )

            return session

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to auto-restore session for game_id={game_id}: {e}")
            raise HTTPException(
                status_code=404,
                detail=f"No active game session for game_id={game_id}. Load the game first.",
            )

    def put(
        self,
        game_id: int,
        game_loop: GameLoop,
        user_id: Optional[int] = None,
        language: str = "zh",
    ) -> GameLoopSession:
        """创建或更新 session。

        Args:
            game_id: 游戏 ID
            game_loop: GameLoop 实例
            user_id: 用户 ID（可选）
            language: 语言代码

        Returns:
            GameLoopSession
        """
        return session_store.put(game_id, game_loop, user_id=user_id, language=language)

    def remove(self, game_id: int, user_id: Optional[int] = None) -> bool:
        """移除 session。

        Args:
            game_id: 游戏 ID
            user_id: 用户 ID（可选）

        Returns:
            bool: 是否成功移除
        """
        return session_store.remove(game_id, user_id)

    def _check_and_generate_missing_illustrations(
        self,
        game_id: int,
        game_loop: GameLoop,
        state_data: Dict[str, Any],
    ) -> None:
        """
        检查并补充缺失的场景插画。

        在 session 恢复后调用，检查当前轮次和历史轮次的插画是否存在，
        如果不存在或文件丢失则触发后台生成。

        Args:
            game_id: 游戏 ID
            game_loop: GameLoop 实例
            state_data: 游戏状态数据
        """
        try:
            from src.database.models import Image as ImageModel
            from src.database.models import SceneImage
            from src.services.image_storage import ImageStorageService

            db = SessionLocal()  # ★ 使用 SessionLocal 获取真正的 SQLAlchemy session
            image_storage = ImageStorageService()

            try:
                player_state = game_loop.player_state
                if player_state is None:
                    return
                current_week = player_state.week
                current_round = player_state.current_round

                # 1. 检查人物形象图片是否存在
                self._check_character_images(
                    db=db,
                    game_id=game_id,
                    player_state=player_state,
                    image_storage=image_storage,
                    character_settings=player_state.character_settings,
                )

                # 2. 检查当前轮次的插画
                # 如果有 current_event，说明正在显示事件，需要 event 阶段的插画
                # 如果没有 current_event 但有上一轮记录，需要 result 阶段的插画

                if game_loop.current_event:
                    # 正在显示事件选项，检查 event 阶段插画
                    self._check_and_generate_illustration(
                        db=db,
                        game_id=game_id,
                        week=current_week,
                        round_number=current_round,
                        stage="event",
                        story_text=game_loop.current_event.event_description,
                        character_settings=player_state.character_settings,
                        player_name=player_state.player_name,
                        image_storage=image_storage,
                    )

                # 3. 检查最近的历史轮次插画（最近5轮）
                self._check_recent_scene_images(
                    db=db,
                    game_id=game_id,
                    player_state=player_state,
                    image_storage=image_storage,
                )

                logger.info(
                    f"[SessionService] Illustration check completed for game_id={game_id}"
                )

            except Exception as inner_e:
                logger.warning(f"[SessionService] Illustration query failed: {inner_e}")
            finally:
                db.close()  # ★ 确保关闭 session

        except Exception as e:
            # 图片生成失败不应该影响 session 恢复
            logger.warning(
                f"[SessionService] Failed to check/generate illustrations: {e}"
            )

    def _check_character_images(
        self,
        db,
        game_id: int,
        player_state,
        image_storage,
        character_settings: Dict[str, Any],
    ) -> None:
        """
        检查人物形象图片是否存在，如果不存在或文件丢失则重新生成。

        Args:
            db: 数据库会话
            game_id: 游戏 ID
            player_state: 玩家状态
            image_storage: 图片存储服务
            character_settings: 角色设定
        """
        from src.database.models import Image as ImageModel

        # 获取所有人物形象图片
        character_images = (
            db.query(ImageModel)
            .filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == "character",
                ImageModel.is_active == True,
            )
            .all()
        )

        missing_images = []
        for img in character_images:
            # 检查文件是否存在
            if not image_storage.image_exists(img.storage_path, img.storage_type):
                logger.warning(
                    f"[SessionService] Character image file missing: "
                    f"image_id={img.image_id}, entity_name={img.entity_name}, "
                    f"storage_path={img.storage_path}"
                )
                missing_images.append(img)

        if missing_images:
            logger.info(
                f"[SessionService] Found {len(missing_images)} missing character images, triggering regeneration..."
            )
            # 标记丢失的图片为非活跃
            for img in missing_images:
                img.is_active = False
            db.commit()

            # 触发后台重新生成人物形象
            self._trigger_character_image_regeneration(
                game_id=game_id,
                missing_images=missing_images,
                character_settings=character_settings,
            )

    def _check_recent_scene_images(
        self,
        db,
        game_id: int,
        player_state,
        image_storage,
    ) -> None:
        """
        检查最近的历史轮次场景插画是否存在。

        Args:
            db: 数据库会话
            game_id: 游戏 ID
            player_state: 玩家状态
            image_storage: 图片存储服务
        """
        from src.database.models import SceneImage

        # 获取最近的场景插画记录
        recent_scenes = (
            db.query(SceneImage)
            .filter(
                SceneImage.game_id == game_id,
            )
            .order_by(SceneImage.scene_id.desc())
            .limit(10)
            .all()
        )

        missing_scenes = []
        for scene in recent_scenes:
            if not image_storage.image_exists(scene.storage_path, scene.storage_type):
                week_display = (
                    f"第{scene.week + 1}周" if scene.week is not None else "未知周"
                )
                logger.warning(
                    f"[SessionService] Scene image file missing: "
                    f"scene_id={scene.scene_id}, {week_display}, round={scene.round_number}, "
                    f"storage_path={scene.storage_path}"
                )
                missing_scenes.append(scene)

        if missing_scenes:
            logger.info(
                f"[SessionService] Found {len(missing_scenes)} missing scene images"
            )
            # 标记丢失的场景图片
            for scene in missing_scenes:
                # 不删除记录，但标记为需要重新生成
                scene.importance_score = "missing"
            db.commit()

    def _trigger_character_image_regeneration(
        self,
        game_id: int,
        missing_images: list,
        character_settings: Dict[str, Any],
    ) -> None:
        """
        在后台线程中触发人物形象重新生成。

        Args:
            game_id: 游戏 ID
            missing_images: 缺失的图片列表
            character_settings: 角色设定
        """

        def regenerate_in_background():
            try:
                from src.ai.image_client import ImageClient
                from src.services.image_service import ImageService
                from src.services.image_storage import ImageStorageService

                db = SessionLocal()
                try:
                    image_client = ImageClient()
                    storage_service = ImageStorageService()
                    image_service = ImageService(
                        db=db,
                        image_client=image_client,
                        storage_service=storage_service,
                    )

                    for img in missing_images:
                        try:
                            # 尝试重新生成
                            logger.info(
                                f"[SessionService] Regenerating character image: "
                                f"entity_name={img.entity_name}"
                            )

                            # 从 metadata 提取角色设定
                            metadata = img.metadata_json or {}
                            char_settings = metadata.get(
                                "characterSettings", character_settings
                            )

                            # 构建描述
                            description = img.prompt_text or "一个普通人"
                            era = "现代"
                            if char_settings:
                                era = (
                                    self._extract_era_from_settings(char_settings)
                                    or "现代"
                                )

                            new_images = image_service.generate_character_image(
                                game_id=game_id,
                                name=img.entity_name,
                                description=description,
                                era=era,
                                entity_key=img.entity_key,
                                metadata=metadata,
                                num_images=1,
                            )

                            if new_images:
                                logger.info(
                                    f"[SessionService] Character image regenerated: "
                                    f"entity_name={img.entity_name}, new_image_id={new_images[0].image_id}"
                                )

                        except Exception as img_e:
                            logger.error(
                                f"[SessionService] Failed to regenerate character image "
                                f"entity_name={img.entity_name}: {img_e}"
                            )

                finally:
                    db.close()

            except Exception as e:
                logger.error(
                    f"[SessionService] Failed to regenerate character images in background: {e}"
                )

        # 启动后台线程
        thread = threading.Thread(target=regenerate_in_background, daemon=True)
        thread.start()

    def _extract_era_from_settings(
        self, char_settings: Dict[str, Any]
    ) -> Optional[str]:
        """从角色设定中提取时代名称"""
        era = char_settings.get("era")
        if era:
            if isinstance(era, dict):
                era_name = era.get("era_name")
                if era_name and era_name.strip():
                    return era_name.strip()

                era_desc = era.get("era_description")
                if era_desc and era_desc.strip():
                    desc = era_desc.strip()
                    for sep in ["。", "，", ",", "."]:
                        if sep in desc:
                            desc = desc.split(sep)[0]
                            break
                    if len(desc) > 30:
                        desc = desc[:30]
                    return desc

                return None
            elif isinstance(era, str):
                if len(era) > 30:
                    return era[:30]
                return era
        return None

    def _check_and_generate_illustration(
        self,
        db,
        game_id: int,
        week: int,
        round_number: int,
        stage: str,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        image_storage=None,
    ) -> None:
        """
        检查指定轮次的插画是否存在，如果不存在或文件丢失则触发后台生成。

        Args:
            db: 数据库会话
            game_id: 游戏 ID
            week: 周数
            round_number: 轮次
            stage: 阶段 (event/result)
            story_text: 故事文本
            character_settings: 角色设定
            player_name: 玩家名称
            image_storage: 图片存储服务（用于检查文件存在）
        """
        from src.database.models import SceneImage

        # 检查插画记录是否存在
        existing = (
            db.query(SceneImage)
            .filter(
                SceneImage.game_id == game_id,
                SceneImage.week == week,
                SceneImage.round_number == round_number,
                SceneImage.stage == stage,
            )
            .first()
        )

        if existing:
            # 检查文件是否真实存在
            if image_storage and existing.storage_path:
                if not image_storage.image_exists(
                    existing.storage_path, existing.storage_type
                ):
                    logger.warning(
                        f"[SessionService] Scene image file missing: "
                        f"scene_id={existing.scene_id}, storage_path={existing.storage_path}, "
                        f"triggering regeneration..."
                    )
                    # 标记为丢失，触发重新生成
                    existing.importance_score = "missing"
                    db.commit()
                    # 继续执行生成逻辑
                else:
                    week_display = f"第{week + 1}周" if week is not None else "未知周"
                    logger.debug(
                        f"[SessionService] 插画已存在且有效: "
                        f"game={game_id}, {week_display}, round={round_number}, stage={stage}"
                    )
                    return
            else:
                # 没有存储服务，只检查记录
                week_display = f"第{week + 1}周" if week is not None else "未知周"
                logger.debug(
                    f"[SessionService] 插画记录已存在: "
                    f"game={game_id}, {week_display}, round={round_number}, stage={stage}"
                )
                return

        week_display = f"第{week + 1}周" if week is not None else "未知周"
        logger.info(
            f"[SessionService] 检测到缺失插画: "
            f"game={game_id}, {week_display}, round={round_number}, stage={stage}, "
            f"触发生成..."
        )

        # 触发后台生成
        self._trigger_illustration_generation(
            game_id=game_id,
            week=week,
            round_number=round_number,
            stage=stage,
            story_text=story_text,
            character_settings=character_settings,
            player_name=player_name,
        )

    def _trigger_illustration_generation(
        self,
        game_id: int,
        week: int,
        round_number: int,
        stage: str,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
    ) -> None:
        """
        在后台线程中触发生成插画。

        Args:
            game_id: 游戏 ID
            week: 周数
            round_number: 轮次
            stage: 阶段 (event/result)
            story_text: 故事文本
            character_settings: 角色设定
            player_name: 玩家名称
        """

        def generate_in_background():
            try:
                from src.ai.image_client import ImageClient
                from src.game.round.illustration_service import RoundIllustrationService
                from src.services.image_storage import ImageStorageService

                # 创建新的数据库会话（在线程中）
                db = SessionLocal()

                try:
                    image_client = ImageClient()
                    image_storage = ImageStorageService()
                    illustration_service = RoundIllustrationService(
                        image_client=image_client,
                        image_storage=image_storage,
                        db_session=db,
                    )

                    # 获取已有的图片列表（用于参考）
                    from src.database.models import Image as ImageModel

                    existing_images = (
                        db.query(ImageModel).filter(ImageModel.game_id == game_id).all()
                    )

                    existing_image_list = [
                        {
                            "image_id": img.image_id,
                            "entity_name": img.entity_name,
                            "image_type": img.image_type,
                            "storage_path": img.storage_path,
                            "storage_type": img.storage_type,
                            "entity_key": img.entity_key,
                        }
                        for img in existing_images
                    ]

                    # 生成插画
                    illustration_service._generate_round_illustration_sync(
                        game_id=game_id,
                        round_number=round_number,
                        story_text=story_text,
                        character_settings=character_settings,
                        player_name=player_name,
                        existing_images=existing_image_list,
                        stage=stage,
                        week=week,
                    )

                    week_display = f"第{week + 1}周" if week is not None else "未知周"
                    logger.info(
                        f"[SessionService] 后台插画生成完成: game={game_id}, {week_display}, round={round_number}, stage={stage}"
                    )

                finally:
                    db.close()

            except Exception as e:
                logger.error(
                    f"[SessionService] Failed to generate illustration in background: {e}"
                )

        # 启动后台线程
        thread = threading.Thread(target=generate_in_background, daemon=True)
        thread.start()


# 全局单例
session_service = SessionService()
