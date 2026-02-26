"""Session management service - unified session get/restore logic.

This module consolidates the duplicated session restoration logic that was
previously scattered across gameplay.py and games.py.

Usage:
    from src.api.services.session_service import session_service
    
    session = session_service.get_or_restore(game_id, user_id)
"""
import logging
import threading
from typing import Optional, Dict, Any, List

from fastapi import HTTPException

from src.api.deps import get_db
from src.api.session_store import session_store, GameLoopSession
from src.database.models import SessionLocal  # ★ 添加 SessionLocal 导入
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
    
    def get(self, game_id: int, user_id: Optional[int] = None) -> Optional[GameLoopSession]:
        """获取内存中的 session，不自动恢复。
        
        Args:
            game_id: 游戏 ID
            user_id: 用户 ID（可选）
        
        Returns:
            GameLoopSession 或 None（如果不存在或已过期）
        """
        return session_store.get(game_id, user_id)
    
    def get_or_restore(
        self, 
        game_id: int, 
        user_id: Optional[int] = None
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
        logger.info(f"Session not in memory for game_id={game_id}, attempting auto-restore from database...")
        return self._restore_from_database(game_id, user_id)
    
    def _restore_from_database(
        self, 
        game_id: int, 
        user_id: Optional[int]
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
            db = get_db()
            state_data = db.load_saved_game(game_id, user_id)
            
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
            session = session_store.put(game_id, game_loop, user_id=user_id, language=language)
            logger.info(f"Auto-restored session from database: game_id={game_id}, has_current_event={game_loop.current_event is not None}")
            
            # ★ 检查并补充缺失的场景插画
            self._check_and_generate_missing_illustrations(game_id, game_loop, state_data)
            
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
        如果不存在则触发后台生成。
        
        Args:
            game_id: 游戏 ID
            game_loop: GameLoop 实例
            state_data: 游戏状态数据
        """
        try:
            from src.database.models import SceneImage
            db = SessionLocal()  # ★ 使用 SessionLocal 获取真正的 SQLAlchemy session
            try:
                player_state = game_loop.player_state
                current_week = player_state.week
                current_round = player_state.current_round
                
                # 1. 检查当前轮次的插画
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
                    )
                
                logger.info(f"[SessionService] Illustration check completed for game_id={game_id}")
            except Exception as inner_e:
                logger.warning(f"[SessionService] Illustration query failed: {inner_e}")
            finally:
                db.close()  # ★ 确保关闭 session
                
        except Exception as e:
            # 图片生成失败不应该影响 session 恢复
            logger.warning(f"[SessionService] Failed to check/generate illustrations: {e}")
    
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
    ) -> None:
        """
        检查指定轮次的插画是否存在，如果不存在则触发后台生成。
        
        Args:
            db: 数据库会话
            game_id: 游戏 ID
            week: 周数
            round_number: 轮次
            stage: 阶段 (event/result)
            story_text: 故事文本
            character_settings: 角色设定
            player_name: 玩家名称
        """
        from src.database.models import SceneImage
        
        # 检查插画是否存在
        existing = db.query(SceneImage).filter(
            SceneImage.game_id == game_id,
            SceneImage.week == week,
            SceneImage.round_number == round_number,
            SceneImage.stage == stage,
        ).first()
        
        if existing:
            logger.debug(f"[SessionService] Illustration exists: game={game_id}, week={week}, round={round_number}, stage={stage}")
            return
        
        logger.info(f"[SessionService] Missing illustration detected: game={game_id}, week={week}, round={round_number}, stage={stage}, triggering generation...")
        
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
                from src.services.image_storage import ImageStorageService
                from src.game.round.illustration_service import RoundIllustrationService
                
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
                    existing_images = db.query(ImageModel).filter(
                        ImageModel.game_id == game_id
                    ).all()
                    
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
                    
                    logger.info(f"[SessionService] Background illustration generated: game={game_id}, week={week}, round={round_number}, stage={stage}")
                    
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"[SessionService] Failed to generate illustration in background: {e}")
        
        # 启动后台线程
        thread = threading.Thread(target=generate_in_background, daemon=True)
        thread.start()


# 全局单例
session_service = SessionService()
