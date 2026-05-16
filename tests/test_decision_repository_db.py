"""DecisionRepository DB integration tests.

Uses real SQLite in-memory database via monkeypatched SessionLocal.
No unittest.mock usage.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.decision_repository import DecisionRepository
from src.database.models import Base, Game, SessionLocal, User


@pytest.fixture(autouse=True)
def patch_session_local():
    """Replace global SessionLocal with in-memory test database."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    original = SessionLocal
    import src.database.decision_repository as repo_module
    import src.database.models as models

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
    user = User(private_id="DEC-USER-1", public_id="DECU01")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def sample_game(db, sample_user):
    game = Game(user_id=sample_user.user_id, language="zh")
    db.add(game)
    db.commit()
    return game


class TestDecisionRepositoryDB:
    """DB integration tests for DecisionRepository."""

    def test_save_decision(self, sample_game):
        """save_decision should persist a decision record."""
        repo = DecisionRepository()
        repo.save_decision(
            game_id=sample_game.game_id,
            week=1,
            event_description="Test event",
            choice_text="Test choice",
            effects={"energy": 10},
        )

        decisions = repo.get_decision_history(sample_game.game_id)
        assert len(decisions) == 1
        assert decisions[0].choice_text == "Test choice"

    def test_save_multiple_decisions(self, sample_game):
        """Multiple decisions should be persisted in order."""
        repo = DecisionRepository()
        for i in range(3):
            repo.save_decision(
                game_id=sample_game.game_id,
                week=i,
                event_description=f"Event {i}",
                choice_text=f"Choice {i}",
                effects={},
            )

        decisions = repo.get_decision_history(sample_game.game_id)
        assert len(decisions) == 3
        assert decisions[0].week == 0
        assert decisions[1].week == 1
        assert decisions[2].week == 2

    def test_get_decision_history_empty(self, sample_game):
        """get_decision_history for game with no decisions should return empty list."""
        repo = DecisionRepository()
        decisions = repo.get_decision_history(sample_game.game_id)
        assert decisions == []

    def test_get_story_history(self, sample_game):
        """get_story_history should return formatted story entries."""
        repo = DecisionRepository()
        repo.save_decision(
            game_id=sample_game.game_id,
            week=1,
            event_description="Story text",
            choice_text="My choice",
            effects={},
        )

        stories = repo.get_story_history(sample_game.game_id)
        assert len(stories) == 1
        assert stories[0]["story_text"] == "Story text"
        assert stories[0]["choice_text"] == "My choice"
        assert stories[0]["week"] == 1

    def test_get_story_history_limit(self, sample_game):
        """get_story_history limit should restrict results."""
        repo = DecisionRepository()
        for i in range(5):
            repo.save_decision(
                game_id=sample_game.game_id,
                week=i,
                event_description=f"Event {i}",
                choice_text=f"Choice {i}",
                effects={},
            )

        stories = repo.get_story_history(sample_game.game_id, limit=2)
        assert len(stories) == 2

    def test_search_story_history_found(self, sample_game):
        """search_story_history should find matching keywords."""
        repo = DecisionRepository()
        repo.save_decision(
            game_id=sample_game.game_id,
            week=1,
            event_description="The dragon attacked the village",
            choice_text="Fight",
            effects={},
        )

        results = repo.search_story_history(sample_game.game_id, keywords=["dragon"])
        assert len(results) == 1
        assert results[0]["matched_keyword"] == "dragon"

    def test_search_story_history_not_found(self, sample_game):
        """search_story_history should return empty for non-matching keywords."""
        repo = DecisionRepository()
        repo.save_decision(
            game_id=sample_game.game_id,
            week=1,
            event_description="The dragon attacked",
            choice_text="Fight",
            effects={},
        )

        results = repo.search_story_history(sample_game.game_id, keywords=["unicorn"])
        assert results == []

    def test_search_story_history_multiple_keywords(self, sample_game):
        """search_story_history should match any keyword."""
        repo = DecisionRepository()
        repo.save_decision(
            game_id=sample_game.game_id,
            week=1,
            event_description="The dragon attacked",
            choice_text="Fight",
            effects={},
        )

        results = repo.search_story_history(
            sample_game.game_id, keywords=["unicorn", "dragon"]
        )
        assert len(results) == 1

    def test_search_story_history_max_results(self, sample_game):
        """search_story_history max_results should limit output."""
        repo = DecisionRepository()
        for i in range(5):
            repo.save_decision(
                game_id=sample_game.game_id,
                week=i,
                event_description=f"Event with dragon {i}",
                choice_text="Fight",
                effects={},
            )

        results = repo.search_story_history(
            sample_game.game_id, keywords=["dragon"], max_results=2
        )
        assert len(results) == 2

    def test_search_story_history_case_insensitive(self, sample_game):
        """search_story_history should be case-insensitive."""
        repo = DecisionRepository()
        repo.save_decision(
            game_id=sample_game.game_id,
            week=1,
            event_description="The DRAGON attacked",
            choice_text="Fight",
            effects={},
        )

        results = repo.search_story_history(sample_game.game_id, keywords=["dragon"])
        assert len(results) == 1
