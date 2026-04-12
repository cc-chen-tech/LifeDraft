"""Configuration management for the game."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Sentry 错误监控配置
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "development")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
PRESETS_DIR = DATA_DIR / "presets"
CACHE_DIR = DATA_DIR / "cache"

# Ensure data directories exist (only for local development)
try:
    DATA_DIR.mkdir(exist_ok=True)
    PRESETS_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
except Exception:
    pass  # May fail in cloud environments, which is ok


class Settings:
    """Game settings and configuration."""

    # OpenAI API Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    OPENAI_BASE_URL: Optional[str] = os.getenv("OPENAI_BASE_URL")

    # ========== Image Generation Configuration ==========
    # 图像生成API（OpenAI兼容接口）
    IMAGE_API_KEY: Optional[str] = os.getenv("IMAGE_API_KEY")
    IMAGE_API_BASE_URL: Optional[str] = os.getenv("IMAGE_API_BASE_URL")
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "wanx-v1")

    # 场景分析服务（复用现有DeepSeek配置或独立配置）
    SCENE_ANALYZER_API_KEY: Optional[str] = os.getenv("SCENE_ANALYZER_API_KEY")
    SCENE_ANALYZER_BASE_URL: Optional[str] = os.getenv("SCENE_ANALYZER_BASE_URL")
    SCENE_ANALYZER_MODEL: str = os.getenv("SCENE_ANALYZER_MODEL", "deepseek-chat")

    # 图片存储配置
    IMAGE_STORAGE_TYPE: str = os.getenv("IMAGE_STORAGE_TYPE", "local")  # local | oss
    IMAGE_LOCAL_PATH: Path = PROJECT_ROOT / "data" / "images"

    # OSS配置（长期使用）
    OSS_ACCESS_KEY_ID: Optional[str] = os.getenv("OSS_ACCESS_KEY_ID")
    OSS_ACCESS_KEY_SECRET: Optional[str] = os.getenv("OSS_ACCESS_KEY_SECRET")
    OSS_ENDPOINT: Optional[str] = os.getenv("OSS_ENDPOINT")
    OSS_BUCKET_NAME: Optional[str] = os.getenv("OSS_BUCKET_NAME")

    # 图像生成配置
    IMAGE_GENERATION_TIMEOUT: int = int(
        os.getenv("IMAGE_GENERATION_TIMEOUT", "120")
    )  # ★ 默认120秒，图生图需要更长时间
    IMAGE_MAX_RETRIES: int = int(os.getenv("IMAGE_MAX_RETRIES", "3"))

    # ★ 模型降级配置（逗号分隔，必须在.env中显式配置）
    TEXT_TO_IMAGE_MODELS: str = os.getenv("TEXT_TO_IMAGE_MODELS", "")
    IMAGE_EDIT_MODELS: str = os.getenv("IMAGE_EDIT_MODELS", "")

    # Game Configuration
    DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "zh")  # en or zh
    CACHE_EVENTS: bool = os.getenv("CACHE_EVENTS", "true").lower() == "true"
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"

    # Game Constants
    STARTING_AGE: int = 22
    ENDING_AGE: int = 30
    WEEKS_PER_YEAR: int = 52
    # Total game duration: 96 weeks (approximately 2 years)
    TOTAL_WEEKS: int = 96

    # Weekly game mechanics
    EVENTS_PER_WEEK: int = 1  # Generate 1 event per week

    # Initial State Values
    INITIAL_ENERGY: int = 70
    INITIAL_MOOD: int = 60
    INITIAL_KNOWLEDGE: int = 50
    INITIAL_WEALTH: int = 10000

    # Resource Bounds
    MIN_RESOURCE: int = 0
    MAX_RESOURCE: int = 100
    MAX_WEALTH: int = 1000000  # No upper limit for wealth

    # Weekly Decay (if applicable)
    ENERGY_DECAY: int = 5  # If no rest
    MOOD_DECAY: int = 2  # If stressed

    # Multi-round System
    ROUNDS_PER_WEEK: int = 3  # Number of rounds per week
    MILESTONE_WEEKS: list = [20, 40, 60, 80]  # Weeks with milestone events

    # AI Generation Timeout
    GENERATION_TIMEOUT: float = 60.0  # Max seconds before auto-reset

    # Database Configuration
    # Priority: DATABASE_URL (cloud) > DATABASE_PATH (local SQLite)
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    DATABASE_PATH: Path = PROJECT_ROOT / "data" / "game.db"

    @classmethod
    def get_image_api_key(cls) -> Optional[str]:
        """获取图像API密钥，如果未配置则复用OpenAI密钥"""
        return cls.IMAGE_API_KEY or cls.OPENAI_API_KEY

    @classmethod
    def get_image_api_base_url(cls) -> Optional[str]:
        """获取图像API基础URL，如果未配置则复用OpenAI基础URL"""
        return cls.IMAGE_API_BASE_URL or cls.OPENAI_BASE_URL

    @classmethod
    def get_scene_analyzer_api_key(cls) -> Optional[str]:
        """获取场景分析API密钥，如果未配置则复用OpenAI密钥"""
        return cls.SCENE_ANALYZER_API_KEY or cls.OPENAI_API_KEY

    @classmethod
    def get_scene_analyzer_base_url(cls) -> Optional[str]:
        """获取场景分析API基础URL，如果未配置则复用OpenAI基础URL"""
        return cls.SCENE_ANALYZER_BASE_URL or cls.OPENAI_BASE_URL

    @classmethod
    def get_database_url(cls) -> str:
        """获取数据库连接URL"""
        if cls.DATABASE_URL:
            # 云数据库模式 (PostgreSQL/MySQL/etc.)
            return cls.DATABASE_URL
        else:
            # 本地SQLite模式
            return f"sqlite:///{cls.DATABASE_PATH}"

    @classmethod
    def validate(cls) -> bool:
        """Validate that required settings are configured."""
        if not cls.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY not found. Please set it in .env file or environment variables."
            )
        return True

    @classmethod
    def ensure_image_dir(cls) -> None:
        """确保图片存储目录存在"""
        if cls.IMAGE_STORAGE_TYPE == "local":
            try:
                cls.IMAGE_LOCAL_PATH.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass  # May fail in some environments, which is ok

    @classmethod
    def get_language(cls) -> str:
        """Get the current language setting."""
        return cls.DEFAULT_LANGUAGE


# Create a singleton instance
settings = Settings()
