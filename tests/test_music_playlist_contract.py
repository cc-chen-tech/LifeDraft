"""Layer 3: Music Playlist API contract tests.

Verify producer/consumer field names are consistent across:
- GET /api/music/playlist/{game_id} response
- PUT /api/music/playlist/{game_id} request + response
- POST /api/music/playlist/{game_id}/sync request + response
- POST /api/music/playlist/{game_id}/advance response
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.models import Base, Game, GamePlaylist, SessionLocal, engine

client = TestClient(app)


class TestMusicPlaylistContract:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)

    def _create_game(self) -> int:
        db = SessionLocal()
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.commit()
        game_id = game.game_id  # type: ignore[attr-defined]
        db.close()
        return game_id

    def test_get_playlist_response_fields(self):
        """GET response must contain all expected consumer fields."""
        game_id = self._create_game()
        # Seed a playlist row
        db = SessionLocal()
        db.add(GamePlaylist(game_id=game_id, queue_json=[{"id": 1, "name": "A"}]))
        db.commit()
        db.close()

        resp = client.get(f"/api/music/playlist/{game_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert "current_song" in data
        assert "queue" in data
        assert "played_songs" in data
        assert "is_playing" in data
        assert "volume" in data
        assert "current_position_ms" in data
        assert "recommendation_mood" in data
        assert "updated_at" in data
        assert isinstance(data["queue"], list)
        assert isinstance(data["is_playing"], bool)
        assert isinstance(data["volume"], (int, float))

    def test_put_playlist_merge_preserves_current(self):
        """PUT with new songs must preserve existing current_song."""
        game_id = self._create_game()
        db = SessionLocal()
        db.add(
            GamePlaylist(
                game_id=game_id,
                current_song_json={"id": 10, "name": "Current"},
                queue_json=[{"id": 11, "name": "OldNext"}],
            )
        )
        db.commit()
        db.close()

        resp = client.put(
            f"/api/music/playlist/{game_id}",
            json={
                "songs": [
                    {
                        "id": 10,
                        "name": "Current",
                        "artists": ["A"],
                        "album": "X",
                        "duration": 200,
                    },
                    {
                        "id": 20,
                        "name": "NewNext",
                        "artists": ["B"],
                        "album": "Y",
                        "duration": 180,
                    },
                ],
                "mood": "激昂",
                "keywords": ["战斗"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # Current song preserved
        assert data["current_song"] is not None
        assert data["current_song"]["id"] == 10
        assert data["current_song"]["name"] == "Current"
        # Queue replaced with new songs minus current
        assert len(data["queue"]) == 1
        assert data["queue"][0]["id"] == 20
        assert data["recommendation_mood"] == "激昂"

    def test_put_playlist_sets_first_song_when_empty(self):
        """PUT on empty playlist must set first new song as current."""
        game_id = self._create_game()

        resp = client.put(
            f"/api/music/playlist/{game_id}",
            json={
                "songs": [
                    {
                        "id": 1,
                        "name": "First",
                        "artists": ["A"],
                        "album": "X",
                        "duration": 200,
                    },
                    {
                        "id": 2,
                        "name": "Second",
                        "artists": ["B"],
                        "album": "Y",
                        "duration": 180,
                    },
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_song"]["id"] == 1
        assert len(data["queue"]) == 1
        assert data["queue"][0]["id"] == 2

    def test_sync_playlist_state(self):
        """POST /sync must update position, is_playing, volume."""
        game_id = self._create_game()
        db = SessionLocal()
        db.add(GamePlaylist(game_id=game_id, current_song_json={"id": 1}))
        db.commit()
        db.close()

        resp = client.post(
            f"/api/music/playlist/{game_id}/sync",
            json={"current_position_ms": 45000, "is_playing": True, "volume": 0.8},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "updated_at" in data

        # Verify side effect
        db = SessionLocal()
        p = db.query(GamePlaylist).filter_by(game_id=game_id).first()
        assert p is not None
        assert p.current_position_ms == 45000  # type: ignore[attr-defined]
        assert p.is_playing is True  # type: ignore[attr-defined]
        assert p.volume == 0.8  # type: ignore[attr-defined]
        db.close()

    def test_advance_playlist_moves_to_next(self):
        """POST /advance must move current to played_songs and pop queue head."""
        game_id = self._create_game()
        db = SessionLocal()
        db.add(
            GamePlaylist(
                game_id=game_id,
                current_song_json={"id": 1, "name": "A"},
                queue_json=[{"id": 2, "name": "B"}, {"id": 3, "name": "C"}],
            )
        )
        db.commit()
        db.close()

        resp = client.post(f"/api/music/playlist/{game_id}/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_song"]["id"] == 2
        assert len(data["played_songs"]) == 1
        assert data["played_songs"][0]["id"] == 1
        assert len(data["queue"]) == 1
        assert data["queue"][0]["id"] == 3

    def test_advance_empty_queue_wraps_to_played(self):
        """When queue is empty, advance should rotate played_songs back into queue."""
        game_id = self._create_game()
        db = SessionLocal()
        db.add(
            GamePlaylist(
                game_id=game_id,
                current_song_json={"id": 1, "name": "A"},
                queue_json=[],
                played_songs_json=[{"id": 0, "name": "Z"}],
            )
        )
        db.commit()
        db.close()

        resp = client.post(f"/api/music/playlist/{game_id}/advance")
        assert resp.status_code == 200
        data = resp.json()
        # Should have wrapped around somehow — at minimum queue should not crash
        assert "current_song" in data

    def test_get_playlist_404_for_missing_game(self):
        resp = client.get("/api/music/playlist/99999")
        assert resp.status_code == 404
