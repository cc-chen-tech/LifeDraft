"""SQLite database models."""

from datetime import datetime
from typing import Any

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey, Index,
                        Integer, String, Text, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config.settings import settings

Base: Any = declarative_base()


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
        "GamePlaylist", back_populates="game", uselist=False, cascade="all, delete-orphan"
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


class SceneImage(Base):
    """Scene image model - 场景插图"""

    __tablename__ = "scene_images"

    scene_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    week = Column(Integer, nullable=False, default=0)  # ★ 新增：周数
    round_number = Column(Integer, nullable=False)  # 对应游戏轮次
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
    current_song_json = Column(JSON, nullable=True)   # type: ignore[var-annotated]
    queue_json = Column(JSON, default=list)           # type: ignore[var-annotated]
    played_songs_json = Column(JSON, default=list)    # type: ignore[var-annotated]
    is_playing = Column(Boolean, default=False)
    volume = Column(Float, default=0.5)
    current_position_ms = Column(Integer, default=0)

    # Recommendation metadata
    recommendation_mood = Column(String(50), nullable=True)
    recommendation_keywords = Column(JSON, nullable=True)  # type: ignore[var-annotated]

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    game = relationship("Game", back_populates="playlist")


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

SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Initialize database tables and performance indexes."""
    Base.metadata.create_all(engine, checkfirst=True)
    # ★ 自动创建性能优化索引（向后兼容：已存在则跳过）
    try:
        from src.database.add_performance_indexes import \
            create_performance_indexes

        create_performance_indexes()
    except Exception:
        # 索引创建失败不应阻塞应用启动
        import logging

        logging.getLogger(__name__).warning("Failed to create performance indexes", exc_info=True)


def get_db():
    """Get database session as context manager."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def with_db_session(func):
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
    def wrapper(*args, **kwargs):
        # If db is explicitly passed, use it directly (testing support)
        if "db" in kwargs:
            return func(*args, **kwargs)

        # Otherwise create a new session
        db = SessionLocal()
        try:
            return func(*args, db=db, **kwargs)
        finally:
            db.close()

    return wrapper
