"""自定义选择持久化集成测试 (Layer 4)

验证 custom_text 在选择后被正确保存到 round_history，
确保 save->load 后不会丢失自定义选择记录。

对应 Bug: #26 (custom_text 未作为强 prompt 约束注入)
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, User
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
    """Session 代理，忽略 close() 调用。"""

    def __init__(self, real_session):
        self._real = real_session

    def __getattr__(self, name):
        return getattr(self._real, name)

    def close(self):
        pass


def _make_state_repo(db_session):
    """Create a StateRepository with mocked SessionLocal and get_db."""
    proxy = _NonClosingSessionProxy(db_session)

    session_patcher = patch(
        "src.database.state_repository.SessionLocal", return_value=proxy
    )
    session_patcher.start()

    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=proxy)
    mock_context.__exit__ = MagicMock(return_value=False)
    db_patcher = patch(
        "src.database.state_repository.get_db", return_value=mock_context
    )
    db_patcher.start()

    repo = StateRepository()
    return repo, session_patcher, db_patcher


class TestCustomChoicePersistence:
    """验证自定义选择文本在保存-读取链路中完整保留。"""

    def test_custom_choice_text_in_round_history(self):
        """自定义选择后 round_history 必须包含 custom_text 和 is_custom 标记。

        ★ Bug #26: custom_text 可能未被正确记录到 round_history，
        导致无法追溯玩家的自定义选择。
        """
        # RoundChoiceProcessor._post_choice_pipeline 在 is_custom=True 时
        # 会向 round_record 添加 is_custom 标记
        player_state = PlayerState(week=0, age=22, current_round=0)

        # 模拟 post-choice pipeline 中的 round_record 构建逻辑
        custom_text = "我决定先观察周围的环境，寻找隐藏的线索"
        round_record = {
            "week": player_state.week,
            "round": player_state.current_round,
            "summary": "玩家做出了自定义选择",
            "event_description": "你进入了一个神秘的房间...",
            "story_continuation": "你仔细观察四周...",
            "choice": custom_text,
            "effects": {"energy": -5, "mood": 10},
            "is_custom": True,
        }
        player_state.round_history.append(round_record)

        state_dict = player_state.to_dict()

        # ★ 核心断言：round_history 中必须保留 custom_text
        history = state_dict.get("round_history", [])
        assert len(history) == 1, "round_history 必须包含一条记录"
        assert (
            history[0].get("choice") == custom_text
        ), "round_history 必须保存玩家的自定义选择文本 (Bug #26)"
        assert (
            history[0].get("is_custom") is True
        ), "自定义选择记录必须标记 is_custom=True"

    def test_custom_choice_preserved_after_save_and_load(self, db_session):
        """save_game_progress + load_saved_game 必须保留自定义选择记录。

        ★ Bug #26: 自定义选择可能在 save->load 后丢失。
        """
        repo, patcher1, patcher2 = _make_state_repo(db_session)

        # 创建用户和游戏
        user = User(private_id="CUSTOM-TEST-1", public_id="CUSTOMT1")
        db_session.add(user)
        db_session.commit()

        custom_text = "我决定把金币分给路边的乞丐"

        game = Game(
            user_id=user.user_id,
            language="zh",
            initial_state={"age": 22},
        )
        db_session.add(game)
        db_session.commit()

        # 构造包含自定义选择记录的玩家状态
        player_state = PlayerState(
            week=1,
            age=23,
            current_round=1,
            round_history=[
                {
                    "week": 0,
                    "round": 0,
                    "summary": "初始故事",
                    "choice": "开始游戏",
                    "effects": {},
                },
                {
                    "week": 0,
                    "round": 1,
                    "summary": "遇到一个乞丐",
                    "event_description": "路边坐着一个衣衫褴褛的老人...",
                    "story_continuation": "老人感激地接过金币...",
                    "choice": custom_text,
                    "effects": {"wealth": -100, "mood": 15},
                    "is_custom": True,
                },
            ],
        )

        # 保存
        result = repo.save_game_progress(game.game_id, player_state)
        assert result is True

        # 加载
        loaded = repo.load_saved_game(game.game_id, user.user_id)
        assert loaded is not None

        # ★ 核心断言：加载后的 round_history 必须保留 custom_text
        loaded_history = loaded.get("round_history", [])
        assert len(loaded_history) == 2

        custom_record = loaded_history[1]
        assert (
            custom_record.get("choice") == custom_text
        ), "加载后的 round_history 必须保留 custom_text (Bug #26)"
        assert (
            custom_record.get("is_custom") is True
        ), "加载后的自定义选择记录必须保留 is_custom=True"
        assert custom_record.get("effects", {}).get("wealth") == -100

        patcher1.stop()
        patcher2.stop()

    def test_standard_choice_not_marked_custom(self):
        """标准选择不应被标记为 is_custom。"""
        player_state = PlayerState(week=0, age=22, current_round=0)

        standard_choice = "向左走"
        round_record = {
            "week": player_state.week,
            "round": player_state.current_round,
            "summary": "标准选择",
            "choice": standard_choice,
            "effects": {"energy": -5},
        }
        player_state.round_history.append(round_record)

        state_dict = player_state.to_dict()
        history = state_dict.get("round_history", [])

        assert history[0].get("choice") == standard_choice
        assert history[0].get("is_custom") is None

    def test_multiple_custom_choices_preserved(self, db_session):
        """多次自定义选择都应被正确保存。"""
        repo, patcher1, patcher2 = _make_state_repo(db_session)

        game = Game(language="zh", initial_state={})
        db_session.add(game)
        db_session.commit()

        custom_texts = [
            "我决定爬上山崖看看风景",
            "我想和那只猫说话",
            "我要在湖里游泳",
        ]

        player_state = PlayerState(week=2, age=22)
        for i, text in enumerate(custom_texts):
            player_state.round_history.append(
                {
                    "week": i // 3,
                    "round": i % 3,
                    "summary": f"自定义选择 {i+1}",
                    "choice": text,
                    "effects": {},
                    "is_custom": True,
                }
            )

        repo.save_game_progress(game.game_id, player_state)
        loaded = repo.load_game_state(game.game_id)

        assert loaded is not None
        loaded_history = loaded.get("round_history", [])
        assert len(loaded_history) == 3
        for i, text in enumerate(custom_texts):
            assert loaded_history[i]["choice"] == text
            assert loaded_history[i].get("is_custom") is True

        patcher1.stop()
        patcher2.stop()

    def test_custom_choice_in_story_history(self):
        """story_history 中也应保留自定义选择标记。"""
        player_state = PlayerState(week=0, age=22, current_round=0)

        custom_text = "我决定用魔法点亮黑暗"
        story_entry = {
            "week": 0,
            "round": 0,
            "story": "你走进了一个黑暗的洞穴...",
            "choice": custom_text,
            "continuation": "魔法光芒照亮了洞穴...",
            "is_custom": True,
        }
        player_state.story_history.append(story_entry)

        state_dict = player_state.to_dict()
        stories = state_dict.get("story_history", [])

        assert len(stories) == 1
        assert stories[0]["choice"] == custom_text
        assert stories[0].get("is_custom") is True

    def test_custom_choice_in_decision_history(self):
        """decision_history 中也应保留自定义选择标记。"""
        player_state = PlayerState(week=0, age=22, current_round=0)

        custom_text = "我要尝试和龙谈判"
        decision_record = {
            "week": 0,
            "round": 0,
            "event": "一条巨龙挡在你面前...",
            "choice": custom_text,
            "effects": {"mood": 20},
            "is_custom": True,
        }
        player_state.decision_history.append(decision_record)

        state_dict = player_state.to_dict()
        decisions = state_dict.get("decision_history", [])

        assert len(decisions) == 1
        assert decisions[0]["choice"] == custom_text
        assert decisions[0].get("is_custom") is True
