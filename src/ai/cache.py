"""Event caching system to reduce API calls."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import CACHE_DIR
from src.ai.models import GameEvent

logger = logging.getLogger(__name__)


class EventCache:
    """Cache for AI-generated events."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize event cache.

        Args:
            cache_dir: Directory for cache files (defaults to settings)
        """
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "events_cache.json"
        self._cache: Dict[str, Dict[str, Any]] = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load cache from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                return {}
        return {}

    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _generate_cache_key(self, player_state: Dict[str, Any], language: str) -> str:
        """
        Generate cache key from player state.

        Args:
            player_state: Player state dictionary
            language: Language code

        Returns:
            Cache key string
        """
        # Create a signature from relevant state attributes
        # Include decision history length to add variation
        decision_count = len(player_state.get("decision_history", []))

        # Round values to reduce cache misses from minor variations
        signature = {
            "age": player_state.get("age", 22),
            "energy": round(player_state.get("energy", 70) / 10) * 10,  # Round to nearest 10
            "mood": round(player_state.get("mood", 60) / 10) * 10,
            "knowledge": round(player_state.get("knowledge", 50) / 10) * 10,
            "wealth": round(player_state.get("wealth", 10000) / 10000)
            * 10000,  # Round to nearest 10000 for more variation
            "week": player_state.get("week", 0),
            "decision_count": decision_count,  # Add decision history length for variation
            "language": language,
        }

        # Create hash
        key_str = json.dumps(signature, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, player_state: Dict[str, Any], language: str) -> Optional[GameEvent]:
        """
        Get cached event if available.

        Args:
            player_state: Player state dictionary
            language: Language code

        Returns:
            Cached GameEvent or None
        """
        cache_key = self._generate_cache_key(player_state, language)
        cached = self._cache.get(cache_key)

        # Only use cache 30% of the time to ensure variety
        import random

        if cached and random.random() < 0.3:
            try:
                return GameEvent.from_json(json.dumps(cached))
            except Exception as e:
                logger.warning(f"Failed to parse cached event: {e}")
                return None

        return None

    def set(self, player_state: Dict[str, Any], language: str, event: GameEvent) -> None:
        """
        Cache an event.

        Args:
            player_state: Player state dictionary
            language: Language code
            event: GameEvent to cache
        """
        cache_key = self._generate_cache_key(player_state, language)

        # Convert event to dict
        event_dict = {
            "event_description": event.event_description,
            "options": [{"text": opt.text, "effects": opt.effects} for opt in event.options],
        }

        self._cache[cache_key] = event_dict
        self._save_cache()
        logger.info(f"Cached event with key: {cache_key[:8]}...")

    def clear(self) -> None:
        """Clear all cached events."""
        self._cache = {}
        self._save_cache()
        logger.info("Cache cleared")

    def size(self) -> int:
        """Get number of cached events."""
        return len(self._cache)
