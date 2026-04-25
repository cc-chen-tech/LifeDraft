"""Playlist service for per-game persistent music playlist management.

Provides CRUD operations for GamePlaylist, including playback state,
queue management, and song history tracking.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.database.models import GamePlaylist

logger = logging.getLogger(__name__)


class PlaylistService:
    """Service for managing per-game music playlists."""

    @staticmethod
    def get_playlist(db: Session, game_id: int) -> Optional[GamePlaylist]:
        """Get the playlist for a specific game.

        Args:
            db: Database session
            game_id: Game ID

        Returns:
            GamePlaylist or None if not found
        """
        return db.query(GamePlaylist).filter(GamePlaylist.game_id == game_id).first()

    @staticmethod
    def get_or_create_playlist(db: Session, game_id: int) -> GamePlaylist:
        """Get existing playlist or create a new one for the game.

        Args:
            db: Database session
            game_id: Game ID

        Returns:
            GamePlaylist instance (existing or newly created)
        """
        playlist = PlaylistService.get_playlist(db, game_id)
        if playlist is None:
            playlist = GamePlaylist(game_id=game_id)
            db.add(playlist)
            db.commit()
            db.refresh(playlist)
            logger.info(f"[PlaylistService] Created new playlist for game_id={game_id}")
        return playlist

    @staticmethod
    def update_playback_state(
        db: Session,
        game_id: int,
        current_song: Optional[Dict[str, Any]] = None,
        is_playing: Optional[bool] = None,
        volume: Optional[float] = None,
        current_position_ms: Optional[int] = None,
    ) -> GamePlaylist:
        """Update playback state fields.

        Args:
            db: Database session
            game_id: Game ID
            current_song: Current song JSON data
            is_playing: Whether music is playing
            volume: Volume level (0.0 - 1.0)
            current_position_ms: Current playback position in milliseconds

        Returns:
            Updated GamePlaylist
        """
        playlist = PlaylistService.get_or_create_playlist(db, game_id)

        if current_song is not None:
            playlist.current_song_json = current_song
        if is_playing is not None:
            playlist.is_playing = is_playing
        if volume is not None:
            playlist.volume = volume
        if current_position_ms is not None:
            playlist.current_position_ms = current_position_ms

        db.commit()
        db.refresh(playlist)
        return playlist

    @staticmethod
    def set_queue(db: Session, game_id: int, queue: List[Dict[str, Any]]) -> GamePlaylist:
        """Replace the entire song queue.

        Args:
            db: Database session
            game_id: Game ID
            queue: List of song JSON objects

        Returns:
            Updated GamePlaylist
        """
        playlist = PlaylistService.get_or_create_playlist(db, game_id)
        playlist.queue_json = queue
        db.commit()
        db.refresh(playlist)
        return playlist

    @staticmethod
    def add_to_queue(
        db: Session, game_id: int, song: Dict[str, Any], position: Optional[int] = None
    ) -> GamePlaylist:
        """Add a song to the queue.

        Args:
            db: Database session
            game_id: Game ID
            song: Song JSON data
            position: Insert position (None = append to end)

        Returns:
            Updated GamePlaylist
        """
        playlist = PlaylistService.get_or_create_playlist(db, game_id)
        queue: List[Dict[str, Any]] = list(playlist.queue_json or [])

        if position is None or position >= len(queue):
            queue.append(song)
        else:
            queue.insert(max(0, position), song)

        playlist.queue_json = queue
        db.commit()
        db.refresh(playlist)
        return playlist

    @staticmethod
    def remove_from_queue(db: Session, game_id: int, position: int) -> GamePlaylist:
        """Remove a song from the queue by position.

        Args:
            db: Database session
            game_id: Game ID
            position: Queue position to remove

        Returns:
            Updated GamePlaylist
        """
        playlist = PlaylistService.get_or_create_playlist(db, game_id)
        queue: List[Dict[str, Any]] = list(playlist.queue_json or [])

        if 0 <= position < len(queue):
            queue.pop(position)
            playlist.queue_json = queue
            db.commit()
            db.refresh(playlist)

        return playlist

    @staticmethod
    def record_played_song(db: Session, game_id: int, song: Dict[str, Any]) -> GamePlaylist:
        """Record a song as played (adds to played history).

        Args:
            db: Database session
            game_id: Game ID
            song: Song JSON data

        Returns:
            Updated GamePlaylist
        """
        playlist = PlaylistService.get_or_create_playlist(db, game_id)
        played: List[Dict[str, Any]] = list(playlist.played_songs_json or [])
        played.append(song)
        playlist.played_songs_json = played
        db.commit()
        db.refresh(playlist)
        return playlist

    @staticmethod
    def update_recommendation_metadata(
        db: Session,
        game_id: int,
        mood: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> GamePlaylist:
        """Update recommendation metadata.

        Args:
            db: Database session
            game_id: Game ID
            mood: Recommendation mood
            keywords: Recommendation keywords

        Returns:
            Updated GamePlaylist
        """
        playlist = PlaylistService.get_or_create_playlist(db, game_id)

        if mood is not None:
            playlist.recommendation_mood = mood
        if keywords is not None:
            playlist.recommendation_keywords = keywords

        db.commit()
        db.refresh(playlist)
        return playlist

    @staticmethod
    def delete_playlist(db: Session, game_id: int) -> bool:
        """Delete a playlist for a game.

        Args:
            db: Database session
            game_id: Game ID

        Returns:
            True if deleted, False if not found
        """
        playlist = PlaylistService.get_playlist(db, game_id)
        if playlist:
            db.delete(playlist)
            db.commit()
            logger.info(f"[PlaylistService] Deleted playlist for game_id={game_id}")
            return True
        return False

    @staticmethod
    def skip_to_next(db: Session, game_id: int) -> Optional[GamePlaylist]:
        """Skip to the next song in the queue.

        Moves current song to played history, sets next song as current.

        Args:
            db: Database session
            game_id: Game ID

        Returns:
            Updated GamePlaylist or None if no next song
        """
        playlist = PlaylistService.get_playlist(db, game_id)
        if not playlist:
            return None

        queue: List[Dict[str, Any]] = list(playlist.queue_json or [])
        if not queue:
            return playlist

        # Record current as played if exists
        if playlist.current_song_json:
            played: List[Dict[str, Any]] = list(playlist.played_songs_json or [])
            played.append(playlist.current_song_json)
            playlist.played_songs_json = played

        # Set next as current
        next_song = queue.pop(0)
        playlist.current_song_json = next_song
        playlist.queue_json = queue
        playlist.is_playing = True
        playlist.current_position_ms = 0

        db.commit()
        db.refresh(playlist)
        return playlist

    @staticmethod
    def clear_queue(db: Session, game_id: int) -> GamePlaylist:
        """Clear the song queue.

        Args:
            db: Database session
            game_id: Game ID

        Returns:
            Updated GamePlaylist
        """
        playlist = PlaylistService.get_or_create_playlist(db, game_id)
        playlist.queue_json = []
        db.commit()
        db.refresh(playlist)
        return playlist
