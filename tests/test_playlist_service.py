"""Layer 4: PlaylistService integration tests — real SQLite round-trip."""

import pytest
from sqlalchemy.orm import Session

from src.database.models import Base, Game, GamePlaylist, SessionLocal, engine
from src.services.playlist_service import PlaylistService


class TestPlaylistService:
    """Verify PlaylistService CRUD with a real DB."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Recreate tables for each test."""
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)

    @pytest.fixture
    def db(self) -> Session:
        """Provide a fresh DB session."""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def game(self, db: Session) -> Game:
        """Create a test game."""
        g = Game(language="zh", initial_state={})
        db.add(g)
        db.commit()
        db.refresh(g)
        return g

    def test_get_or_create_playlist_creates_new(self, db: Session, game: Game):
        """get_or_create_playlist must create a new playlist when none exists."""
        playlist = PlaylistService.get_or_create_playlist(db, game.game_id)

        assert playlist.playlist_id is not None
        assert playlist.game_id == game.game_id
        assert playlist.queue_json == []
        assert playlist.played_songs_json == []
        assert playlist.is_playing is False
        assert playlist.volume == 0.5
        assert playlist.current_position_ms == 0

    def test_get_or_create_playlist_returns_existing(self, db: Session, game: Game):
        """get_or_create_playlist must return existing playlist, not create duplicate."""
        p1 = PlaylistService.get_or_create_playlist(db, game.game_id)
        p1.volume = 0.8
        db.commit()

        p2 = PlaylistService.get_or_create_playlist(db, game.game_id)

        assert p1.playlist_id == p2.playlist_id
        assert p2.volume == 0.8

    def test_update_playback_state(self, db: Session, game: Game):
        """update_playback_state must persist all playback fields."""
        song = {"id": 1, "name": "Test Song"}
        playlist = PlaylistService.update_playback_state(
            db,
            game.game_id,
            current_song=song,
            is_playing=True,
            volume=0.7,
            current_position_ms=12000,
        )

        assert playlist.current_song_json == song
        assert playlist.is_playing is True
        assert playlist.volume == 0.7
        assert playlist.current_position_ms == 12000

    def test_set_queue(self, db: Session, game: Game):
        """set_queue must replace the entire queue."""
        queue = [
            {"id": 1, "name": "Song 1"},
            {"id": 2, "name": "Song 2"},
        ]
        playlist = PlaylistService.set_queue(db, game.game_id, queue)

        assert playlist.queue_json == queue

    def test_add_to_queue_appends(self, db: Session, game: Game):
        """add_to_queue must append song to the end by default."""
        PlaylistService.set_queue(db, game.game_id, [{"id": 1, "name": "First"}])
        playlist = PlaylistService.add_to_queue(db, game.game_id, {"id": 2, "name": "Second"})

        assert len(playlist.queue_json) == 2
        assert playlist.queue_json[1]["name"] == "Second"

    def test_add_to_queue_inserts_at_position(self, db: Session, game: Game):
        """add_to_queue must insert at specified position."""
        PlaylistService.set_queue(
            db, game.game_id, [{"id": 1, "name": "First"}, {"id": 3, "name": "Third"}]
        )
        playlist = PlaylistService.add_to_queue(
            db, game.game_id, {"id": 2, "name": "Second"}, position=1
        )

        assert [s["id"] for s in playlist.queue_json] == [1, 2, 3]

    def test_remove_from_queue(self, db: Session, game: Game):
        """remove_from_queue must remove song at specified position."""
        PlaylistService.set_queue(
            db,
            game.game_id,
            [
                {"id": 1, "name": "First"},
                {"id": 2, "name": "Second"},
                {"id": 3, "name": "Third"},
            ],
        )
        playlist = PlaylistService.remove_from_queue(db, game.game_id, position=1)

        assert len(playlist.queue_json) == 2
        assert [s["id"] for s in playlist.queue_json] == [1, 3]

    def test_remove_from_queue_invalid_position(self, db: Session, game: Game):
        """remove_from_queue must be a no-op for invalid position."""
        PlaylistService.set_queue(db, game.game_id, [{"id": 1, "name": "Only"}])
        playlist = PlaylistService.remove_from_queue(db, game.game_id, position=10)

        assert len(playlist.queue_json) == 1

    def test_record_played_song(self, db: Session, game: Game):
        """record_played_song must append to played history."""
        song1 = {"id": 1, "name": "Song 1"}
        song2 = {"id": 2, "name": "Song 2"}

        PlaylistService.record_played_song(db, game.game_id, song1)
        playlist = PlaylistService.record_played_song(db, game.game_id, song2)

        assert len(playlist.played_songs_json) == 2
        assert playlist.played_songs_json[0] == song1
        assert playlist.played_songs_json[1] == song2

    def test_update_recommendation_metadata(self, db: Session, game: Game):
        """update_recommendation_metadata must persist mood and keywords."""
        playlist = PlaylistService.update_recommendation_metadata(
            db, game.game_id, mood="melancholic", keywords=["piano", "rain", "night"]
        )

        assert playlist.recommendation_mood == "melancholic"
        assert playlist.recommendation_keywords == ["piano", "rain", "night"]

    def test_delete_playlist(self, db: Session, game: Game):
        """delete_playlist must remove the playlist and return True."""
        PlaylistService.get_or_create_playlist(db, game.game_id)

        result = PlaylistService.delete_playlist(db, game.game_id)
        assert result is True

        remaining = db.query(GamePlaylist).filter_by(game_id=game.game_id).first()
        assert remaining is None

    def test_delete_playlist_not_found(self, db: Session, game: Game):
        """delete_playlist must return False when playlist does not exist."""
        result = PlaylistService.delete_playlist(db, game.game_id)
        assert result is False

    def test_skip_to_next(self, db: Session, game: Game):
        """skip_to_next must move current to played and set next from queue."""
        current = {"id": 1, "name": "Current"}
        next_song = {"id": 2, "name": "Next"}

        PlaylistService.update_playback_state(
            db, game.game_id, current_song=current, is_playing=True
        )
        PlaylistService.set_queue(db, game.game_id, [next_song])

        playlist = PlaylistService.skip_to_next(db, game.game_id)

        assert playlist is not None
        assert playlist.current_song_json == next_song
        assert playlist.played_songs_json == [current]
        assert playlist.queue_json == []
        assert playlist.is_playing is True
        assert playlist.current_position_ms == 0

    def test_skip_to_next_empty_queue(self, db: Session, game: Game):
        """skip_to_next must return playlist unchanged when queue is empty."""
        current = {"id": 1, "name": "Current"}
        PlaylistService.update_playback_state(
            db, game.game_id, current_song=current, is_playing=True
        )

        playlist = PlaylistService.skip_to_next(db, game.game_id)

        assert playlist is not None
        assert playlist.current_song_json == current
        assert playlist.queue_json == []

    def test_skip_to_next_no_playlist(self, db: Session, game: Game):
        """skip_to_next must return None when no playlist exists."""
        playlist = PlaylistService.skip_to_next(db, game.game_id)
        assert playlist is None

    def test_clear_queue(self, db: Session, game: Game):
        """clear_queue must empty the queue without affecting other fields."""
        current = {"id": 1, "name": "Current"}
        PlaylistService.update_playback_state(
            db, game.game_id, current_song=current, volume=0.8
        )
        PlaylistService.set_queue(
            db, game.game_id, [{"id": 2, "name": "Queued"}]
        )

        playlist = PlaylistService.clear_queue(db, game.game_id)

        assert playlist.queue_json == []
        assert playlist.current_song_json == current
        assert playlist.volume == 0.8

    def test_cascade_delete_game_removes_playlist(self, db: Session, game: Game):
        """Deleting a Game must cascade-delete its playlist via ORM relationship."""
        PlaylistService.get_or_create_playlist(db, game.game_id)

        db.delete(game)
        db.commit()

        remaining = db.query(GamePlaylist).filter_by(game_id=game.game_id).first()
        assert remaining is None
