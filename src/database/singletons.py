"""Database singletons - centralized singleton management.

This module provides singleton access to database-related classes,
eliminating circular dependencies between api.deps and api.services.

Usage:
    from src.database.singletons import get_game_db, get_user_manager

    db = get_game_db()  # Returns GameDatabase singleton
    user_mgr = get_user_manager()  # Returns UserManager singleton
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.database.db import GameDatabase
    from src.database.user_manager import UserManager

# Singletons (initialized once)
_game_db: Optional["GameDatabase"] = None
_user_manager: Optional["UserManager"] = None


def get_game_db() -> "GameDatabase":
    """Get the global GameDatabase singleton.

    Returns:
        GameDatabase: The shared database instance.
    """
    global _game_db
    if _game_db is None:
        from src.database.db import GameDatabase

        _game_db = GameDatabase()
    return _game_db


def get_user_manager() -> "UserManager":
    """Get the global UserManager singleton.

    Returns:
        UserManager: The shared user manager instance.
    """
    global _user_manager
    if _user_manager is None:
        from src.database.user_manager import UserManager

        _user_manager = UserManager()
    return _user_manager
