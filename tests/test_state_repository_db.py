"""StateRepository DB integration tests.

Uses real SQLite in-memory database via monkeypatched SessionLocal.
No unittest.mock usage.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, SessionLocal, User
from src.database.state_repository import StateRepository
from src.game.state import PlayerState


@pytest.fixture(autouse=True)
def patch_session_local():
    """Replace global SessionLocal with in-memory test database."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    original = SessionLocal
    import src.database.models as models
    import src.database.state_repository as repo_module

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
    user = User(private_id="STATE-USER-1", public_id="STATEU01")
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


class TestStateRepositoryDB:
    """DB integration tests for StateRepository."""

    def test_save_state(self, sample_game, sample_player_state):
        """save_state should persist a state snapshot."""
        repo = StateRepository()
        repo.save_state(sample_game.game_id, sample_player_state)

        states = repo.load_game_state(sample_game.game_id)
        assert states is not None
        assert states.get("player_name") == "TestPlayer"

    def test_load_game_state_returns_latest(self, sample_game, sample_player_state):
        """load_game_state should return the latest state."""
        repo = StateRepository()

        state1 = PlayerState(week=1, age=22, player_name="Old")
        state2 = PlayerState(week=5, age=25, player_name="New")
        repo.save_state(sample_game.game_id, state1)
        repo.save_state(sample_game.game_id, state2)

        latest = repo.load_game_state(sample_game.game_id)
        assert latest.get("player_name") == "New"

    def test_load_game_state_not_found(self):
        """load_game_state for non-existent game should return None."""
        repo = StateRepository()
        result = repo.load_game_state(99999)
        assert result is None

    def test_save_game_progress(self, sample_game, sample_player_state):
        """save_game_progress should save and return True."""
        repo = StateRepository()
        result = repo.save_game_progress(sample_game.game_id, sample_player_state)
        assert result is True

    def test_save_game_progress_none_state(self, sample_game):
        """save_game_progress with None should return False."""
        repo = StateRepository()
        result = repo.save_game_progress(sample_game.game_id, None)
        assert result is False

    def test_load_saved_game(self, sample_game, sample_user, sample_player_state):
        """load_saved_game should return state with game_id."""
        repo = StateRepository()
        repo.save_state(sample_game.game_id, sample_player_state)

        state = repo.load_saved_game(sample_game.game_id, sample_user.user_id)
        assert state is not None
        assert state.get("_game_id") == sample_game.game_id

    def test_load_saved_game_wrong_user(self, sample_game):
        """load_saved_game with wrong user should return None."""
        repo = StateRepository()
        state = repo.load_saved_game(sample_game.game_id, 99999)
        assert state is None

    def test_load_saved_game_injects_constraint_level(self, sample_game, sample_user):
        """load_saved_game should inject constraint_level."""
        repo = StateRepository()
        state = PlayerState(week=1, age=22)
        repo.save_state(sample_game.game_id, state)

        loaded = repo.load_saved_game(sample_game.game_id, sample_user.user_id)
        assert "constraint_level" in loaded
