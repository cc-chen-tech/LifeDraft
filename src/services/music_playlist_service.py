"""Music playlist service — persistent per-game queue management."""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast

from sqlalchemy.orm import Session

from src.database.models import GamePlaylist

SongDict = Dict[str, Any]

REPORTED_TITLE_FAMILY_CUES = {
    "小幸运",
    "断了的弦",
    "绅士",
    "红尘客栈",
    "非你莫属",
    "给我一首歌的时间",
    "等你下课",
    "不再联系",
    "说散就散",
    "匆匆那年",
    "告白气球",
    "喜欢你",
    "夜曲",
    "一直很安静",
    "平凡之路",
    "岁月神偷",
    "都选C",
    "她说",
    "童话",
    "丑八怪",
    "可爱女人",
}


def _canonical_playlist_title(title: object) -> str:
    text = str(title or "").casefold()
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    text = re.sub(
        r"(心动版|加速版|降速版|抖音版|翻唱版|古风翻唱|翻唱|cover|伴奏|纯音乐版|剪辑版|完整版|live|remix|remaster|0\.\d+x|\d+(?:\.\d+)?x|版)",
        "",
        text,
    )
    return re.sub(r"[\s\-—_·.。…!！?？,，、:：;；'\"“”‘’《》\[\]【】/\\]+", "", text)


def _playlist_title_family_key(song: SongDict) -> str:
    canonical_title = _canonical_playlist_title(song.get("name"))
    for cue in REPORTED_TITLE_FAMILY_CUES:
        canonical_cue = _canonical_playlist_title(cue)
        if canonical_cue and (
            canonical_title == canonical_cue or canonical_cue in canonical_title
        ):
            return canonical_cue
    return canonical_title


@dataclass(frozen=True)
class PlaylistMergeResult:
    """Resolved playlist state after applying the queue policy."""

    current_song: Optional[SongDict]
    queue: List[SongDict]


class PlaylistQueuePolicy:
    """Queue update rules shared by Netease refreshes and generated tracks."""

    @staticmethod
    def _song_key(song: SongDict) -> Any:
        return song.get("id")

    def merge_recommendations(
        self,
        current_song: Optional[SongDict],
        existing_queue: List[SongDict],
        incoming_songs: List[SongDict],
    ) -> PlaylistMergeResult:
        """Merge new recommendations without interrupting current playback."""
        if current_song is None:
            if incoming_songs:
                return PlaylistMergeResult(
                    current_song=incoming_songs[0],
                    queue=self._dedupe(incoming_songs[1:], None),
                )
            return PlaylistMergeResult(current_song=None, queue=list(existing_queue))

        current_id = self._song_key(current_song)
        current_title_key = _playlist_title_family_key(current_song)
        queue: List[SongDict] = []
        seen_ids: set[Any] = set()
        seen_title_keys: set[str] = {current_title_key} if current_title_key else set()
        for song in incoming_songs:
            song_id = self._song_key(song)
            title_key = _playlist_title_family_key(song)
            if song_id == current_id or song_id in seen_ids:
                continue
            if title_key and title_key in seen_title_keys:
                continue
            queue.append(song)
            seen_ids.add(song_id)
            if title_key:
                seen_title_keys.add(title_key)

        return PlaylistMergeResult(current_song=current_song, queue=queue)

    def insert_generated_track(
        self,
        playlist: Dict[str, Any],
        generated_track: SongDict,
    ) -> Dict[str, Any]:
        """Insert generated music as the next upcoming item without interrupting current."""
        queue: List[SongDict] = list(playlist.get("queue") or [])
        current_song = playlist.get("current_song")
        generated_id = self._song_key(generated_track)

        queue = [item for item in queue if self._song_key(item) != generated_id]
        if current_song is not None and self._song_key(current_song) == generated_id:
            updated = dict(playlist)
            updated["current_song"] = current_song
            updated["queue"] = queue
            return updated
        if current_song is None:
            current_song = generated_track
        else:
            queue.insert(0, generated_track)

        updated = dict(playlist)
        updated["current_song"] = current_song
        updated["queue"] = queue
        return updated

    def _dedupe(
        self,
        songs: List[SongDict],
        excluded_id: Any,
    ) -> List[SongDict]:
        deduped: List[SongDict] = []
        seen_ids: set[Any] = set()
        seen_title_keys: set[str] = set()
        for song in songs:
            song_id = self._song_key(song)
            title_key = _playlist_title_family_key(song)
            if song_id == excluded_id or song_id in seen_ids:
                continue
            if title_key and title_key in seen_title_keys:
                continue
            deduped.append(song)
            seen_ids.add(song_id)
            if title_key:
                seen_title_keys.add(title_key)
        return deduped


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
        playlist_data = cast(Any, playlist)
        current: Optional[SongDict] = playlist_data.current_song_json

        policy = PlaylistQueuePolicy()
        merged = policy.merge_recommendations(
            current_song=current,
            existing_queue=list(playlist_data.queue_json or []),
            incoming_songs=songs,
        )
        playlist_data.current_song_json = merged.current_song
        playlist_data.queue_json = merged.queue

        if mood is not None:
            playlist_data.recommendation_mood = mood
        if keywords is not None:
            playlist_data.recommendation_keywords = keywords

        db.commit()
        db.refresh(playlist)
        return cls._to_state(playlist)

    @staticmethod
    def insert_generated_track(
        playlist: Dict[str, Any],
        generated_track: SongDict,
    ) -> Dict[str, Any]:
        """Insert a generated track into future queue without interrupting playback."""
        return PlaylistQueuePolicy().insert_generated_track(playlist, generated_track)

    @classmethod
    def insert_generated_track_for_game(
        cls,
        db: Session,
        game_id: int,
        generated_track: SongDict,
    ) -> PlaylistState:
        """Persist a generated track into a game's future queue."""
        playlist = cls.get_or_create(db, game_id)
        playlist_data = cast(Any, playlist)
        updated = PlaylistQueuePolicy().insert_generated_track(
            {
                "current_song": playlist_data.current_song_json,
                "queue": list(playlist_data.queue_json or []),
            },
            generated_track,
        )
        playlist_data.current_song_json = updated["current_song"]
        playlist_data.queue_json = updated["queue"]
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
        playlist_data = cast(Any, playlist)
        playlist_data.current_position_ms = current_position_ms
        playlist_data.is_playing = is_playing
        playlist_data.volume = volume
        db.commit()
        db.refresh(playlist)
        return {
            "success": True,
            "updated_at": (
                playlist_data.updated_at.isoformat() if playlist_data.updated_at else None
            ),
        }

    @classmethod
    def advance(cls, db: Session, game_id: int) -> PlaylistState:
        """Move current song to played_songs tail, pop queue head as new current."""
        playlist = cls.get_or_create(db, game_id)
        playlist_data = cast(Any, playlist)
        current: Optional[SongDict] = playlist_data.current_song_json
        queue: List[SongDict] = list(playlist_data.queue_json or [])
        played: List[SongDict] = list(playlist_data.played_songs_json or [])

        if current is not None:
            played.append(current)
            # P3-存储修复：played 历史只保留最近 200 首（此前无限增长，随存档膨胀）。
            if len(played) > 200:
                played = played[-200:]

        if queue:
            playlist_data.current_song_json = queue[0]
            playlist_data.queue_json = queue[1:]
            playlist_data.played_songs_json = played
        else:
            # Wrap around: rotate played back to queue, keep the first played as current
            if played:
                playlist_data.current_song_json = played[0]
                playlist_data.queue_json = played[1:]
                playlist_data.played_songs_json = []
            else:
                playlist_data.current_song_json = None
                playlist_data.queue_json = []
                playlist_data.played_songs_json = []

        db.commit()
        db.refresh(playlist)
        return cls._to_state(playlist)

    @classmethod
    def _to_state(cls, playlist: GamePlaylist) -> PlaylistState:
        from datetime import datetime

        playlist_data = cast(Any, playlist)
        return PlaylistState(
            game_id=playlist_data.game_id,
            current_song=playlist_data.current_song_json,
            queue=list(playlist_data.queue_json or []),
            played_songs=list(playlist_data.played_songs_json or []),
            is_playing=bool(playlist_data.is_playing),
            volume=float(playlist_data.volume or 0.5),
            current_position_ms=int(playlist_data.current_position_ms or 0),
            recommendation_mood=playlist_data.recommendation_mood,
            updated_at=(
                playlist_data.updated_at.isoformat()
                if isinstance(playlist_data.updated_at, datetime)
                else str(playlist_data.updated_at) if playlist_data.updated_at else None
            ),
        )


_service_instance: Optional[MusicPlaylistService] = None


def get_music_playlist_service() -> MusicPlaylistService:
    global _service_instance
    if _service_instance is None:
        _service_instance = MusicPlaylistService()
    return _service_instance
