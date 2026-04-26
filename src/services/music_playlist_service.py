"""Music playlist service — persistent per-game queue management."""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.database.models import GamePlaylist

SongDict = Dict[str, Any]


class PlaylistState:
    """DTO returned to consumers (routers / frontend)."""

    def __init__(
        self,
        game_id: int,
        current_song: Optional[SongDict],
        queue: List[SongDict],
        played_songs: List[SongDict],
        is_playing: bool,
        volume: float,
        current_position_ms: int,
        recommendation_mood: Optional[str],
        updated_at: Optional[str],
    ):
        self.game_id = game_id
        self.current_song = current_song
        self.queue = queue
        self.played_songs = played_songs
        self.is_playing = is_playing
        self.volume = volume
        self.current_position_ms = current_position_ms
        self.recommendation_mood = recommendation_mood
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current_song": self.current_song,
            "queue": self.queue,
            "played_songs": self.played_songs,
            "is_playing": self.is_playing,
            "volume": self.volume,
            "current_position_ms": self.current_position_ms,
            "recommendation_mood": self.recommendation_mood,
            "updated_at": self.updated_at,
        }


class MusicPlaylistService:
    """Handles playlist CRUD and queue-merge logic.

    Merge rule: when new songs arrive, preserve the currently playing song.
    Only the upcoming queue is replaced."""

    @staticmethod
    def get_or_create(db: Session, game_id: int) -> GamePlaylist:
        playlist = db.query(GamePlaylist).filter_by(game_id=game_id).first()
        if playlist is None:
            playlist = GamePlaylist(game_id=game_id)
            db.add(playlist)
            db.commit()
            db.refresh(playlist)
        return playlist

    @classmethod
    def get_state(cls, db: Session, game_id: int) -> PlaylistState:
        playlist = cls.get_or_create(db, game_id)
        return cls._to_state(playlist)

    @classmethod
    def merge_songs(
        cls,
        db: Session,
        game_id: int,
        songs: List[SongDict],
        mood: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> PlaylistState:
        """Merge new recommendation songs into the playlist.

        - If no current song exists, the first new song becomes current.
        - If a current song exists, it is preserved.
        - Any new songs with the same ID as current are removed from the queue.
        - The remaining new songs replace the existing queue entirely.
        """
        playlist = cls.get_or_create(db, game_id)
        current: Optional[SongDict] = playlist.current_song_json  # type: ignore

        if current is None:
            # No current song — start from the beginning of the new list
            if songs:
                playlist.current_song_json = songs[0]  # type: ignore
                playlist.queue_json = songs[1:]  # type: ignore
            else:
                playlist.queue_json = []  # type: ignore
        else:
            current_id = current.get("id")
            # Filter out the current song from the new list
            new_queue = [s for s in songs if s.get("id") != current_id]
            playlist.queue_json = new_queue  # type: ignore

        if mood is not None:
            playlist.recommendation_mood = mood  # type: ignore
        if keywords is not None:
            playlist.recommendation_keywords = keywords  # type: ignore

        db.commit()
        db.refresh(playlist)
        return cls._to_state(playlist)

    @classmethod
    def sync_state(
        cls,
        db: Session,
        game_id: int,
        current_position_ms: int,
        is_playing: bool,
        volume: float,
    ) -> Dict[str, Any]:
        playlist = cls.get_or_create(db, game_id)
        playlist.current_position_ms = current_position_ms  # type: ignore
        playlist.is_playing = is_playing  # type: ignore
        playlist.volume = volume  # type: ignore
        db.commit()
        db.refresh(playlist)
        return {
            "success": True,
            "updated_at": playlist.updated_at.isoformat() if playlist.updated_at else None,  # type: ignore
        }

    @classmethod
    def advance(cls, db: Session, game_id: int) -> PlaylistState:
        """Move current song to played_songs tail, pop queue head as new current."""
        playlist = cls.get_or_create(db, game_id)
        current: Optional[SongDict] = playlist.current_song_json  # type: ignore
        queue: List[SongDict] = list(playlist.queue_json or [])  # type: ignore
        played: List[SongDict] = list(playlist.played_songs_json or [])  # type: ignore

        if current is not None:
            played.append(current)

        if queue:
            playlist.current_song_json = queue[0]  # type: ignore
            playlist.queue_json = queue[1:]  # type: ignore
            playlist.played_songs_json = played  # type: ignore
        else:
            # Wrap around: rotate played back to queue, keep the first played as current
            if played:
                playlist.current_song_json = played[0]  # type: ignore
                playlist.queue_json = played[1:]  # type: ignore
                playlist.played_songs_json = []  # type: ignore
            else:
                playlist.current_song_json = None  # type: ignore
                playlist.queue_json = []  # type: ignore
                playlist.played_songs_json = []  # type: ignore

        db.commit()
        db.refresh(playlist)
        return cls._to_state(playlist)

    @classmethod
    def _to_state(cls, playlist: GamePlaylist) -> PlaylistState:
        from datetime import datetime

        return PlaylistState(
            game_id=playlist.game_id,  # type: ignore
            current_song=playlist.current_song_json,  # type: ignore
            queue=list(playlist.queue_json or []),  # type: ignore
            played_songs=list(playlist.played_songs_json or []),  # type: ignore
            is_playing=bool(playlist.is_playing),  # type: ignore
            volume=float(playlist.volume or 0.5),  # type: ignore
            current_position_ms=int(playlist.current_position_ms or 0),  # type: ignore
            recommendation_mood=playlist.recommendation_mood,  # type: ignore
            updated_at=(
                playlist.updated_at.isoformat()  # type: ignore
                if isinstance(playlist.updated_at, datetime)
                else str(playlist.updated_at) if playlist.updated_at else None  # type: ignore
            ),
        )


_service_instance: Optional[MusicPlaylistService] = None


def get_music_playlist_service() -> MusicPlaylistService:
    global _service_instance
    if _service_instance is None:
        _service_instance = MusicPlaylistService()
    return _service_instance
