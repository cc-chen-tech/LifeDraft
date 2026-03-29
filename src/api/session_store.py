"""GameLoop session store — manages in-memory GameLoop instances per user session."""

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from src.game.game_loop import GameLoop

logger = logging.getLogger(__name__)

# Session timeout in seconds (2 hours)
SESSION_TIMEOUT = 2 * 60 * 60


class GameLoopSession:
    """Wrapper holding a GameLoop instance with metadata."""

    __slots__ = (
        "game_loop",
        "game_id",
        "user_id",
        "last_access",
        "language",
        "_is_generating",
        "sse_cache",
        "_sse_event_id",
        # ★ Options cache for fast resume
        "_cached_options",
        "_cached_options_key",
        "_is_prefetching_options",
    )

    # Maximum number of SSE story chunks to cache for reconnection
    MAX_SSE_CACHE_SIZE = 500

    def __init__(
        self,
        game_loop: GameLoop,
        game_id: int,
        user_id: Optional[int] = None,
        language: str = "zh",
    ):
        self.game_loop = game_loop
        self.game_id = game_id
        self.user_id = user_id
        self.last_access = time.time()
        self.language = language
        self._is_generating = False
        # SSE reconnection support: cache story chunks with event IDs
        self.sse_cache: list[str] = []
        self._sse_event_id: int = 0
        # ★ Options cache for fast resume
        self._cached_options: Optional[List[Dict[str, Any]]] = None
        self._cached_options_key: Optional[str] = None  # "week_round" format
        self._is_prefetching_options: bool = False

    def touch(self):
        """Update last access timestamp."""
        self.last_access = time.time()

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.last_access) > SESSION_TIMEOUT

    def try_start_generating(self) -> bool:
        """Try to acquire generating lock. Returns True if successful, False if already generating.

        Note: This is safe in asyncio single-threaded model because Python operations
        between await points are atomic. No threading.Lock needed.
        """
        if self._is_generating:
            return False
        self._is_generating = True
        return True

    def finish_generating(self):
        """Release generating lock."""
        self._is_generating = False

    # ---- SSE cache methods for reconnection support ----

    def cache_sse_chunk(self, chunk: str) -> int:
        """Cache a story chunk and return its event ID."""
        event_id = self._sse_event_id
        self._sse_event_id += 1
        self.sse_cache.append(chunk)
        # Trim cache if too large (keep tail)
        if len(self.sse_cache) > self.MAX_SSE_CACHE_SIZE:
            trim_count = len(self.sse_cache) - self.MAX_SSE_CACHE_SIZE
            self.sse_cache = self.sse_cache[trim_count:]
        return event_id

    def get_cached_chunks_after(self, last_event_id: int) -> list[tuple[int, str]]:
        """Get cached chunks after the given event ID for replay.
        Returns list of (event_id, chunk) tuples.
        """
        # Calculate how many chunks we have
        total_chunks = self._sse_event_id
        cached_count = len(self.sse_cache)
        # First cached event ID
        first_cached_id = total_chunks - cached_count

        result = []
        start_id = last_event_id + 1
        for event_id in range(start_id, total_chunks):
            cache_index = event_id - first_cached_id
            if 0 <= cache_index < cached_count:
                result.append((event_id, self.sse_cache[cache_index]))
        return result

    def clear_sse_cache(self):
        """Clear SSE cache after generation complete."""
        self.sse_cache.clear()
        self._sse_event_id = 0

    # ---- Options cache methods for fast resume ----

    def get_cache_key(self, week: int, round_num: int) -> str:
        """Generate cache key for current week/round."""
        return f"{week}_{round_num}"

    def get_cached_options(
        self, week: int, round_num: int
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached options if available for current week/round."""
        cache_key = self.get_cache_key(week, round_num)
        logger.info(
            f"[Options Cache] Checking: requested={cache_key}, cached={self._cached_options_key}, has_data={self._cached_options is not None}"
        )
        if self._cached_options_key == cache_key and self._cached_options:
            logger.info(f"[Options Cache] Hit for week={week}, round={round_num}")
            return self._cached_options
        return None

    def set_cached_options(
        self, week: int, round_num: int, options: List[Dict[str, Any]]
    ) -> None:
        """Cache options for current week/round."""
        cache_key = self.get_cache_key(week, round_num)
        self._cached_options_key = cache_key
        self._cached_options = options
        logger.info(
            f"[Options Cache] Stored {len(options)} options for week={week}, round={round_num}"
        )

    def clear_options_cache(self) -> None:
        """Clear options cache (call when choice is made or new round starts)."""
        if self._cached_options:
            logger.info(f"[Options Cache] Cleared (was for {self._cached_options_key})")
        self._cached_options = None
        self._cached_options_key = None

    def is_prefetching_options(self) -> bool:
        """Check if options prefetch is in progress."""
        return self._is_prefetching_options

    def start_prefetching_options(self) -> None:
        """Mark options prefetch as started."""
        self._is_prefetching_options = True
        logger.info("[Options Prefetch] Started")

    def finish_prefetching_options(self) -> None:
        """Mark options prefetch as finished."""
        self._is_prefetching_options = False
        logger.info("[Options Prefetch] Finished")


class SessionStore:
    """
    Thread-safe in-memory store mapping session_key → GameLoopSession.

    Session key format: "user_{user_id}_game_{game_id}" or "anon_game_{game_id}"
    """

    def __init__(self):
        self._sessions: Dict[str, GameLoopSession] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    # ---- key helpers ----

    @staticmethod
    def make_key(game_id: int, user_id: Optional[int] = None) -> str:
        if user_id is not None:
            return f"user_{user_id}_game_{game_id}"
        return f"anon_game_{game_id}"

    # ---- public API ----

    def get(
        self, game_id: int, user_id: Optional[int] = None
    ) -> Optional[GameLoopSession]:
        """Get a session if it exists and is not expired."""
        self._maybe_cleanup()
        key = self.make_key(game_id, user_id)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None
            if session.is_expired:
                del self._sessions[key]
                logger.info(f"Session expired: {key}")
                return None
            session.touch()
            return session

    def put(
        self,
        game_id: int,
        game_loop: GameLoop,
        user_id: Optional[int] = None,
        language: str = "zh",
    ) -> GameLoopSession:
        """Create or update a session.

        If session already exists, update the game_loop reference but preserve
        cached data (like options cache) for better performance.
        """
        key = self.make_key(game_id, user_id)

        with self._lock:
            existing_session = self._sessions.get(key)
            if existing_session is not None and not existing_session.is_expired:
                # ★ Preserve cache: Update game_loop reference but keep cached options
                existing_session.game_loop = game_loop
                existing_session.touch()
                logger.info(
                    f"Session updated: {key}, "
                    f"preserved_options_cache={existing_session._cached_options_key is not None}"
                )
                return existing_session

            # Create new session
            session = GameLoopSession(
                game_loop=game_loop,
                game_id=game_id,
                user_id=user_id,
                language=language,
            )
            self._sessions[key] = session
            logger.info(f"Session created: {key}")
            return session

    def remove(self, game_id: int, user_id: Optional[int] = None) -> bool:
        """Remove a session. Returns True if it existed."""
        key = self.make_key(game_id, user_id)
        with self._lock:
            if key in self._sessions:
                del self._sessions[key]
                logger.info(f"Session removed: {key}")
                return True
        return False

    def get_user_sessions(self, user_id: int) -> list:
        """List all active sessions for a user."""
        prefix = f"user_{user_id}_game_"
        with self._lock:
            return [
                s
                for k, s in self._sessions.items()
                if k.startswith(prefix) and not s.is_expired
            ]

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(1 for s in self._sessions.values() if not s.is_expired)

    # ---- internal ----

    def _maybe_cleanup(self):
        """Periodically remove expired sessions."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        with self._lock:
            expired = [k for k, s in self._sessions.items() if s.is_expired]
            for k in expired:
                del self._sessions[k]
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")


# Global singleton
session_store = SessionStore()
