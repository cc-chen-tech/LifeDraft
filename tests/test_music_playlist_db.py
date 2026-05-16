"""Layer 4: GamePlaylist DB integration tests — real SQLite save→read round-trip."""

import pytest

from src.database.models import Base, Game, GamePlaylist, SessionLocal, engine


class TestGamePlaylistDB:
    """Verify GamePlaylist CRUD and Game relationship with a real DB."""

    @pytest.fixture(autouse=True)
    def setup_db(self):
        """Recreate tables for each test."""
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)

    def test_create_playlist_linked_to_game(self):
        """Saving a GamePlaylist linked to a Game must round-trip."""
        db = SessionLocal()
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.commit()
        db.refresh(game)

        playlist = GamePlaylist(
            game_id=game.game_id,
            current_song_json={"id": 1, "name": "Test Song"},
            queue_json=[{"id": 2, "name": "Next"}],
            is_playing=True,
            volume=0.7,
            current_position_ms=12000,
        )
        db.add(playlist)
        db.commit()
        db.refresh(playlist)

        assert playlist.playlist_id is not None
        assert playlist.game_id == game.game_id
        assert playlist.current_song_json["name"] == "Test Song"
        assert len(playlist.queue_json) == 1
        assert playlist.is_playing is True
        db.close()

    def test_playlist_game_relationship(self):
        """Game.playlist must return the linked GamePlaylist."""
        db = SessionLocal()
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.commit()
        db.refresh(game)

        playlist = GamePlaylist(
            game_id=game.game_id,
            queue_json=[{"id": 3}],
        )
        db.add(playlist)
        db.commit()

        # Use a fresh session to verify relationship works
        db2 = SessionLocal()
        fetched = db2.query(Game).filter_by(game_id=game.game_id).first()
        assert fetched is not None
        assert fetched.playlist is not None
        assert fetched.playlist.queue_json[0]["id"] == 3
        db2.close()
        db.close()

    def test_cascade_delete_game_removes_playlist(self):
        """Deleting a Game must cascade-delete its GamePlaylist."""
        db = SessionLocal()
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.commit()
        db.refresh(game)

        playlist = GamePlaylist(game_id=game.game_id, queue_json=[])
        db.add(playlist)
        db.commit()

        db.delete(game)
        db.commit()

        remaining = db.query(GamePlaylist).filter_by(game_id=game.game_id).first()
        assert remaining is None
        db.close()

    def test_game_id_unique_constraint(self):
        """Two playlists for the same game_id must be rejected."""
        db = SessionLocal()
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.commit()
        db.refresh(game)

        p1 = GamePlaylist(game_id=game.game_id, queue_json=[])
        db.add(p1)
        db.commit()

        from sqlalchemy.exc import IntegrityError

        p2 = GamePlaylist(game_id=game.game_id, queue_json=[])
        db.add(p2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.close()
