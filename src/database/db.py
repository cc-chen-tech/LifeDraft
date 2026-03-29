"""Database operations - Facade pattern wrapping individual repositories.

This module provides backward compatibility by delegating all operations
to specialized repository classes. Existing consumers can continue using
GameDatabase without any changes to their import paths.
"""

import logging
from typing import Any, Dict, List, Optional

from src.database.character_preset_repository import CharacterPresetRepository
from src.database.decision_repository import DecisionRepository
from src.database.game_repository import GameRepository
from src.database.models import (CharacterPreset, Decision, Game, SessionLocal,
                                 get_db, init_db)
from src.database.save_point_repository import SavePointRepository
from src.database.session_repository import SessionRepository
from src.database.state_repository import StateRepository
from src.game.state import PlayerState

logger = logging.getLogger(__name__)


class GameDatabase:
    """Database operations for game persistence.

    This is a Facade class that delegates all operations to specialized
    repository classes for better code organization and maintainability.

    Repositories:
        - GameRepository: Game CRUD operations (create/get/list/delete)
        - StateRepository: Game state read/write operations
        - DecisionRepository: Decision history and story search
        - CharacterPresetRepository: Character preset CRUD
        - SessionRepository: Active game session management
        - SavePointRepository: Time rewind save system
    """

    def __init__(self):
        """Initialize database and repositories."""
        init_db()
        self._game_repo = GameRepository()
        self._state_repo = StateRepository()
        self._decision_repo = DecisionRepository()
        self._preset_repo = CharacterPresetRepository()
        self._session_repo = SessionRepository()
        self._save_point_repo = SavePointRepository()

    # ==================== Game CRUD ====================

    def create_game(
        self,
        language: str = "en",
        initial_state: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
    ) -> int:
        """Create a new game record."""
        return self._game_repo.create_game(language, initial_state, user_id)

    def get_game(self, game_id: int, user_id: Optional[int] = None) -> Optional[Game]:
        """Get game record."""
        return self._game_repo.get_game(game_id, user_id)

    def list_games(self, limit: int = 50, user_id: Optional[int] = None) -> List[Game]:
        """List recent games."""
        return self._game_repo.list_games(limit, user_id)

    def list_saved_games(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取用户的已保存游戏列表（包含详细信息）。"""
        return self._game_repo.list_saved_games(user_id, limit)

    def delete_saved_game(self, game_id: int, user_id: int) -> bool:
        """删除已保存的游戏（验证用户权限）。"""
        return self._game_repo.delete_saved_game(game_id, user_id)

    def save_ending(
        self,
        game_id: int,
        final_state: Dict[str, Any],
        ending_type: str,
        summary: str,
        achievements: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save game ending."""
        return self._game_repo.save_ending(game_id, final_state, ending_type, summary, achievements)

    # ==================== State Read/Write ====================

    def save_state(self, game_id: int, player_state: PlayerState) -> None:
        """Save a game state snapshot."""
        return self._state_repo.save_state(game_id, player_state)

    def load_game_state(self, game_id: int) -> Optional[Dict[str, Any]]:
        """Load the latest game state."""
        return self._state_repo.load_game_state(game_id)

    def save_game_progress(self, game_id: int, player_state: "PlayerState") -> bool:
        """保存游戏进度（更新最新状态）。"""
        return self._state_repo.save_game_progress(game_id, player_state)

    def load_saved_game(self, game_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """加载已保存的游戏（验证用户权限）。"""
        return self._state_repo.load_saved_game(game_id, user_id)

    # ==================== Decision History ====================

    def save_decision(
        self,
        game_id: int,
        week: int,
        event_description: str,
        choice_text: str,
        effects: Dict[str, Any],
    ) -> None:
        """Save a decision record."""
        return self._decision_repo.save_decision(
            game_id, week, event_description, choice_text, effects
        )

    def get_decision_history(self, game_id: int) -> List[Decision]:
        """Get decision history for a game."""
        return self._decision_repo.get_decision_history(game_id)

    def get_story_history(self, game_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """获取历史故事文本，用于一致性验证和关键行为核查。"""
        return self._decision_repo.get_story_history(game_id, limit)

    def search_story_history(
        self, game_id: int, keywords: List[str], max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索历史故事中包含关键词的段落。"""
        return self._decision_repo.search_story_history(game_id, keywords, max_results)

    # ==================== Character Presets ====================

    def save_character_preset(
        self,
        preset_name: str,
        player_name: str,
        life_vision: str,
        character_settings: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> int:
        """Save a character preset."""
        return self._preset_repo.save_character_preset(
            preset_name, player_name, life_vision, character_settings, user_id
        )

    def load_character_preset(
        self, preset_id: int, user_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Load a character preset."""
        return self._preset_repo.load_character_preset(preset_id, user_id)

    def list_character_presets(
        self, limit: int = 50, user_id: Optional[int] = None
    ) -> List[CharacterPreset]:
        """List character presets."""
        return self._preset_repo.list_character_presets(limit, user_id)

    def delete_character_preset(self, preset_id: int, user_id: Optional[int] = None) -> bool:
        """Delete a character preset."""
        return self._preset_repo.delete_character_preset(preset_id, user_id)

    # ==================== Session Management ====================

    def set_active_game(self, user_id: int, game_id: int) -> bool:
        """设置用户当前活跃的游戏ID。"""
        return self._session_repo.set_active_game(user_id, game_id)

    def get_active_game(self, user_id: int) -> Optional[int]:
        """获取用户当前活跃的游戏ID。"""
        return self._session_repo.get_active_game(user_id)

    def clear_active_game(self, user_id: int) -> bool:
        """清除用户的活跃游戏ID。"""
        return self._session_repo.clear_active_game(user_id)

    # ==================== Save Points (Time Rewind) ====================

    def create_save_point(
        self,
        game_id: int,
        user_id: int,
        player_state: "PlayerState",
        save_name: Optional[str] = None,
    ) -> Optional[int]:
        """创建存档点（手动存档）。"""
        return self._save_point_repo.create_save_point(game_id, user_id, player_state, save_name)

    def list_save_points(self, game_id: int, user_id: int) -> List[Dict[str, Any]]:
        """列出游戏的所有存档点。"""
        return self._save_point_repo.list_save_points(game_id, user_id)

    def load_save_point(self, state_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """加载特定存档点（时间回溯）。"""
        return self._save_point_repo.load_save_point(state_id, user_id)

    def delete_save_point(self, state_id: int, user_id: int) -> bool:
        """删除存档点。"""
        return self._save_point_repo.delete_save_point(state_id, user_id)

    def get_all_states_for_game(
        self, game_id: int, user_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取游戏的所有状态快照（用于时间线展示）。"""
        return self._save_point_repo.get_all_states_for_game(game_id, user_id, limit)
