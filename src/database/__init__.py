"""Database package."""

from src.database.models import (
    Base,
    CharacterPreset,
    Decision,
    Ending,
    Friendship,
    Game,
    GameState,
    SessionLocal,
    User,
    engine,
    get_db,
    init_db,
)
from src.database.singletons import get_game_db, get_user_manager
from src.database.user_manager import UserManager, generate_private_id, generate_public_id

__all__ = [
    "Base",
    "User",
    "Friendship",
    "Game",
    "GameState",
    "Decision",
    "Ending",
    "CharacterPreset",
    "engine",
    "SessionLocal",
    "init_db",
    "get_db",
    "get_game_db",
    "get_user_manager",
    "UserManager",
    "generate_private_id",
    "generate_public_id",
]
