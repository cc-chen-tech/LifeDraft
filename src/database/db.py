"""Database operations."""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from src.database.models import Game, GameState, Decision, Ending, CharacterPreset, init_db, get_db, SessionLocal
from src.game.state import PlayerState

logger = logging.getLogger(__name__)


class GameDatabase:
    """Database operations for game persistence."""
    
    def __init__(self):
        """Initialize database."""
        init_db()
    
    def create_game(
        self,
        language: str = "en",
        initial_state: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None
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
                language=language,
                initial_state=initial_state or {},
                user_id=user_id
            )
            db.add(game)
            db.commit()
            db.refresh(game)
            return game.game_id
        finally:
            db.close()
    
    def save_state(
        self,
        game_id: int,
        player_state: PlayerState
    ) -> None:
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
                state_json=player_state.to_dict()
            )
            db.add(state)
            db.commit()
    
    def save_decision(
        self,
        game_id: int,
        week: int,
        event_description: str,
        choice_text: str,
        effects: Dict[str, Any]
    ) -> None:
        """
        Save a decision record.
        
        Args:
            game_id: Game ID
            week: Week number
            event_description: Event description
            choice_text: Chosen option text
            effects: Effects dictionary
        """
        with get_db() as db:
            decision = Decision(
                game_id=game_id,
                week=week,
                event_description=event_description,
                choice_text=choice_text,
                effects=effects
            )
            db.add(decision)
            db.commit()
    
    def save_ending(
        self,
        game_id: int,
        final_state: Dict[str, Any],
        ending_type: str,
        summary: str,
        achievements: Optional[Dict[str, Any]] = None
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
                achievements=achievements or {}
            )
            db.add(ending)
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
            state = db.query(GameState).filter(
                GameState.game_id == game_id
            ).order_by(GameState.week.desc()).first()
            
            if state:
                return state.state_json
            
            # If no snapshots found, fallback to the initial state in the Game record
            game = db.query(Game).filter(Game.game_id == game_id).first()
            if game:
                return game.initial_state
                
            return None
    
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
    
    def get_decision_history(self, game_id: int) -> List[Decision]:
        """Get decision history for a game."""
        db = SessionLocal()
        try:
            return db.query(Decision).filter(
                Decision.game_id == game_id
            ).order_by(Decision.week).all()
        finally:
            db.close()
    
    def get_story_history(self, game_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        ★ 获取历史故事文本，用于一致性验证和关键行为核查。
        
        Args:
            game_id: 游戏ID
            limit: 最多返回的故事数量
        
        Returns:
            故事列表，每个包含 week, story_text, choice_text
        """
        db = SessionLocal()
        try:
            decisions = db.query(Decision).filter(
                Decision.game_id == game_id
            ).order_by(Decision.week.desc()).limit(limit).all()
            
            return [
                {
                    "week": d.week,
                    "story_text": d.event_description,
                    "choice_text": d.choice_text,
                    "created_at": d.created_at.isoformat() if d.created_at else None
                }
                for d in reversed(decisions)  # 反转为时间顺序
            ]
        finally:
            db.close()
    
    def search_story_history(
        self, 
        game_id: int, 
        keywords: List[str], 
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        ★ 搜索历史故事中包含关键词的段落，用于验证捕捉事实是否被忽略。
        
        Args:
            game_id: 游戏ID
            keywords: 要搜索的关键词列表
            max_results: 最多返回结果数
        
        Returns:
            包含关键词的故事片段列表
        """
        db = SessionLocal()
        try:
            decisions = db.query(Decision).filter(
                Decision.game_id == game_id
            ).order_by(Decision.week).all()
            
            results = []
            for d in decisions:
                story_lower = d.event_description.lower() if d.event_description else ""
                for kw in keywords:
                    if kw.lower() in story_lower:
                        results.append({
                            "week": d.week,
                            "story_text": d.event_description,
                            "matched_keyword": kw,
                        })
                        break  # 一个故事只记录一次
                
                if len(results) >= max_results:
                    break
            
            return results
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
            games = db.query(Game).filter(
                Game.user_id == user_id,
                Game.ending_type.is_(None)  # 只显示未结束的游戏
            ).order_by(Game.updated_at.desc()).limit(limit).all()
            
            result = []
            for game in games:
                # 获取最新的游戏状态
                latest_state = db.query(GameState).filter(
                    GameState.game_id == game.game_id
                ).order_by(GameState.week.desc()).first()
                
                # 从 initial_state 或 latest_state 获取信息
                state_data = latest_state.state_json if latest_state else game.initial_state
                initial_data = game.initial_state or {}
                
                # player_name 优先从 initial_state 获取（因为旧的 game_states 可能没有这个字段）
                player_name = (
                    state_data.get("player_name") or 
                    initial_data.get("player_name") or 
                    ""  # ★ 返回空字符串，让前端决定显示什么
                ) if state_data else initial_data.get("player_name", "")
                week = state_data.get("week", 1) if state_data else 1
                age = state_data.get("age", 22) if state_data else 22
                
                result.append({
                    "game_id": game.game_id,
                    "player_name": player_name,
                    "week": week,
                    "age": age,
                    "created_at": game.created_at,
                    "updated_at": game.updated_at,
                    "has_progress": latest_state is not None
                })
            
            return result
        finally:
            db.close()
    
    def save_game_progress(self, game_id: int, player_state: 'PlayerState') -> bool:
        """
        保存游戏进度（更新最新状态）。
        
        Args:
            game_id: 游戏ID
            player_state: 当前玩家状态
        
        Returns:
            是否成功
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not player_state:
            logger.error(f"save_game_progress: player_state is None for game_id={game_id}")
            return False
        
        # ★ 显示用周数（人类可读，从1开始）
        week_display = f"第{player_state.week + 1}周" if player_state.week is not None else "未知周"
        logger.info(f"save_game_progress: Saving game_id={game_id}, {week_display}, age={player_state.age}")
        
        db = SessionLocal()
        try:
            # 保存新的状态快照
            state = GameState(
                game_id=game_id,
                week=player_state.week,
                age=player_state.age,
                state_json=player_state.to_dict()
            )
            db.add(state)
            
            # 更新 Game 表的 updated_at
            game = db.query(Game).filter(Game.game_id == game_id).first()
            if game:
                game.updated_at = datetime.utcnow()
                logger.info(f"save_game_progress: Updated game {game_id} updated_at")
            else:
                logger.warning(f"save_game_progress: Game {game_id} not found in database")
            
            db.commit()
            logger.info(f"save_game_progress: Successfully saved game_id={game_id}")
            return True
        except Exception as e:
            logger.error(f"save_game_progress: Failed to save game_id={game_id}, error={e}")
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
            game = db.query(Game).filter(
                Game.game_id == game_id,
                Game.user_id == user_id
            ).first()
            
            if not game:
                return None
            
            # 获取最新状态（按创建时间降序，确保返回最新的记录）
            latest_state = db.query(GameState).filter(
                GameState.game_id == game_id
            ).order_by(GameState.created_at.desc()).first()
            
            state_data = latest_state.state_json if latest_state else game.initial_state
            initial_data = game.initial_state or {}
            
            if state_data:
                state_data["_game_id"] = game_id  # 添加 game_id 以便后续保存
                
                # 从 initial_state 补充 player_name 和 life_vision（旧存档可能没有这些字段）
                if not state_data.get("player_name") and initial_data.get("player_name"):
                    state_data["player_name"] = initial_data["player_name"]
                if not state_data.get("life_vision") and initial_data.get("life_vision"):
                    state_data["life_vision"] = initial_data["life_vision"]
            
            return state_data
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
            game = db.query(Game).filter(
                Game.game_id == game_id,
                Game.user_id == user_id
            ).first()
            
            if game:
                db.delete(game)  # cascade 会自动删除关联的 states 和 decisions
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    # Character preset methods
    def save_character_preset(
        self,
        preset_name: str,
        player_name: str,
        life_vision: str,
        character_settings: Dict[str, Any],
        user_id: Optional[int] = None
    ) -> int:
        """
        Save a character preset.
        
        Args:
            preset_name: Name for the preset
            player_name: Player name
            life_vision: Life vision text
            character_settings: Character settings dictionary
            user_id: 用户ID（可选）
        
        Returns:
            Preset ID
        """
        db = SessionLocal()
        try:
            preset = CharacterPreset(
                preset_name=preset_name,
                player_name=player_name,
                life_vision=life_vision,
                character_settings=character_settings,
                user_id=user_id
            )
            db.add(preset)
            db.commit()
            db.refresh(preset)
            return preset.preset_id
        finally:
            db.close()
    
    def load_character_preset(self, preset_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Load a character preset.
        
        Args:
            preset_id: Preset ID
            user_id: 用户ID，如果提供则验证所有权（允许公共预设）
        
        Returns:
            Preset dictionary or None
        """
        from sqlalchemy import or_
        db = SessionLocal()
        try:
            query = db.query(CharacterPreset).filter(
                CharacterPreset.preset_id == preset_id
            )
            # 如果提供了 user_id，验证所有权（允许自己的和公共的）
            if user_id is not None:
                query = query.filter(
                    or_(
                        CharacterPreset.user_id == user_id,
                        CharacterPreset.user_id.is_(None),
                    )
                )
            
            preset = query.first()
            
            if preset:
                return {
                    "preset_id": preset.preset_id,
                    "preset_name": preset.preset_name,
                    "player_name": preset.player_name,
                    "life_vision": preset.life_vision,
                    "character_settings": preset.character_settings,
                    "created_at": preset.created_at.isoformat() if preset.created_at else None
                }
            return None
        finally:
            db.close()
    
    def list_character_presets(self, limit: int = 50, user_id: Optional[int] = None) -> List[CharacterPreset]:
        """
        List character presets.
        
        Args:
            limit: Maximum number of presets to return
            user_id: 用户ID，如果提供则返回该用户的预设 + 公共预设
        
        Returns:
            List of presets
        """
        from sqlalchemy import or_
        db = SessionLocal()
        try:
            query = db.query(CharacterPreset)
            if user_id is not None:
                # 登录用户：看到自己的预设 + 公共预设（user_id 为 NULL 的）
                query = query.filter(
                    or_(
                        CharacterPreset.user_id == user_id,
                        CharacterPreset.user_id.is_(None),
                    )
                )
            else:
                # 未登录用户：只能看到公共预设
                query = query.filter(CharacterPreset.user_id.is_(None))
            return query.order_by(
                CharacterPreset.updated_at.desc()
            ).limit(limit).all()
        finally:
            db.close()
    
    def delete_character_preset(self, preset_id: int, user_id: Optional[int] = None) -> bool:
        """
        Delete a character preset.
        
        Args:
            preset_id: Preset ID
            user_id: 用户ID，如果提供则验证所有权
        
        Returns:
            True if deleted, False if not found or not authorized
        """
        db = SessionLocal()
        try:
            query = db.query(CharacterPreset).filter(
                CharacterPreset.preset_id == preset_id
            )
            # 如果提供了 user_id，验证所有权（但允许删除 user_id 为 NULL 的旧数据）
            if user_id is not None:
                from sqlalchemy import or_
                query = query.filter(
                    or_(
                        CharacterPreset.user_id == user_id,
                        CharacterPreset.user_id.is_(None)  # Allow deleting orphaned presets
                    )
                )
            
            preset = query.first()
            
            if preset:
                db.delete(preset)
                db.commit()
                return True
            return False
        finally:
            db.close()

    # ==================== 服务端会话管理 ====================

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
        from src.database.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                user.last_active_game_id = game_id
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
        from src.database.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user and user.last_active_game_id:
                # 验证游戏是否仍然存在且属于该用户
                game = db.query(Game).filter(
                    Game.game_id == user.last_active_game_id,
                    Game.user_id == user_id
                ).first()
                if game:
                    return user.last_active_game_id
                else:
                    # 游戏已被删除，清除引用
                    user.last_active_game_id = None
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
        from src.database.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                user.last_active_game_id = None
                db.commit()
                return True
            return False
        finally:
            db.close()
    
    # ==================== 时间回溯存档系统 ====================
    
    def create_save_point(self, game_id: int, user_id: int, player_state: 'PlayerState', save_name: Optional[str] = None) -> Optional[int]:
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
        import logging
        logger = logging.getLogger(__name__)
        
        db = SessionLocal()
        try:
            # 验证游戏属于该用户
            game = db.query(Game).filter(
                Game.game_id == game_id,
                Game.user_id == user_id
            ).first()
            
            if not game:
                logger.warning(f"create_save_point: Game {game_id} not found or not owned by user {user_id}")
                return None
            
            # 创建存档点
            save_point = GameState(
                game_id=game_id,
                week=player_state.week,
                age=player_state.age,
                state_json=player_state.to_dict(),
                is_save_point=True,
                save_name=save_name
            )
            db.add(save_point)
            
            # 更新 Game 表的 updated_at
            game.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(save_point)
            
            logger.info(f"create_save_point: Created save_point {save_point.state_id} for game {game_id}")
            return save_point.state_id
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
            game = db.query(Game).filter(
                Game.game_id == game_id,
                Game.user_id == user_id
            ).first()
            
            if not game:
                return []
            
            # 查询所有存档点
            save_points = db.query(GameState).filter(
                GameState.game_id == game_id,
                GameState.is_save_point == True
            ).order_by(GameState.created_at.desc()).all()
            
            result = []
            for sp in save_points:
                state = sp.state_json or {}
                result.append({
                    "state_id": sp.state_id,
                    "game_id": sp.game_id,
                    "week": sp.week,
                    "age": sp.age,
                    "save_name": sp.save_name,
                    "created_at": sp.created_at,
                    "player_name": state.get("player_name", "未命名"),
                })
            
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
            save_point = db.query(GameState).filter(
                GameState.state_id == state_id
            ).first()
            
            if not save_point:
                return None
            
            # 验证游戏属于该用户
            game = db.query(Game).filter(
                Game.game_id == save_point.game_id,
                Game.user_id == user_id
            ).first()
            
            if not game:
                return None
            
            state_data = save_point.state_json
            if state_data:
                state_data["_game_id"] = save_point.game_id
            
            return state_data
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
            save_point = db.query(GameState).filter(
                GameState.state_id == state_id,
                GameState.is_save_point == True
            ).first()
            
            if not save_point:
                return False
            
            # 验证游戏属于该用户
            game = db.query(Game).filter(
                Game.game_id == save_point.game_id,
                Game.user_id == user_id
            ).first()
            
            if not game:
                return False
            
            db.delete(save_point)
            db.commit()
            return True
        finally:
            db.close()
    
    def get_all_states_for_game(self, game_id: int, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
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
            game = db.query(Game).filter(
                Game.game_id == game_id,
                Game.user_id == user_id
            ).first()
            
            if not game:
                return []
            
            # 查询所有状态快照
            states = db.query(GameState).filter(
                GameState.game_id == game_id
            ).order_by(GameState.created_at.desc()).limit(limit).all()
            
            result = []
            for s in states:
                state = s.state_json or {}
                result.append({
                    "state_id": s.state_id,
                    "game_id": s.game_id,
                    "week": s.week,
                    "age": s.age,
                    "is_save_point": s.is_save_point,
                    "save_name": s.save_name,
                    "created_at": s.created_at,
                    "player_name": state.get("player_name", "未命名"),
                })
            
            return result
        finally:
            db.close()
