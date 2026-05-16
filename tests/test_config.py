"""Tests for config layer: settings.py, logging_config.py."""

import logging
from pathlib import Path

import pytest

# ==================== Settings Tests ====================


class TestSettings:
    """Test Settings class and module-level constants."""

    def test_project_root_exists(self):
        """Test PROJECT_ROOT points to a valid directory."""
        from config.settings import PROJECT_ROOT

        assert PROJECT_ROOT.exists()
        assert PROJECT_ROOT.is_dir()

    def test_data_dirs_defined(self):
        """Test data directory paths are defined."""
        from config.settings import CACHE_DIR, DATA_DIR, PRESETS_DIR

        assert isinstance(DATA_DIR, Path)
        assert isinstance(PRESETS_DIR, Path)
        assert isinstance(CACHE_DIR, Path)

    def test_settings_class_constants(self):
        """Test Settings class has expected constants."""
        from config.settings import Settings

        assert Settings.STARTING_AGE == 22
        assert Settings.ENDING_AGE == 30
        assert Settings.WEEKS_PER_YEAR == 52
        assert Settings.TOTAL_WEEKS == 96
        assert Settings.EVENTS_PER_WEEK == 1
        assert Settings.INITIAL_ENERGY == 70
        assert Settings.INITIAL_MOOD == 60
        assert Settings.INITIAL_KNOWLEDGE == 50
        assert Settings.INITIAL_WEALTH == 10000
        assert Settings.MIN_RESOURCE == 0
        assert Settings.MAX_RESOURCE == 100
        assert Settings.MAX_WEALTH == 1000000
        assert Settings.ENERGY_DECAY == 5
        assert Settings.MOOD_DECAY == 2

    def test_settings_database_path(self):
        """Test DATABASE_PATH is a Path object."""
        from config.settings import Settings

        assert isinstance(Settings.DATABASE_PATH, Path)

    def test_get_database_url_sqlite(self):
        """Test get_database_url returns SQLite URL when no DATABASE_URL env."""
        from config.settings import Settings

        original = Settings.DATABASE_URL
        try:
            Settings.DATABASE_URL = None
            url = Settings.get_database_url()
            assert url.startswith("sqlite:///")
        finally:
            Settings.DATABASE_URL = original

    def test_get_database_url_cloud(self):
        """Test get_database_url returns cloud URL when DATABASE_URL is set."""
        from config.settings import Settings

        original = Settings.DATABASE_URL
        try:
            Settings.DATABASE_URL = "postgresql://user:pass@host/db"
            url = Settings.get_database_url()
            assert url == "postgresql://user:pass@host/db"
        finally:
            Settings.DATABASE_URL = original

    def test_validate_with_api_key(self):
        """Test validate passes when OPENAI_API_KEY is set."""
        from config.settings import Settings

        original = Settings.OPENAI_API_KEY
        try:
            Settings.OPENAI_API_KEY = "test-key"
            assert Settings.validate() is True
        finally:
            Settings.OPENAI_API_KEY = original

    def test_validate_without_api_key_raises(self):
        """Test validate raises when OPENAI_API_KEY is missing."""
        from config.settings import Settings

        original = Settings.OPENAI_API_KEY
        try:
            Settings.OPENAI_API_KEY = None
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                Settings.validate()
        finally:
            Settings.OPENAI_API_KEY = original

    def test_get_language(self):
        """Test get_language returns DEFAULT_LANGUAGE."""
        from config.settings import Settings

        lang = Settings.get_language()
        assert lang in ("zh", "en")

    def test_singleton_instance(self):
        """Test settings singleton is created."""
        from config.settings import Settings, settings

        assert settings is not None
        assert isinstance(settings, Settings)


# ==================== Logging Config Tests ====================


class TestLoggingConfig:
    """Test logging configuration."""

    def test_setup_logging_console_only(self, tmp_path):
        """Test setup_logging with console only (no file)."""
        from config.logging_config import setup_logging

        logger = setup_logging(log_level="DEBUG", log_to_file=False)
        assert logger is not None
        assert logger.level == logging.DEBUG

    def test_setup_logging_with_file(self, tmp_path):
        """Test setup_logging with file handler."""
        from config.logging_config import setup_logging

        logger = setup_logging(
            log_level="WARNING", log_to_file=True, log_file="test.log"
        )
        assert logger.level == logging.WARNING
        # Check file handler was added
        has_file_handler = any(
            isinstance(h, logging.handlers.RotatingFileHandler) for h in logger.handlers
        )
        assert has_file_handler

    def test_setup_logging_info_level(self):
        """Test setup_logging with INFO level."""
        from config.logging_config import setup_logging

        logger = setup_logging(log_level="INFO", log_to_file=False)
        assert logger.level == logging.INFO

    def test_setup_logging_invalid_level_defaults_to_info(self):
        """Test invalid log level defaults to INFO."""
        from config.logging_config import setup_logging

        logger = setup_logging(log_level="NONEXISTENT", log_to_file=False)
        assert logger.level == logging.INFO

    def test_setup_logging_clears_handlers(self):
        """Test setup_logging clears existing handlers."""
        from config.logging_config import setup_logging

        # First call adds handlers
        setup_logging(log_to_file=False)
        # Second call should clear and re-add
        logger = setup_logging(log_to_file=False)
        # Should have exactly 1 console handler
        console_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        assert len(console_handlers) >= 1

    def test_third_party_log_levels(self):
        """Test third party library log levels are set to WARNING."""
        from config.logging_config import setup_logging

        setup_logging(log_to_file=False)
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("openai").level == logging.WARNING
        assert logging.getLogger("urllib3").level == logging.WARNING

    def test_log_dir_exists(self):
        """Test LOG_DIR is created."""
        from config.logging_config import LOG_DIR

        assert LOG_DIR.exists()
