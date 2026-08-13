"""Game initialization - creates new game sessions from character settings."""

import logging
import re
from typing import Any, Dict, Optional, Tuple

from config.settings import settings
from config.feature_flags import get_feature
from src.database.db import GameDatabase
from src.game.game_loop import GameLoop

logger = logging.getLogger(__name__)


def _coerce_initial_wealth_amount(value: Any) -> Optional[int]:
    """Coerce explicit generated wealth values while ignoring qualitative labels."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, min(1_000_000, int(value)))
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    compact = re.sub(r"[\s,，￥¥$元人民币rmbRMB]+", "", text)
    if not compact:
        return None

    ten_thousand_match = re.search(r"(\d+(?:\.\d+)?)万", compact)
    if ten_thousand_match:
        return max(0, min(1_000_000, int(float(ten_thousand_match.group(1)) * 10_000)))

    number_match = re.search(r"\d+(?:\.\d+)?", compact)
    if not number_match:
        return None

    return max(0, min(1_000_000, int(float(number_match.group(0)))))


def extract_initial_wealth_from_settings(character_settings: Dict[str, Any]) -> Optional[int]:
    """Return numeric initial wealth from character settings, if explicitly generated."""
    wealth_setting = character_settings.get("wealth")
    if not isinstance(wealth_setting, dict):
        return None

    for key in ("wealth", "starting_wealth", "initial_wealth_amount", "initial_wealth"):
        wealth = _coerce_initial_wealth_amount(wealth_setting.get(key))
        if wealth is not None:
            return wealth

    return None


def _initial_wealth_from_settings(character_settings: Dict[str, Any]) -> int:
    configured_wealth = extract_initial_wealth_from_settings(character_settings)
    return configured_wealth if configured_wealth is not None else settings.INITIAL_WEALTH


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
        character_settings = dict(character_settings)
        if get_feature("daily_timeline_v2"):
            character_settings = self._normalize_daily_start_date(character_settings)
        character_settings["relationships"] = self._normalize_relationships_settings(
            character_settings.get("relationships", {})
        )

        # 提取 constraint_level（从 character_settings 或默认 expert）
        constraint_level = (
            character_settings.get("constraint_level", "expert") if character_settings else "expert"
        )

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
            "wealth": _initial_wealth_from_settings(character_settings),
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
            "constraint_level": constraint_level,
        }
        if get_feature("daily_timeline_v2"):
            from src.game.daily_timeline import build_daily_timeline

            initial_state["timeline_version"] = 2
            initial_state["timeline"] = build_daily_timeline(
                start_date=character_settings["start_date"], day_index=0
            )
            initial_state["day_history"] = []
            initial_state["next_age_day"] = 365

        # Initialize relationships from character settings
        self._initialize_relationships(initial_state, character_settings)

        # Seed the P1-7 continuity authority before the initial state is
        # persisted. This makes the first generation subject to the same
        # canonical identity rules as every later round.
        from src.game.continuity_ledger import ContinuityLedger

        ledger = ContinuityLedger.from_state(initial_state)
        ledger.persist(initial_state)

        from src.game.wealth_ledger import WealthLedger

        wealth_ledger = WealthLedger.from_player_state(initial_state)
        wealth_ledger.persist(initial_state)

        # 提取 narrative_style_id（从 character_settings 中获取，默认 None）
        style_id = character_settings.get("narrative_style_id") if character_settings else None

        # 当无 narrative_style_id 时自动匹配风格
        if not style_id and character_settings:
            try:
                from src.ai.narrative.style_matcher import auto_match_style

                result = auto_match_style(character_settings)
                if result.confidence >= 0.15:  # 最低置信度阈值
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

        if style_id:
            initial_state["narrative_style_id"] = style_id

        # Save the initial game state to database
        if self.game_db:
            game_id = self.game_db.create_game(
                language=self.language,
                initial_state=initial_state,
                user_id=user_id,
                narrative_style_id=style_id,
                constraint_level=constraint_level,
            )
            logger.info(
                f"Created new game: game_id={game_id}, player={player_name}, user_id={user_id}, "
                f"constraint_level={constraint_level}"
            )
        else:
            # If no database, generate a fake ID
            import time

            game_id = int(time.time() * 1000) % 1000000
            logger.warning(f"No database provided, using temporary game_id={game_id}")

        # Create GameLoop and load the state
        game_loop = GameLoop(language=self.language, quality_level=constraint_level)
        game_loop.load_game(initial_state)

        return game_loop, game_id

    @staticmethod
    def _normalize_daily_start_date(
        character_settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate the selected date and synchronize year-derived settings."""
        from datetime import date

        normalized = dict(character_settings)
        era = dict(normalized.get("era") or {})
        age = dict(normalized.get("age") or {})
        era_year = int(era.get("year", 2024))
        raw_start = normalized.get("start_date") or f"{era_year:04d}-01-01"
        parsed = date.fromisoformat(str(raw_start))
        era["year"] = parsed.year
        if "age" in age:
            age["birth_year"] = parsed.year - int(age["age"])
        normalized["start_date"] = parsed.isoformat()
        normalized["era"] = era
        normalized["age"] = age
        return normalized

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

    def _normalize_relationships_settings(self, relationships: Any) -> Dict[str, Any]:
        """Normalize accepted relationship payload variants to the canonical dict shape."""
        if isinstance(relationships, list):
            return {"key_people": relationships}
        if not isinstance(relationships, dict):
            return {"key_people": []}

        normalized = dict(relationships)
        key_people = normalized.get("key_people", [])
        if not isinstance(key_people, list):
            key_people = []
        normalized["key_people"] = key_people
        return normalized
