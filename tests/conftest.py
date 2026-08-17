"""
Shared pytest fixtures for all tests.

This file is automatically loaded by pytest and provides common fixtures
that can be used across all test files.

Usage:
    def test_something(client, auth_headers):
        response = client.get("/api/endpoint", headers=auth_headers)
        assert response.status_code == 200
"""

import os
import tempfile
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

# Patch httpx.Response for SSE contract tests (must be after all imports)
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.database.models import Base, Game, User
from src.game.state import PlayerState

if not hasattr(httpx.Response, "__enter__"):
    httpx.Response.__enter__ = lambda self: self
    httpx.Response.__exit__ = lambda self, *args: None

_original_iter_lines = httpx.Response.iter_lines


def _patched_iter_lines(self):
    for line in _original_iter_lines(self):
        yield line.encode("utf-8")


httpx.Response.iter_lines = _patched_iter_lines


@pytest.fixture(autouse=True)
def _restore_background_job_admission():
    """Keep the production shutdown flag from leaking between tests.

    ``TestClient(app)`` context managers run the real FastAPI lifespan, which
    calls ``shutdown_sse_thread_pool(prevent_new_background_jobs=True)`` and
    permanently disables background-job admission for the process. That would
    poison every later test that relies on background pools, so re-arm the
    flag after each test. Tests that assert the disabled path (e.g. the
    permanent-shutdown contract) still observe it during their own body.
    """
    yield
    from src.api.routers.gameplay import sse_helpers

    sse_helpers._background_jobs_enabled = True


@pytest.fixture
def constraint_harness_disabled(monkeypatch):
    """Explicitly select the non-Harness production configuration."""
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "false")


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
            {
                "text": "Start working immediately",
                "effects": {"energy": -20, "money": 50},
            },
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
        display_name="TestUser",
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


# ============================================================
# 优化测试专用 Fixtures
# ============================================================


@pytest.fixture
def thread_pool():
    """提供受控的 ThreadPoolExecutor，测试后自动 shutdown"""
    from concurrent.futures import ThreadPoolExecutor

    pool = ThreadPoolExecutor(max_workers=2)
    yield pool
    pool.shutdown(wait=False)


@pytest.fixture
def semaphore():
    """提供测试用异步信号量"""
    import asyncio

    return asyncio.Semaphore(2)


@pytest.fixture
def safe_image_dir(tmp_path):
    """创建安全的临时图片目录，用于路径遍历测试"""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    # 创建子目录结构
    char_dir = img_dir / "1" / "character"
    char_dir.mkdir(parents=True)
    (char_dir / "test.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    # 创建 round_scene 子目录
    scene_dir = img_dir / "1" / "round_scene"
    scene_dir.mkdir(parents=True)
    (scene_dir / "scene_w1_r1.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    return img_dir


@pytest.fixture
def mock_sse_manager():
    """模拟 SSE 连接管理器，带连接计数"""

    class SSEConnectionManager:
        def __init__(self, max_per_user=3, max_global=100):
            self.max_per_user = max_per_user
            self.max_global = max_global
            self._connections = {}  # user_id -> count
            self._total = 0

        def can_connect(self, user_id):
            user_count = self._connections.get(user_id, 0)
            return user_count < self.max_per_user and self._total < self.max_global

        def connect(self, user_id):
            if not self.can_connect(user_id):
                return False
            self._connections[user_id] = self._connections.get(user_id, 0) + 1
            self._total += 1
            return True

        def disconnect(self, user_id):
            if user_id in self._connections and self._connections[user_id] > 0:
                self._connections[user_id] -= 1
                self._total -= 1

        @property
        def total_connections(self):
            return self._total

        def user_connections(self, user_id):
            return self._connections.get(user_id, 0)

    return SSEConnectionManager()


@pytest.fixture
def mock_cache_with_ttl():
    """提供带 TTL 和大小限制的测试缓存"""

    class TTLCache:
        def __init__(self, max_size=10, ttl=60):
            self.max_size = max_size
            self.ttl = ttl
            self._cache = {}
            self._access_times = {}
            self._creation_times = {}
            self._access_counter = 0

        def get(self, key):
            if key in self._cache:
                if time.time() - self._creation_times[key] > self.ttl:
                    self.delete(key)
                    return None
                self._access_counter += 1
                self._access_times[key] = self._access_counter
                return self._cache[key]
            return None

        def set(self, key, value):
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()
            self._cache[key] = value
            self._access_counter += 1
            self._access_times[key] = self._access_counter
            self._creation_times[key] = time.time()

        def delete(self, key):
            self._cache.pop(key, None)
            self._access_times.pop(key, None)
            self._creation_times.pop(key, None)

        def _evict_lru(self):
            if not self._access_times:
                return
            lru_key = min(self._access_times, key=self._access_times.get)
            self.delete(lru_key)

        @property
        def size(self):
            return len(self._cache)

    return TTLCache


# ==================== API Testing Fixtures ====================


@pytest.fixture
def mock_collection_session_service():
    """Mock session_service for collection/images API tests.

    Provides a configured mock session with game_loop and player_state.
    """
    with patch("src.api.routers.collection.session_service") as mock_ss:
        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}
        mock_player_state.items = {}
        mock_player_state.landmarks = {}
        mock_player_state.player_name = "TestPlayer"
        mock_player_state.character_settings = {}
        mock_player_state.round_history = []
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session.language = "zh"
        mock_ss.get_or_restore.return_value = mock_session

        yield mock_ss


@pytest.fixture
def mock_image_service():
    """Mock ImageService for image API tests."""
    with patch("src.services.image_service.ImageService") as mock_class:
        mock_service = MagicMock()
        mock_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_collection_service():
    """Mock CollectionService for collection API tests."""
    with patch("src.services.collection_service.CollectionService") as mock_class:
        mock_service = MagicMock()
        mock_class.return_value = mock_service
        yield mock_service


@pytest.fixture
def mock_image_storage():
    """Mock ImageStorageService for image API tests."""
    with patch("src.services.image_storage.ImageStorageService") as mock_class:
        from pathlib import Path

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = True
        mock_storage.get_image_data.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_storage.local_path = Path("/tmp/test_images")
        mock_class.return_value = mock_storage
        yield mock_storage


@pytest.fixture
def sample_collection_response():
    """Sample collection response data for tests."""
    return {
        "characters": [],
        "items": [],
        "landmarks": [],
        "total_characters": 0,
        "total_items": 0,
        "total_landmarks": 0,
    }


@pytest.fixture
def sample_image_model():
    """Sample ImageModel mock for tests."""
    mock_image = MagicMock()
    mock_image.image_id = 1
    mock_image.game_id = 1
    mock_image.image_type = "character"
    mock_image.entity_name = "TestCharacter"
    mock_image.entity_key = "player"
    mock_image.prompt_text = "Test prompt"
    mock_image.version = 1
    mock_image.created_at = None
    return mock_image


# ============================================================
# 叙事风格系统 + 硬性逻辑验证器 Fixtures
# ============================================================


@pytest.fixture
def sample_style_manifest():
    """最小合法的 StyleManifest，用于叙事风格测试。"""
    from src.ai.narrative.style_manifest import (ChapterRules,
                                                 GlobalParameters,
                                                 LanguageConfig,
                                                 PhilosophyConfig,
                                                 StructureConfig,
                                                 StyleManifest,
                                                 TechniqueConfig)

    return StyleManifest(
        style_id="test_style",
        style_name="测试风格",
        version="1.0",
        description="用于单元测试的叙事风格",
        philosophy=PhilosophyConfig(
            narrative_voice="全知视角，冷静克制",
            thematic_core=["命运", "选择", "成长"],
            worldview="现实主义",
        ),
        structure=StructureConfig(
            macro="三幕式结构",
            arc="起承转合",
            chapter_rules=ChapterRules(
                opening_style="环境描写引入",
                closing_style="悬念收尾",
                hook_types=["悬念", "伏笔"],
                avg_length="3000-5000字",
            ),
        ),
        techniques=TechniqueConfig(
            core_techniques=["白描", "意识流"],
            stylistic_devices=["隐喻", "象征"],
            narrative_patterns=["欲扬先抑", "草蛇灰线"],
        ),
        language=LanguageConfig(
            prose_style="简练含蓄",
            dialogue="口语化，符合人物身份",
            rhetoric=["比喻", "排比", "对偶"],
            emotional_expression="克制内敛",
        ),
        global_parameters=GlobalParameters(
            temperature=0.85,
            top_p=1.0,
        ),
    )


@pytest.fixture
def sample_player_state_with_creative():
    """包含创意增强/史诗叙事新字段的 PlayerState。"""
    state = PlayerState()
    state.player_name = "李逍遥"
    state.energy = 80
    state.mood = 70
    state.knowledge = 60
    state.age = 28
    state.week = 12
    state.decision_history = [
        {"week": 10, "choice": "接受师门任务", "effects": {"knowledge": 5}},
        {"week": 11, "choice": "前往洛阳", "effects": {"energy": -10}},
    ]
    state.world_model_data = {
        "character_locations": {
            "李逍遥": {
                "location": "洛阳城",
                "region": "河南",
                "since_week": 11,
                "travel_mode": "visiting",
            },
            "赵灵儿": {
                "location": "苗疆",
                "region": "云南",
                "since_week": 0,
                "travel_mode": "resident",
            },
        },
        "career_records": {},
        "active_commitments": [
            {
                "description": "答应师父三日内取回灵药",
                "parties": ["师父"],
                "deadline_week": 13,
                "status": "pending",
                "created_week": 11,
                "importance": "critical",
            }
        ],
        "causal_chains": [
            {
                "trigger_event": "在洛阳偶遇神秘老者",
                "trigger_week": 11,
                "expected_consequences": ["获得藏宝图线索"],
                "actual_consequences": [],
                "status": "pending",
            }
        ],
        "physical_states": {
            "李逍遥": {"status": "healthy", "conditions": [], "last_updated_week": 12},
        },
        "dynamic_facts": [],
        "character_profiles": {
            "赵灵儿": {
                "identity": "苗疆圣女",
                "appearance": "清丽脱俗，白衣飘飘",
                "personality": "温柔善良，单纯天真",
            }
        },
    }
    return state


@pytest.fixture
def sample_world_model_extended():
    """包含新字段的 WorldModel 扩展数据。"""
    return {
        "character_locations": {
            "主角": {
                "location": "长安城东市",
                "region": "长安",
                "since_week": 5,
                "travel_mode": "resident",
            },
            "王二": {
                "location": "长安城西市",
                "region": "长安",
                "since_week": 3,
                "travel_mode": "resident",
            },
            "张三": {
                "location": "洛阳",
                "region": "洛阳",
                "since_week": 1,
                "travel_mode": "resident",
            },
        },
        "career_records": {
            "主角": {
                "current_job": "书生",
                "employer": "白鹿书院",
                "level": "junior",
                "since_week": 1,
            },
        },
        "active_commitments": [
            {
                "description": "答应周末陪母亲去寺庙进香",
                "parties": ["母亲"],
                "deadline_week": 6,
                "status": "pending",
                "created_week": 5,
                "importance": "critical",
            },
            {
                "description": "与王二约定三日后比武",
                "parties": ["王二"],
                "deadline_week": 7,
                "status": "pending",
                "created_week": 5,
                "importance": "normal",
            },
        ],
        "causal_chains": [
            {
                "trigger_event": "得罪了衙门师爷",
                "trigger_week": 3,
                "expected_consequences": ["师爷报复", "衙门刁难"],
                "actual_consequences": [],
                "status": "pending",
            }
        ],
        "physical_states": {
            "主角": {"status": "healthy", "conditions": [], "last_updated_week": 5},
            "王二": {
                "status": "injured",
                "conditions": ["左臂骨折"],
                "last_updated_week": 4,
            },
        },
        "dynamic_facts": [],
        "character_profiles": {
            "王二": {
                "identity": "铁匠之子",
                "appearance": "魁梧壮硕，面色黝黑",
                "personality": "豪爽直率，重义气",
            },
            "张三": {
                "identity": "洛阳商人",
                "appearance": "瘦削精明，眯眯眼",
                "personality": "精明算计，唯利是图",
            },
        },
    }


@pytest.fixture
def mock_style_loader(tmp_path):
    """基于 tmp_path 的 StyleLoader，用于测试文件扫描。"""
    from src.ai.narrative.style_manifest import StyleLoader

    return StyleLoader(styles_dir=str(tmp_path))


@pytest.fixture
def mock_story_text():
    """标准测试用故事文本(~500字中文)。"""
    return (
        "清晨的阳光透过窗棂洒进屋内，李逍遥缓缓睁开双眼。"
        "昨夜的梦境还残留在脑海中，那个神秘老者的话语仿佛仍在耳畔回响。"
        "他翻身起床，推开木窗，洛阳城的晨景尽收眼底。"
        "街道上已有早起的商贩在摆摊，远处传来寺庙的钟声。\n\n"
        "「今日便是与师父约定的最后期限了。」李逍遥暗自思忖，"
        "心中不免有些焦虑。那株灵药据说生长在城外的悬崖峭壁之上，"
        "寻常人根本无法攀登。\n\n"
        "他简单收拾了行装，腰间别上长剑，推门而出。"
        "客栈掌柜见他一副风尘仆仆的模样，笑着招呼道："
        "「李少侠，这么早就要出发？要不先用些早点？」\n\n"
        "李逍遥摇了摇头：「多谢掌柜好意，在下有要事在身，不便耽搁。」"
        "说罢，他大步流星地走出客栈，向城门方向行去。\n\n"
        "洛阳城的街道在清晨显得格外宁静。偶有几辆牛车咯吱咯吱地驶过，"
        "留下两道深深的车辙。李逍遥穿过东市，经过西市，"
        "终于来到了南城门前。守城的兵丁懒洋洋地打着哈欠，"
        "见他背着包袱佩着剑，也不多盘问，挥手放行。\n\n"
        "出了城门，一条蜿蜒的山路伸向远方。两旁是郁郁葱葱的树林，"
        "春日的微风带着花香扑面而来。然而李逍遥无暇欣赏美景，"
        "他心中只想着如何在日落之前找到那株传说中的灵药。\n\n"
        "就在这时，前方的岔路口出现了一个熟悉的身影——"
        "竟是多日不见的王二！只见他左臂缠着绷带，"
        "靠在路边的大石上歇息。\n\n"
        "李逍遥面临一个选择：是上前与王二攀谈了解情况，"
        "还是为了赶时间继续赶路？毕竟师父的期限就在今日。"
    )
