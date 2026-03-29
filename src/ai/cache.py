"""Event caching system to reduce API calls."""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import CACHE_DIR
from src.ai.models import GameEvent

logger = logging.getLogger(__name__)


class EventCache:
    """Cache for AI-generated events.

    H-07: 支持 TTL 和大小限制，使用 LRU 策略淘汰旧条目。
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_size: int = 10000,
        ttl: int = 3600,
    ):
        """
        Initialize event cache.

        Args:
            cache_dir: Directory for cache files (defaults to settings)
            max_size: Maximum number of cached entries (H-07)
            ttl: Time-to-live in seconds for cache entries (H-07)
        """
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "events_cache.json"

        # H-07: TTL 和大小限制配置
        self.max_size = max_size
        self.ttl = ttl

        # H-07: 使用 OrderedDict 支持 LRU
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._timestamps: Dict[str, float] = {}

        # 加载持久化缓存（不带时间戳，这些条目会在首次访问时获得时间戳）
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # H-07: 转换为 OrderedDict
                    self._cache = OrderedDict(data)
                    # 为加载的条目设置当前时间戳
                    current_time = time.time()
                    for key in self._cache:
                        self._timestamps[key] = current_time
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                self._cache = OrderedDict()
                self._timestamps = {}

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

        if cache_key in self._cache:
            # H-07: 检查 TTL
            if time.time() - self._timestamps.get(cache_key, 0) > self.ttl:
                del self._cache[cache_key]
                self._timestamps.pop(cache_key, None)
                return None

            # H-07: LRU - 移到末尾
            self._cache.move_to_end(cache_key)

            # Only use cache 30% of the time to ensure variety
            import random

            if random.random() < 0.3:
                try:
                    return GameEvent.from_json(json.dumps(self._cache[cache_key]))
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

        # H-07: 如果 key 已存在，移到末尾
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)

        self._cache[cache_key] = event_dict
        self._timestamps[cache_key] = time.time()

        # H-07: 超出大小限制时淘汰最旧的
        while len(self._cache) > self.max_size:
            oldest_key, _ = self._cache.popitem(last=False)
            self._timestamps.pop(oldest_key, None)

        self._save_cache()
        logger.info(f"Cached event with key: {cache_key[:8]}...")

    def clear(self) -> None:
        """Clear all cached events."""
        self._cache = OrderedDict()
        self._timestamps = {}
        self._save_cache()
        logger.info("Cache cleared")

    def delete(self, key: str) -> None:
        """Delete a specific cache entry by key.

        Args:
            key: The cache key to delete
        """
        if key in self._cache:
            del self._cache[key]
            self._timestamps.pop(key, None)
            self._save_cache()

    def size(self) -> int:
        """Get number of cached events."""
        return len(self._cache)
