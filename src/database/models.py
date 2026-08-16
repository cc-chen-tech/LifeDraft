"""SQLite database models."""

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Callable, Generator, TypeVar, cast

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Index, Integer, String, Text, create_engine, inspect, text)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from config.settings import settings

VOICE_ASSET_VERSION = 2


class Base(DeclarativeBase):
    pass


F = TypeVar("F", bound=Callable[..., Any])


class User(Base):
    """用户模型 - 支持通过私有ID登录，公有ID加好友"""

    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    private_id = Column(String(32), unique=True, nullable=False, index=True)  # 登录用
    public_id = Column(String(8), unique=True, nullable=False, index=True)  # 显示/加好友用
    display_name = Column(String(50), nullable=True)  # 可选昵称
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # ★ 服务端会话管理：记录最近活跃的游戏ID，用于自动恢复
    last_active_game_id = Column(Integer, ForeignKey("games.game_id"), nullable=True, index=True)

    # 关联
    # 明确指定 foreign_keys，因为 users-games 之间存在两个外键路径
    games = relationship(
        "Game",
        foreign_keys="Game.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # 我发起的好友请求
    sent_friend_requests = relationship(
        "Friendship",
        foreign_keys="Friendship.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # 我收到的好友请求
    received_friend_requests = relationship(
        "Friendship",
        foreign_keys="Friendship.friend_id",
        back_populates="friend",
        cascade="all, delete-orphan",
    )


class Friendship(Base):
    """好友关系模型"""

    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)  # 发起者
    friend_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)  # 接收者
    status = Column(String(20), default="pending")  # pending/accepted/rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    user = relationship("User", foreign_keys=[user_id], back_populates="sent_friend_requests")
    friend = relationship(
        "User", foreign_keys=[friend_id], back_populates="received_friend_requests"
    )

    # 确保同一对用户之间只有一条好友记录
    __table_args__ = (Index("ix_friendship_pair", "user_id", "friend_id", unique=True),)


class Game(Base):
    """Game session model."""

    __tablename__ = "games"

    game_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)  # 关联用户
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True
    )  # 最后修改时间，H-08: 添加索引
    language = Column(String(10), default="en")
    initial_state = Column(JSON)
    final_state = Column(JSON, nullable=True)
    ending_type = Column(String(50), nullable=True)
    ending_summary = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)  # 是否公开给好友查看
    narrative_style_id = Column(String, nullable=True)  # 叙事风格ID
    constraint_level = Column(String, default="expert")  # 叙事质量级别: fast/expert/master

    # Relationships
    user = relationship("User", back_populates="games", foreign_keys=[user_id])
    states = relationship("GameState", back_populates="game", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="game", cascade="all, delete-orphan")
    ending = relationship(
        "Ending", back_populates="game", cascade="all, delete-orphan", uselist=False
    )
    images = relationship("Image", back_populates="game", cascade="all, delete-orphan")
    scene_images = relationship("SceneImage", back_populates="game", cascade="all, delete-orphan")
    playlist = relationship(
        "GamePlaylist",
        back_populates="game",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # ★ 复合索引：加速 list_saved_games 查询 (user_id + ending_type IS NULL + ORDER BY updated_at)
    __table_args__ = (
        Index("ix_games_user_ending_updated", "user_id", "ending_type", "updated_at"),
    )


class GameState(Base):
    """Game state snapshot model."""

    __tablename__ = "game_states"

    state_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    week = Column(Integer, nullable=False)
    age = Column(Integer, nullable=False)
    state_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ★ 时间回溯存档系统：区分手动存档点和自动快照
    is_save_point = Column(Boolean, default=False)  # 是否为手动存档点
    save_name = Column(String(100), nullable=True)  # 存档名称（可选）

    # Relationships
    game = relationship("Game", back_populates="states")

    # H-08: 复合索引优化查询性能
    __table_args__ = (
        Index("ix_game_state_game_week", "game_id", "week"),
        # ★ 加速 load_saved_game 的 ORDER BY created_at DESC 查询
        Index("ix_game_state_game_created", "game_id", "created_at"),
    )


class Decision(Base):
    """Decision record model."""

    __tablename__ = "decisions"

    decision_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False)
    week = Column(Integer, nullable=False)
    event_description = Column(Text, nullable=False)
    choice_text = Column(String(200), nullable=False)
    effects = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    game = relationship("Game", back_populates="decisions")

    # H-08: 复合索引优化查询性能
    __table_args__ = (Index("ix_decision_game_week", "game_id", "week"),)


class Ending(Base):
    """Ending record model."""

    __tablename__ = "endings"

    ending_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, unique=True)
    final_state = Column(JSON, nullable=False)
    ending_type = Column(String(50), nullable=False)
    summary = Column(Text, nullable=False)
    achievements = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    game = relationship("Game", back_populates="ending", uselist=False)


class CharacterPreset(Base):
    """Character preset model for saving character creation settings."""

    __tablename__ = "character_presets"

    preset_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.user_id"), nullable=True, index=True
    )  # 关联用户，可为空（兼容旧数据）
    preset_name = Column(String(100), nullable=False)
    player_name = Column(String(100), nullable=False)
    life_vision = Column(Text, nullable=True)
    character_settings = Column(JSON, nullable=False)
    narrative_style_id = Column(String, default="chinese_classic_saga")  # 叙事风格ID
    constraint_level = Column(String, default="expert")  # 叙事质量级别: fast/expert/master
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    user = relationship("User", backref="character_presets")


class Image(Base):
    """Image model - 存储所有生成的图片（人物/地点/物品）"""

    __tablename__ = "images"

    image_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)

    # 图片类型: character(人物) | location(地点) | item(物品)
    image_type = Column(String(20), nullable=False, index=True)

    # 实体标识（用于关联）
    entity_name = Column(String(100), nullable=False)  # 人物名/地点名/物品名
    entity_key = Column(String(100), nullable=True)  # 唯一标识键（如 player_main, npc_1 等）

    # 图片信息
    prompt_text = Column(Text, nullable=False)  # 生成时使用的prompt
    storage_path = Column(String(500), nullable=False)  # 存储路径
    storage_type = Column(String(20), default="local")  # local | oss

    # 元数据
    metadata_json = Column(JSON, nullable=True)  # 额外信息(JSON)

    # 版本控制（支持重新生成）
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)  # 是否为当前版本

    # 主图/变体关系
    is_primary = Column(Boolean, default=False)  # 是否为主图（第一张）
    primary_image_id = Column(Integer, ForeignKey("images.image_id"), nullable=True)  # 关联的主图ID

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联
    game = relationship("Game", back_populates="images")

    # 索引
    __table_args__ = (
        Index("ix_images_game_type_entity", "game_id", "image_type", "entity_name"),
        Index("idx_image_lookup", "game_id", "image_type", "entity_name", "is_active"),
    )


class PortraitImageGenerationJob(Base):
    """Durable background job for a game's main-character portrait."""

    __tablename__ = "portrait_image_generation_jobs"

    job_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    entity_key = Column(String(100), nullable=False, default="player_main")
    request_json = Column(JSON, nullable=False)
    image_id = Column(Integer, ForeignKey("images.image_id"), nullable=True)
    status = Column(String(20), nullable=False, index=True, default="queued")
    attempt_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    game = relationship("Game")
    user = relationship("User")
    image = relationship("Image")

    __table_args__ = (
        Index(
            "ix_portrait_image_jobs_active_lookup",
            "game_id",
            "user_id",
            "entity_key",
            "status",
            "created_at",
        ),
    )


class SceneImage(Base):
    """Scene image model - 场景插图"""

    __tablename__ = "scene_images"

    scene_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    week = Column(Integer, nullable=False, default=0)  # ★ 新增：周数
    round_number = Column(Integer, nullable=False)  # 对应游戏轮次
    story_date = Column(String(10), nullable=True, index=True)
    day_index = Column(Integer, nullable=True, index=True)
    stage = Column(String(20), default="result")  # ★ event(事件故事) | result(结果故事)

    # 场景信息
    scene_description = Column(Text, nullable=False)  # 场景描述
    final_prompt = Column(Text, nullable=False)  # 最终生成的prompt

    # 生成的场景图片
    storage_path = Column(String(500), nullable=False)
    storage_type = Column(String(20), default="local")  # local | oss

    # 关联的实体图片ID列表
    referenced_images = Column(JSON, nullable=True)  # [image_id1, image_id2, ...]

    # 元数据
    importance_score = Column(String(10), nullable=True)  # 重要性评分

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联
    game = relationship("Game", back_populates="scene_images")

    # 索引 - 包含 week 的唯一复合索引，防止并发时重复写入同一场景
    __table_args__ = (
        Index(
            "ix_scene_images_game_week_round_stage",
            "game_id",
            "week",
            "round_number",
            "stage",
            unique=True,
        ),
        Index(
            "ix_scene_images_game_day_stage",
            "game_id",
            "day_index",
            "stage",
            unique=True,
        ),
    )


class GamePlaylist(Base):
    """Per-game persistent music playlist.

    Stores the current song, upcoming queue, and playback state
    so music survives page navigation and game progression.
    """

    __tablename__ = "game_playlists"

    playlist_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, unique=True, index=True)

    # Playback state
    current_song_json = Column(JSON, nullable=True)
    queue_json = Column(JSON, default=list)
    played_songs_json = Column(JSON, default=list)
    is_playing = Column(Boolean, default=False)
    volume = Column(Float, default=0.5)
    current_position_ms = Column(Integer, default=0)

    # Recommendation metadata
    recommendation_mood = Column(String(50), nullable=True)
    recommendation_keywords = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    game = relationship("Game", back_populates="playlist")


class VoiceReadingSetting(Base):
    """Persisted per-user voice reading settings."""

    __tablename__ = "voice_reading_settings"

    setting_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, unique=True, index=True)
    selected_voice_color = Column(String(80), nullable=True)
    auto_read_enabled = Column(Boolean, default=True, nullable=False)
    selected_speed = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")


class GeneratedVoiceAsset(Base):
    """Persisted metadata for reusable generated story narration audio."""

    __tablename__ = "generated_voice_assets"

    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    source_type = Column(String(40), nullable=False, index=True)
    context_json = Column(JSON, nullable=False)
    text_hash = Column(String(128), nullable=False, index=True)
    voice_id = Column(String(80), nullable=False, index=True)
    speed = Column(Float, default=1.0, nullable=False)
    provider = Column(String(80), nullable=False, index=True)
    model = Column(String(120), nullable=False)
    storage_path = Column(String(500), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    asset_version = Column(Integer, default=VOICE_ASSET_VERSION, nullable=False)
    status = Column(String(30), nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        Index(
            "ix_generated_voice_asset_hash_voice_speed",
            "text_hash",
            "voice_id",
            "speed",
            "status",
        ),
    )


class VoiceReadingJob(Base):
    """Story narration job state recoverable after reload."""

    __tablename__ = "voice_reading_jobs"

    job_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    dedupe_key = Column(String(128), nullable=True, unique=True, index=True)
    asset_id = Column(Integer, ForeignKey("generated_voice_assets.asset_id"), nullable=True)
    context_json = Column(JSON, nullable=False)
    text_hash = Column(String(128), nullable=False, index=True)
    voice_id = Column(String(80), nullable=False)
    speed = Column(Float, default=1.0, nullable=False)
    asset_version = Column(Integer, default=VOICE_ASSET_VERSION, nullable=False)
    status = Column(String(30), nullable=False, index=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    asset = relationship("GeneratedVoiceAsset")
    segments = relationship(
        "VoiceReadingSegment",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="VoiceReadingSegment.paragraph_index",
    )


class VoiceReadingSegment(Base):
    """One ordered paragraph in a chapter narration job."""

    __tablename__ = "voice_reading_segments"

    segment_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("voice_reading_jobs.job_id"), nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("generated_voice_assets.asset_id"), nullable=True)
    paragraph_index = Column(Integer, nullable=False)
    text_hash = Column(String(128), nullable=False, index=True)
    text_content = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="queued", index=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    job = relationship("VoiceReadingJob", back_populates="segments")
    asset = relationship("GeneratedVoiceAsset")

    __table_args__ = (
        Index(
            "ix_voice_segment_job_paragraph",
            "job_id",
            "paragraph_index",
            unique=True,
        ),
    )


class VoiceReadingProgress(Base):
    """Per-story listening position owned by one user."""

    __tablename__ = "voice_reading_progress"

    progress_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    day_index = Column(Integer, nullable=False)
    story_date = Column(String(10), nullable=True)
    text_hash = Column(String(128), nullable=False)
    voice_id = Column(String(80), nullable=False)
    speed = Column(Float, nullable=False, default=1.0)
    paragraph_index = Column(Integer, nullable=False, default=0)
    position_ms = Column(Integer, nullable=False, default=0)
    completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")
    game = relationship("Game")

    __table_args__ = (
        Index(
            "ix_voice_progress_story_identity",
            "user_id",
            "game_id",
            "day_index",
            "text_hash",
            "voice_id",
            "speed",
            unique=True,
        ),
    )


class DailyRecommendedPrefetch(Base):
    """Persisted speculative next-day event for one recommended choice."""

    __tablename__ = "daily_recommended_prefetches"

    prefetch_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    event_id = Column(String(96), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    day_index = Column(Integer, nullable=False)
    option_index = Column(Integer, nullable=False)
    state_fingerprint = Column(String(128), nullable=False)
    status = Column(String(30), nullable=False, default="queued", index=True)
    next_event_json = Column(JSON, nullable=True)
    tts_job_id = Column(Integer, ForeignKey("voice_reading_jobs.job_id"), nullable=True)
    voice_id = Column(String(80), nullable=True)
    voice_speed = Column(Float, nullable=True)
    demanded = Column(Boolean, nullable=False, default=False)
    lease_token = Column(String(64), nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True)
    error_code = Column(String(80), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    consumed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ix_daily_recommended_prefetch_identity",
            "game_id",
            "event_id",
            "revision",
            "option_index",
            "state_fingerprint",
            unique=True,
        ),
    )


class GeneratedMusicAsset(Base):
    """Persisted metadata for reusable AI-generated background music."""

    __tablename__ = "generated_music_assets"

    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    source = Column(String(30), default="ai_generated", nullable=False)
    provider = Column(String(80), nullable=False, index=True)
    model = Column(String(120), nullable=False)
    status = Column(String(30), nullable=False, index=True)
    music_brief_json = Column(JSON, nullable=False)
    prompt_text = Column(Text, nullable=False)
    brief_hash = Column(String(128), nullable=False, index=True)
    storage_path = Column(String(500), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    loopable = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    game = relationship("Game")
    library_entry = relationship(
        "GeneratedMusicLibraryEntry",
        back_populates="asset",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (
        Index(
            "ix_generated_music_asset_brief_provider",
            "brief_hash",
            "provider",
        ),
    )


class GeneratedMusicLibraryEntry(Base):
    """Sanitized searchable profile for a ready AI-generated music asset."""

    __tablename__ = "generated_music_library_entries"

    entry_id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(
        Integer,
        ForeignKey("generated_music_assets.asset_id"),
        nullable=False,
        unique=True,
        index=True,
    )
    source_game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    provider = Column(String(80), nullable=False, index=True)
    model = Column(String(120), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)
    mood = Column(String(120), nullable=False, index=True)
    scene_type = Column(String(160), nullable=False, index=True)
    environment = Column(String(240), nullable=False, index=True)
    pacing = Column(String(80), nullable=False)
    energy = Column(String(80), nullable=False, index=True)
    instruments_json = Column(JSON, nullable=False)
    negative_cues_json = Column(JSON, nullable=False)
    generation_settings_json = Column(JSON, nullable=False)
    prompt_fingerprint = Column(String(128), nullable=False, index=True)
    duration_ms = Column(Integer, nullable=False)
    loopable = Column(Boolean, default=True, nullable=False, index=True)
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    last_used_game_id = Column(Integer, ForeignKey("games.game_id"), nullable=True, index=True)
    last_match_score = Column(Integer, nullable=True)
    last_match_reason = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    asset = relationship("GeneratedMusicAsset", back_populates="library_entry")
    source_game = relationship("Game", foreign_keys=[source_game_id])
    last_used_game = relationship("Game", foreign_keys=[last_used_game_id])

    __table_args__ = (
        Index(
            "ix_music_library_lookup",
            "status",
            "provider",
            "model",
            "scene_type",
            "mood",
            "energy",
        ),
        Index(
            "ix_music_library_loopable_duration",
            "loopable",
            "duration_ms",
        ),
        Index(
            "ix_music_library_status_updated",
            "status",
            "updated_at",
        ),
    )


# Create engine and session
# 使用 settings.get_database_url() 支持云数据库
database_url = settings.get_database_url()

# C-03: 增强连接池配置
if database_url.startswith("postgresql"):
    engine = create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
    )
else:
    engine = create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db() -> None:
    """Initialize database tables and performance indexes."""
    Base.metadata.create_all(engine, checkfirst=True)
    _ensure_legacy_columns()
    # ★ 自动创建性能优化索引（向后兼容：已存在则跳过）
    try:
        from src.database.add_performance_indexes import \
            create_performance_indexes

        create_performance_indexes()  # type: ignore[no-untyped-call]
    except Exception:
        # 索引创建失败不应阻塞应用启动
        import logging

        logging.getLogger(__name__).warning("Failed to create performance indexes", exc_info=True)


def _ensure_legacy_columns() -> None:
    """Add compatible columns to existing SQLite and PostgreSQL databases."""
    legacy_columns = {
        "games": {
            "narrative_style_id": "VARCHAR",
            "constraint_level": "VARCHAR DEFAULT 'expert'",
        },
        "character_presets": {
            "narrative_style_id": "VARCHAR DEFAULT 'chinese_classic_saga'",
            "constraint_level": "VARCHAR DEFAULT 'expert'",
        },
        "scene_images": {
            "story_date": "VARCHAR(10)",
            "day_index": "INTEGER",
        },
        "voice_reading_settings": {
            "selected_speed": "FLOAT DEFAULT 1.0 NOT NULL",
        },
        "voice_reading_jobs": {
            "dedupe_key": "VARCHAR(128)",
            "asset_version": "INTEGER DEFAULT 1 NOT NULL",
        },
        "generated_voice_assets": {
            "asset_version": "INTEGER DEFAULT 1 NOT NULL",
        },
    }

    with engine.begin() as connection:
        inspector = inspect(connection)
        available_tables = set(inspector.get_table_names())
        for table_name, columns in legacy_columns.items():
            if table_name not in available_tables:
                continue
            existing = {
                str(column["name"])
                for column in inspector.get_columns(table_name)
            }
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    alter_query = (
                        'ALTER TABLE "'
                        + table_name
                        + '" ADD COLUMN "'
                        + column_name
                        + '" '
                        + column_type
                    )
                    connection.execute(text(alter_query))
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_voice_reading_jobs_dedupe_key_runtime "
                "ON voice_reading_jobs (dedupe_key)"
            )
        )


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Get database session as context manager."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def with_db_session(func: F) -> F:
    """
    Decorator that injects a database session as the first argument.

    Usage:
        @with_db_session
        def some_method(self, db: Session, other_args):
            # Use db session
            pass

    The decorator handles session creation and cleanup automatically.
    If 'db' is explicitly passed in kwargs, it will be used directly
    (useful for testing with custom sessions).
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # If db is explicitly passed, use it directly (testing support)
        if "db" in kwargs:
            return func(*args, **kwargs)

        # Otherwise create a new session
        db = SessionLocal()
        try:
            return func(*args, db=db, **kwargs)
        finally:
            db.close()

    return cast(F, wrapper)
