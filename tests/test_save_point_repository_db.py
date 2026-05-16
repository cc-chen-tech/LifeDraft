"""SavePointRepository DB integration tests.

Uses real SQLite in-memory database via monkeypatched SessionLocal.
No unittest.mock usage.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, SessionLocal, User
from src.database.save_point_repository import SavePointRepository
from src.game.state import PlayerState


@pytest.fixture(autouse=True)
def patch_session_local():
    """Replace global SessionLocal with in-memory test database."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    original = SessionLocal
    import src.database.models as models
    import src.database.save_point_repository as repo_module

    models.SessionLocal = TestSessionLocal
    repo_module.SessionLocal = TestSessionLocal
    yield engine
    models.SessionLocal = original
    repo_module.SessionLocal = original


@pytest.fixture
def db(patch_session_local):
    """Create a fresh test session using the shared engine."""
    engine = patch_session_local
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user(db):
    user = User(private_id="SAVE-USER-1", public_id="SAVEU01")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def sample_game(db, sample_user):
    game = Game(user_id=sample_user.user_id, language="zh")
    db.add(game)
    db.commit()
    return game


@pytest.fixture
def sample_player_state():
    return PlayerState(week=5, age=25, current_round=2, player_name="TestPlayer")


class TestSavePointRepositoryDB:
    """DB integration tests for SavePointRepository."""

    def test_create_save_point_success(self, sample_game, sample_user, sample_player_state):
        """create_save_point should persist a save point."""
        repo = SavePointRepository()
        save_id = repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=sample_user.user_id,
            player_state=sample_player_state,
            save_name="Manual Save",
        )

        assert save_id is not None

    def test_create_save_point_wrong_user(self, sample_game, sample_player_state):
        """create_save_point with wrong user_id should return None."""
        repo = SavePointRepository()
        save_id = repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=99999,
            player_state=sample_player_state,
        )

        assert save_id is None

    def test_list_save_points(self, sample_game, sample_user, sample_player_state):
        """list_save_points should return all save points for a game."""
        repo = SavePointRepository()
        repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=sample_user.user_id,
            player_state=sample_player_state,
            save_name="Save 1",
        )

        save_points = repo.list_save_points(sample_game.game_id, sample_user.user_id)
        assert len(save_points) == 1
        assert save_points[0]["save_name"] == "Save 1"

    def test_list_save_points_wrong_user(self, sample_game, sample_user):
        """list_save_points with wrong user should return empty list."""
        repo = SavePointRepository()
        save_points = repo.list_save_points(sample_game.game_id, 99999)
        assert save_points == []

    def test_load_save_point(self, sample_game, sample_user, sample_player_state):
        """load_save_point should return the saved state."""
        repo = SavePointRepository()
        save_id = repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=sample_user.user_id,
            player_state=sample_player_state,
        )

        state = repo.load_save_point(save_id, sample_user.user_id)
        assert state is not None
        assert state.get("player_name") == "TestPlayer"
        assert state.get("_game_id") == sample_game.game_id

    def test_load_save_point_wrong_user(self, sample_game, sample_user, sample_player_state):
        """load_save_point with wrong user should return None."""
        repo = SavePointRepository()
        save_id = repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=sample_user.user_id,
            player_state=sample_player_state,
        )

        state = repo.load_save_point(save_id, 99999)
        assert state is None

    def test_load_save_point_not_found(self, sample_user):
        """load_save_point for non-existent ID should return None."""
        repo = SavePointRepository()
        state = repo.load_save_point(99999, sample_user.user_id)
        assert state is None

    def test_delete_save_point(self, sample_game, sample_user, sample_player_state):
        """delete_save_point should remove the save point."""
        repo = SavePointRepository()
        save_id = repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=sample_user.user_id,
            player_state=sample_player_state,
        )

        result = repo.delete_save_point(save_id, sample_user.user_id)
        assert result is True

        # Verify it's gone
        state = repo.load_save_point(save_id, sample_user.user_id)
        assert state is None

    def test_delete_save_point_wrong_user(self, sample_game, sample_user, sample_player_state):
        """delete_save_point with wrong user should return False."""
        repo = SavePointRepository()
        save_id = repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=sample_user.user_id,
            player_state=sample_player_state,
        )

        result = repo.delete_save_point(save_id, 99999)
        assert result is False

    def test_delete_save_point_not_found(self, sample_user):
        """delete_save_point for non-existent ID should return False."""
        repo = SavePointRepository()
        result = repo.delete_save_point(99999, sample_user.user_id)
        assert result is False

    def test_get_all_states_for_game(self, sample_game, sample_user, sample_player_state):
        """get_all_states_for_game should return all states including snapshots."""
        repo = SavePointRepository()
        repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=sample_user.user_id,
            player_state=sample_player_state,
            save_name="Test Save",
        )

        states = repo.get_all_states_for_game(sample_game.game_id, sample_user.user_id)
        assert len(states) >= 1

    def test_get_all_states_for_game_wrong_user(self, sample_game):
        """get_all_states_for_game with wrong user should return empty list."""
        repo = SavePointRepository()
        states = repo.get_all_states_for_game(sample_game.game_id, 99999)
        assert states == []

    def test_create_save_point_includes_week_and_age(
        self, sample_game, sample_user, sample_player_state
    ):
        """Save point should capture week and age from player state."""
        repo = SavePointRepository()
        repo.create_save_point(
            game_id=sample_game.game_id,
            user_id=sample_user.user_id,
            player_state=sample_player_state,
        )

        save_points = repo.list_save_points(sample_game.game_id, sample_user.user_id)
        assert len(save_points) == 1
        assert save_points[0]["week"] == 5
        assert save_points[0]["age"] == 25
