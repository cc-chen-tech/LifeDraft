"""保存持久化完整性集成测试 (Layer 4)

验证 current_event_data 在 save->load 链路中完整保留，
防止刷新后章节重新生成。

对应 Bug: #29/#16 (current_event_data 未持久化 / 选择后被清除)
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, GameState, User
from src.database.state_repository import StateRepository
from src.game.state import PlayerState

pytestmark = pytest.mark.integration


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


class _NonClosingSessionProxy:
    """Session 代理，忽略 close() 调用。

    StateRepository.save_game_progress 在 finally 中调用 db.close()，
    如果直接返回真实 session，后续查询会因 session 已关闭而失败。
    """

    def __init__(self, real_session):
        self._real = real_session

    def __getattr__(self, name):
        return getattr(self._real, name)

    def close(self):
        pass  # 忽略关闭操作


def _make_state_repo(db_session):
    """Create a StateRepository with mocked SessionLocal and get_db."""
    proxy = _NonClosingSessionProxy(db_session)

    # Patch SessionLocal
    session_patcher = patch(
        "src.database.state_repository.SessionLocal", return_value=proxy
    )
    session_patcher.start()

    # Patch get_db to return a context manager yielding the proxy
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=proxy)
    mock_context.__exit__ = MagicMock(return_value=False)
    db_patcher = patch(
        "src.database.state_repository.get_db", return_value=mock_context
    )
    db_patcher.start()

    repo = StateRepository()
    return repo, session_patcher, db_patcher


class TestCurrentEventDataPersistence:
    """验证 current_event_data 在保存-读取链路中完整保留。"""

    def test_player_state_to_dict_includes_current_event_data(self):
        """PlayerState.to_dict() 必须包含完整的 current_event_data。

        ★ Bug #29: current_event_data 未被序列化到字典中，
        导致保存后丢失。
        """
        current_event = {
            "event_description": "你站在十字路口，面前有三条路...",
            "options": [
                {"text": "走左边的路", "effects": {"energy": -5}},
                {"text": "走中间的路", "effects": {"mood": 10}},
                {"text": "走右边的路", "effects": {"wealth": 20}},
            ],
            "story_text": "这是一个关于抉择的故事...",
        }

        player_state = PlayerState(
            week=5,
            age=23,
            current_round=1,
            current_event_data=current_event,
        )

        state_dict = player_state.to_dict()

        assert (
            "current_event_data" in state_dict
        ), "PlayerState.to_dict() 必须包含 current_event_data 字段"
        saved_event = state_dict["current_event_data"]
        assert saved_event is not None, "current_event_data 不应为 None"
        assert (
            saved_event.get("event_description") == current_event["event_description"]
        )
        assert len(saved_event.get("options", [])) == 3

    def test_save_game_progress_preserves_current_event_data(self, db_session):
        """save_game_progress 不得清除 current_event_data。

        ★ Bug #29/#16: save_game_progress 中的"一致性检查"错误地
        将 current_event_data 设为 None，导致刷新后章节重新生成。
        """
        repo, patcher1, patcher2 = _make_state_repo(db_session)

        # 创建游戏记录
        game = Game(language="zh", initial_state={"age": 22})
        db_session.add(game)
        db_session.commit()

        current_event = {
            "event_description": "你发现了一个神秘宝箱...",
            "options": [
                {"text": "打开宝箱", "effects": {"wealth": 100}},
                {"text": "离开", "effects": {"mood": 5}},
            ],
        }

        # 模拟"已选择但下一事件已生成"的状态
        player_state = PlayerState(
            week=2,
            age=23,
            current_round=1,
            round_history=[
                {"week": 0, "round": 0, "summary": "初始故事", "choice": "开始"},
                {"week": 0, "round": 1, "summary": "第一周第一轮", "choice": "向左走"},
                {"week": 0, "round": 2, "summary": "第一周第二轮", "choice": "向右走"},
                {"week": 1, "round": 0, "summary": "第二周", "choice": "接受任务"},
                {
                    "week": 1,
                    "round": 1,
                    "summary": "第二周第一轮",
                    "choice": "探索洞穴",
                },
                {"week": 2, "round": 0, "summary": "第三周", "choice": "与商人交易"},
                {
                    "week": 2,
                    "round": 1,
                    "summary": "第三周第一轮",
                    "choice": "继续前进",
                },
            ],
            current_event_data=current_event,
        )

        # 保存游戏进度
        result = repo.save_game_progress(game.game_id, player_state)
        assert result is True

        # ★ 核心断言：current_event_data 不应被清除
        assert player_state.current_event_data is not None, (
            "save_game_progress 不得清除 current_event_data，"
            "否则刷新后章节会重新生成 (Bug #29/#16)"
        )
        assert (
            player_state.current_event_data.get("event_description")
            == current_event["event_description"]
        )

        # 验证数据库中保存的状态也包含 current_event_data
        saved_state = (
            db_session.query(GameState)
            .filter(GameState.game_id == game.game_id)
            .first()
        )
        assert saved_state is not None
        state_json = saved_state.state_json
        assert (
            "current_event_data" in state_json
        ), "数据库中的 state_json 必须包含 current_event_data"
        assert state_json["current_event_data"] is not None
        assert (
            state_json["current_event_data"].get("event_description")
            == current_event["event_description"]
        )

        patcher1.stop()
        patcher2.stop()

    def test_load_saved_game_restores_current_event_data(self, db_session):
        """load_saved_game 必须完整恢复 current_event_data。

        ★ Bug #29: 加载存档后 current_event_data 为 None，
        前端被迫重新生成章节。
        """
        repo, patcher1, patcher2 = _make_state_repo(db_session)

        # 创建用户和游戏
        user = User(private_id="SAVE-TEST-1", public_id="SAVETST1")
        db_session.add(user)
        db_session.commit()

        current_event = {
            "event_description": "暴风雨即将来临...",
            "options": [
                {"text": "寻找避雨处", "effects": {"energy": 10}},
                {"text": "在雨中前行", "effects": {"mood": -5}},
            ],
            "story_text": "乌云密布，雷声隆隆...",
        }

        game = Game(
            user_id=user.user_id,
            language="zh",
            initial_state={"age": 22, "current_event_data": None},
        )
        db_session.add(game)
        db_session.commit()

        # 保存一个包含 current_event_data 的状态
        player_state = PlayerState(
            week=3,
            age=24,
            current_round=2,
            current_event_data=current_event,
        )
        repo.save_game_progress(game.game_id, player_state)

        # 加载游戏
        loaded = repo.load_saved_game(game.game_id, user.user_id)
        assert loaded is not None

        # ★ 核心断言：加载的状态必须包含 current_event_data
        loaded_event = loaded.get("current_event_data")
        assert loaded_event is not None, (
            "load_saved_game 必须恢复 current_event_data，"
            "否则刷新后会重新生成章节 (Bug #29)"
        )
        assert (
            loaded_event.get("event_description") == current_event["event_description"]
        )
        assert len(loaded_event.get("options", [])) == 2
        assert loaded_event.get("story_text") == current_event["story_text"]

        patcher1.stop()
        patcher2.stop()

    def test_save_preserves_current_event_data_across_multiple_saves(self, db_session):
        """多次保存不应累积清除 current_event_data。"""
        repo, patcher1, patcher2 = _make_state_repo(db_session)

        game = Game(language="zh", initial_state={})
        db_session.add(game)
        db_session.commit()

        event_v1 = {"event_description": "事件版本1", "options": [{"text": "选项A"}]}
        event_v2 = {"event_description": "事件版本2", "options": [{"text": "选项B"}]}

        # 第一次保存
        player_state = PlayerState(week=1, age=22, current_event_data=event_v1)
        repo.save_game_progress(game.game_id, player_state)

        # 第二次保存（模拟游戏推进后）
        player_state.week = 2
        player_state.current_event_data = event_v2
        repo.save_game_progress(game.game_id, player_state)

        # 加载最新状态
        loaded = repo.load_game_state(game.game_id)
        assert loaded is not None
        assert loaded.get("current_event_data") is not None
        assert loaded["current_event_data"]["event_description"] == "事件版本2"

        patcher1.stop()
        patcher2.stop()

    def test_current_event_data_none_is_preserved(self, db_session):
        """current_event_data 为 None 时也应被正确保存（不变成其他值）。"""
        repo, patcher1, patcher2 = _make_state_repo(db_session)

        game = Game(language="zh", initial_state={})
        db_session.add(game)
        db_session.commit()

        player_state = PlayerState(week=0, age=22, current_event_data=None)
        repo.save_game_progress(game.game_id, player_state)

        loaded = repo.load_game_state(game.game_id)
        assert loaded is not None
        # None should be preserved or at least not cause errors
        assert loaded.get("current_event_data") is None

        patcher1.stop()
        patcher2.stop()
