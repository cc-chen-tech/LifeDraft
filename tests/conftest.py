"""
Shared pytest fixtures for all tests.

This file is automatically loaded by pytest and provides common fixtures
that can be used across all test files.

Usage:
    def test_something(client, auth_headers):
        response = client.get("/api/endpoint", headers=auth_headers)
        assert response.status_code == 200
"""
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.database.models import Base, User, Game, GameState
from src.game.state import PlayerState


# ==================== FastAPI Client Fixtures ====================

@pytest.fixture
def client():
    """Create a FastAPI test client.
    
    Use this for API endpoint tests.
    """
    return TestClient(app)


# ==================== Authentication Fixtures ====================

@pytest.fixture
def auth_headers():
    """Create authorization headers with a test token.
    
    Use with authenticated endpoints.
    """
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_auth():
    """Mock the decode_token function to return a test user ID.
    
    All authenticated requests will be treated as user_id=1.
    """
    with patch("src.api.deps.decode_token") as mock:
        mock.return_value = 1
        yield mock


@pytest.fixture
def mock_auth_user_id():
    """Mock auth that returns a specific user ID.
    
    Use as a factory: mock_auth_user_id(42) -> returns user_id=42
    """
    def _mock_auth(user_id=1):
        with patch("src.api.deps.decode_token") as mock:
            mock.return_value = user_id
            yield mock
    return _mock_auth


# ==================== Database Fixtures ====================

@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database engine for testing.
    
    Tables are created automatically. Use db_session for actual operations.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing.
    
    Automatically closes after the test.
    """
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_db():
    """Mock the get_db dependency.
    
    Use for API tests that need database mocking.
    """
    db = MagicMock()
    with patch("src.api.routers.games.get_db", return_value=db):
        yield db


@pytest.fixture
def temp_db_file():
    """Create a temporary SQLite database file.
    
    Use for tests that need file-based database.
    Automatically cleans up after the test.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    engine = create_engine(f"sqlite:///{path}", echo=False)
    Base.metadata.create_all(engine)
    
    yield engine, path
    
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


# ==================== Session Store Fixtures ====================

@pytest.fixture
def mock_session_store():
    """Mock the session_store for API tests.
    
    Provides a MagicMock that can be configured for different scenarios.
    """
    with patch("src.api.routers.games.session_store") as mock:
        yield mock


@pytest.fixture
def mock_session_service():
    """Mock the session_service for API tests."""
    with patch("src.api.routers.games.session_service") as mock:
        yield mock


@pytest.fixture
def mock_session():
    """Create a mock game session with default state.
    
    Returns a MagicMock configured with typical session data.
    """
    session = MagicMock()
    session.game_id = 1
    session.game_loop = MagicMock()
    session.game_loop.get_state.return_value = MagicMock(
        to_dict=lambda: {
            "player_name": "TestPlayer",
            "energy": 100,
            "mood": 80,
        }
    )
    session.game_loop.get_progress.return_value = {"week": 1, "age": 25}
    session.game_loop.get_round_info.return_value = {
        "current_round": 0,
        "rounds_per_week": 3,
    }
    session.game_loop.current_event = None
    return session


# ==================== User Manager Fixtures ====================

@pytest.fixture
def mock_user_manager():
    """Mock UserManager for auth tests."""
    with patch("src.api.routers.auth.get_user_manager") as mock:
        manager = MagicMock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_create_token():
    """Mock create_token for auth tests."""
    with patch("src.api.routers.auth.create_token") as mock:
        mock.return_value = "test_jwt_token"
        yield mock


# ==================== Game State Fixtures ====================

@pytest.fixture
def sample_player_state():
    """Create a sample PlayerState for testing.
    
    Returns a PlayerState with reasonable default values.
    """
    state = PlayerState()
    state.player_name = "TestPlayer"
    state.energy = 100
    state.mood = 80
    state.money = 1000
    state.knowledge = 50
    state.social = 60
    state.week = 1
    state.age = 25
    return state


@pytest.fixture
def sample_game_state_dict():
    """Create a sample game state dictionary.
    
    Use for tests that need raw state data.
    """
    return {
        "player_name": "TestPlayer",
        "energy": 100,
        "mood": 80,
        "money": 1000,
        "knowledge": 50,
        "social": 60,
        "week": 1,
        "age": 25,
        "relationships": {},
        "characters": {},
    }


@pytest.fixture
def sample_event():
    """Create a sample game event for testing."""
    return {
        "event_description": "You wake up on a Monday morning, feeling refreshed.",
        "options": [
            {"text": "Go for a morning jog", "effects": {"energy": -10, "mood": 5}},
            {"text": "Sleep in", "effects": {"energy": 5, "mood": -5}},
            {"text": "Start working immediately", "effects": {"energy": -20, "money": 50}},
        ],
    }


# ==================== Database Model Fixtures ====================

@pytest.fixture
def sample_user(db_session):
    """Create a sample user in the database.
    
    Returns the created User object.
    """
    user = User(
        private_id="TEST-PRIVATE-ID-12345",
        public_id="TESTPUB1",
        display_name="TestUser"
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_game(db_session, sample_user):
    """Create a sample game in the database.
    
    Returns the created Game object.
    """
    game = Game(
        user_id=sample_user.user_id,
        player_name="TestPlayer",
        state={"week": 1, "age": 25},
    )
    db_session.add(game)
    db_session.commit()
    return game


# ==================== AI Service Fixtures ====================

@pytest.fixture
def mock_ai_client():
    """Mock the AI client for tests that don't need real AI calls."""
    with patch("src.ai.client.AIClient") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_story_generator():
    """Mock the story generator."""
    with patch("src.ai.story_generator.StoryGenerator") as mock:
        generator = MagicMock()
        mock.return_value = generator
        yield generator


# ==================== Test Data Fixtures ====================

@pytest.fixture
def sample_character_settings():
    """Create sample character settings for game creation tests."""
    return {
        "era": {"era_name": "现代", "description": "Contemporary era"},
        "age": {"start_age": 25},
        "gender": {"gender": "male"},
        "world": {"world_name": "Earth", "description": "Modern world"},
        "family": {
            "family_background": "Middle-class family",
            "parents": ["Father - Engineer", "Mother - Teacher"],
        },
        "relationships": {
            "key_people": [
                {"name": "Friend A", "relationship": "Best friend"},
                {"name": "Friend B", "relationship": "Colleague"},
            ]
        },
        "traits": {"personality": ["curious", "ambitious"]},
        "wealth": {"initial_wealth": "middle"},
    }


# ==================== Utility Fixtures ====================

@pytest.fixture
def freeze_time():
    """Freeze time to a specific moment.
    
    Use as: freeze_time("2024-01-01 12:00:00")
    """
    def _freeze(time_str):
        with patch("datetime.datetime") as mock:
            mock.now.return_value = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            yield mock
    return _freeze
