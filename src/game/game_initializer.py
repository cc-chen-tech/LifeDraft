"""Game initialization - creates new game sessions from character settings."""

import logging
from typing import Any, Dict, Optional, Tuple

from config.settings import settings
from src.database.db import GameDatabase
from src.game.game_loop import GameLoop

logger = logging.getLogger(__name__)


class GameInitializer:
    """Handles initialization of new game sessions from character settings."""

    def __init__(self, game_db: Optional[GameDatabase] = None, language: str = "zh"):
        """
        Initialize the game initializer.

        Args:
            game_db: Database instance for saving games
            language: Language code for the game
        """
        self.game_db = game_db
        self.language = language

    def initialize_game_from_settings(
        self,
        character_settings: Dict[str, Any],
        player_name: str,
        life_vision: str,
        user_id: Optional[int] = None,
    ) -> Tuple[GameLoop, int]:
        """
        Initialize a new game from character settings.

        Args:
            character_settings: Character configuration from frontend
            player_name: Player's chosen name
            life_vision: Player's life vision/goals
            user_id: Optional user ID for logged-in users

        Returns:
            Tuple of (GameLoop instance, game_id)

        Raises:
            ValueError: If required settings are missing
        """
        if not character_settings:
            raise ValueError("character_settings is required")
        if not player_name:
            raise ValueError("player_name is required")

        # Create initial player state
        initial_state = {
            "player_name": player_name,
            "life_vision": life_vision,
            "character_settings": character_settings,
            "age": character_settings.get("age", {}).get("age", settings.STARTING_AGE),
            "week": 0,
            "current_round": 0,
            "energy": settings.INITIAL_ENERGY,
            "mood": settings.INITIAL_MOOD,
            "knowledge": settings.INITIAL_KNOWLEDGE,
            "wealth": settings.INITIAL_WEALTH,
            "relationships": {},
            "characters": {},
            "decision_history": [],
            "story_history": [],
            "four_week_summaries": [],
            "yearly_summaries": [],
            "round_history": [],
            "weekly_summaries": [],
            "pending_storylines": [],
            "established_facts": [],
            "foreshadowing_seeds": [],
            "character_habits": [],
            "pending_character_introductions": [],
        }

        # Initialize relationships from character settings
        self._initialize_relationships(initial_state, character_settings)

        # 提取 narrative_style_id（从 character_settings 中获取，默认 None）
        style_id = character_settings.get("narrative_style_id") if character_settings else None

        # 当无 narrative_style_id 时自动匹配风格
        if not style_id and character_settings:
            try:
                from src.ai.narrative.style_matcher import auto_match_style

                result = auto_match_style(character_settings)
                if result.confidence >= 0.3:  # 最低置信度阈值
                    style_id = result.style_id
                    logger.info(
                        f"Auto-matched narrative style: {result.style_id} "
                        f"(confidence={result.confidence:.2f})"
                    )
                else:
                    logger.info(
                        f"Style auto-match confidence too low: {result.confidence:.2f}, "
                        f"skipping style assignment"
                    )
            except Exception as e:
                logger.warning(f"Style auto-match failed: {e}")

        # Save the initial game state to database
        if self.game_db:
            game_id = self.game_db.create_game(
                language=self.language,
                initial_state=initial_state,
                user_id=user_id,
                narrative_style_id=style_id,
            )
            logger.info(
                f"Created new game: game_id={game_id}, player={player_name}, user_id={user_id}"
            )
        else:
            # If no database, generate a fake ID
            import time

            game_id = int(time.time() * 1000) % 1000000
            logger.warning(f"No database provided, using temporary game_id={game_id}")

        # Create GameLoop and load the state
        game_loop = GameLoop(language=self.language)
        game_loop.load_game(initial_state)

        return game_loop, game_id

    def _initialize_relationships(
        self, initial_state: Dict[str, Any], character_settings: Dict[str, Any]
    ) -> None:
        """
        Initialize relationships and characters from settings.

        Args:
            initial_state: Initial state dictionary to populate
            character_settings: Character configuration
        """
        relationships = character_settings.get("relationships", {})

        # Initialize key people relationships
        key_people = relationships.get("key_people", [])
        for person in key_people:
            if isinstance(person, dict) and "name" in person:
                name = person["name"]
                if name:  # Skip empty names
                    # Default affinity is neutral (50)
                    initial_state["relationships"][name] = 50

                    # If detailed character data exists, initialize CharacterState
                    if "role" in person or "personality" in person:
                        initial_state["characters"][name] = {
                            "name": name,
                            "role": person.get("role", ""),
                            "personality": person.get("personality", ""),
                            "background": person.get("background", ""),
                            "appearance": person.get("appearance", ""),
                            "affinity": 50,
                            "mood": 60,
                            "trust": 50,
                            "active": True,
                            "last_interaction_week": 0,
                            "interaction_count": 0,
                            "status_notes": [],
                        }

        logger.debug(f"Initialized {len(initial_state['relationships'])} relationships")
