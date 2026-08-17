"""SessionRepository DB integration tests.

Uses real SQLite in-memory database via monkeypatched SessionLocal.
No unittest.mock usage.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, SessionLocal, User
from src.database.session_repository import SessionRepository

pytestmark = [pytest.mark.integration]



@pytest.fixture(autouse=True)
def patch_session_local():
    """Replace global SessionLocal with in-memory test database."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    original = SessionLocal
    import src.database.models as models
    import src.database.session_repository as repo_module

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
    """Create a test user."""
    user = User(private_id="TEST-USER-1", public_id="TESTU01")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def sample_game(db, sample_user):
    """Create a test game."""
    game = Game(user_id=sample_user.user_id, language="zh")
    db.add(game)
    db.commit()
    return game


class TestSessionRepositoryDB:
    """DB integration tests for SessionRepository."""

    def test_set_active_game_success(self, sample_user, sample_game):
        """set_active_game should update user's last_active_game_id."""
        repo = SessionRepository()
        result = repo.set_active_game(sample_user.user_id, sample_game.game_id)

        assert result is True

    def test_set_active_game_user_not_found(self, sample_game):
        """set_active_game for non-existent user should return False."""
        repo = SessionRepository()
        result = repo.set_active_game(99999, sample_game.game_id)

        assert result is False

    def test_get_active_game_success(self, sample_user, sample_game):
        """get_active_game should return the active game ID."""
        repo = SessionRepository()
        repo.set_active_game(sample_user.user_id, sample_game.game_id)

        active_id = repo.get_active_game(sample_user.user_id)
        assert active_id == sample_game.game_id

    def test_get_active_game_no_active_game(self, sample_user):
        """get_active_game when no game is set should return None."""
        repo = SessionRepository()
        active_id = repo.get_active_game(sample_user.user_id)
        assert active_id is None

    def test_get_active_game_user_not_found(self):
        """get_active_game for non-existent user should return None."""
        repo = SessionRepository()
        active_id = repo.get_active_game(99999)
        assert active_id is None

    def test_get_active_game_deleted_game(self, sample_user, sample_game, db):
        """get_active_game should clear reference if game was deleted."""
        repo = SessionRepository()
        repo.set_active_game(sample_user.user_id, sample_game.game_id)

        # Delete the game directly via db
        db.delete(sample_game)
        db.commit()

        active_id = repo.get_active_game(sample_user.user_id)
        assert active_id is None

    def test_clear_active_game_success(self, sample_user, sample_game):
        """clear_active_game should remove active game reference."""
        repo = SessionRepository()
        repo.set_active_game(sample_user.user_id, sample_game.game_id)

        result = repo.clear_active_game(sample_user.user_id)
        assert result is True

        active_id = repo.get_active_game(sample_user.user_id)
        assert active_id is None

    def test_clear_active_game_user_not_found(self):
        """clear_active_game for non-existent user should return False."""
        repo = SessionRepository()
        result = repo.clear_active_game(99999)
        assert result is False

    def test_roundtrip_set_get_clear(self, sample_user, sample_game):
        """Full roundtrip: set -> get -> clear -> get."""
        repo = SessionRepository()

        # Set
        assert repo.set_active_game(sample_user.user_id, sample_game.game_id) is True

        # Get
        assert repo.get_active_game(sample_user.user_id) == sample_game.game_id

        # Clear
        assert repo.clear_active_game(sample_user.user_id) is True

        # Get again
        assert repo.get_active_game(sample_user.user_id) is None

    def test_set_active_game_overwrites_previous(self, sample_user, sample_game, db):
        """Setting a new active game should overwrite the previous one."""
        game2 = Game(user_id=sample_user.user_id, language="en")
        db.add(game2)
        db.commit()

        repo = SessionRepository()
        repo.set_active_game(sample_user.user_id, sample_game.game_id)
        repo.set_active_game(sample_user.user_id, game2.game_id)

        assert repo.get_active_game(sample_user.user_id) == game2.game_id
