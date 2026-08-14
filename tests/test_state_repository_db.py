"""StateRepository DB integration tests.

Uses real SQLite in-memory database via monkeypatched SessionLocal.
No unittest.mock usage.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Game, SessionLocal, User
from src.database.state_repository import StateRepository
from src.game.state import PlayerState


@pytest.fixture(autouse=True)
def patch_session_local():
    """Replace global SessionLocal with in-memory test database."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    original = SessionLocal
    import src.database.models as models
    import src.database.state_repository as repo_module

    models.SessionLocal = TestSessionLocal
    repo_module.SessionLocal = TestSessionLocal
    yield engine
    models.SessionLocal = original
    repo_module.SessionLocal = original


@pytest.fixture
def db(patch_session_local):
    """Create a fresh test session using the shared engine."""
    engine = patch_session_local
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_user(db):
    user = User(private_id="STATE-USER-1", public_id="STATEU01")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def sample_game(db, sample_user):
    game = Game(user_id=sample_user.user_id, language="zh")
    db.add(game)
    db.commit()
    return game


@pytest.fixture
def sample_player_state():
    return PlayerState(week=5, age=25, current_round=2, player_name="TestPlayer")


class TestStateRepositoryDB:
    """DB integration tests for StateRepository."""

    def test_save_state(self, sample_game, sample_player_state):
        """save_state should persist a state snapshot."""
        repo = StateRepository()
        repo.save_state(sample_game.game_id, sample_player_state)

        states = repo.load_game_state(sample_game.game_id)
        assert states is not None
        assert states.get("player_name") == "TestPlayer"

    def test_load_game_state_returns_latest(self, sample_game, sample_player_state):
        """load_game_state should return the latest state."""
        repo = StateRepository()

        state1 = PlayerState(week=1, age=22, player_name="Old")
        state2 = PlayerState(week=5, age=25, player_name="New")
        repo.save_state(sample_game.game_id, state1)
        repo.save_state(sample_game.game_id, state2)

        latest = repo.load_game_state(sample_game.game_id)
        assert latest.get("player_name") == "New"

    def test_load_game_state_not_found(self):
        """load_game_state for non-existent game should return None."""
        repo = StateRepository()
        result = repo.load_game_state(99999)
        assert result is None

    def test_save_game_progress(self, sample_game, sample_player_state):
        """save_game_progress should save and return True."""
        repo = StateRepository()
        result = repo.save_game_progress(sample_game.game_id, sample_player_state)
        assert result is True

    def test_save_game_progress_sanitizes_structured_financial_world_authority(
        self, sample_game
    ):
        repo = StateRepository()
        state = PlayerState(
            player_name="林岚",
            world_model_data={
                "career_records": {
                    "林岚": {"current_job": "月薪8000元的产品经理"},
                    "周宁": {"current_job": "经济援助项目协调员"},
                },
                "active_commitments": [
                    {"description": "承诺偿还5000元债务"},
                    {"description": "在经济压力下互相支持"},
                ],
                "causal_chains": [
                    {"cause": "付款2000元", "expected_consequence": "账户余额改善"},
                    {"cause": "家庭消费压力加剧", "expected_consequence": "生活选择更加谨慎"},
                ],
            },
        )

        assert repo.save_game_progress(sample_game.game_id, state) is True
        saved = str(repo.load_game_state(sample_game.game_id)["world_model_data"])

        assert "经济援助项目协调员" in saved
        assert "家庭消费压力加剧" in saved
        for forbidden in ("8000", "5000", "2000", "账户余额"):
            assert forbidden not in saved

    def test_save_game_progress_none_state(self, sample_game):
        """save_game_progress with None should return False."""
        repo = StateRepository()
        result = repo.save_game_progress(sample_game.game_id, None)
        assert result is False

    def test_load_saved_game(self, sample_game, sample_user, sample_player_state):
        """load_saved_game should return state with game_id."""
        repo = StateRepository()
        repo.save_state(sample_game.game_id, sample_player_state)

        state = repo.load_saved_game(sample_game.game_id, sample_user.user_id)
        assert state is not None
        assert state.get("_game_id") == sample_game.game_id

    def test_load_saved_game_wrong_user(self, sample_game):
        """load_saved_game with wrong user should return None."""
        repo = StateRepository()
        state = repo.load_saved_game(sample_game.game_id, 99999)
        assert state is None

    def test_load_saved_game_injects_constraint_level(self, sample_game, sample_user):
        """load_saved_game should inject constraint_level."""
        repo = StateRepository()
        state = PlayerState(week=1, age=22)
        repo.save_state(sample_game.game_id, state)

        loaded = repo.load_saved_game(sample_game.game_id, sample_user.user_id)
        assert "constraint_level" in loaded

    def test_save_game_progress_prunes_old_auto_snapshots_but_keeps_save_points(
        self, sample_game, sample_user, db
    ):
        """P3-存储优化：超出保留上限的旧自动快照被清理，手动存档点永不删除。"""
        from src.database.models import GameState

        repo = StateRepository()
        repo.AUTO_SNAPSHOT_KEEP_COUNT = 3

        # 先造一个手动存档点
        save_point = GameState(
            game_id=sample_game.game_id,
            week=0,
            age=22,
            state_json={"player_name": "SavePoint"},
            is_save_point=True,
            save_name="我的存档",
        )
        db.add(save_point)
        db.commit()

        for i in range(8):
            state = PlayerState(week=i, age=22, player_name=f"Player{i}")
            assert repo.save_game_progress(sample_game.game_id, state) is True

        db.expire_all()
        auto_states = (
            db.query(GameState)
            .filter(
                GameState.game_id == sample_game.game_id,
                GameState.is_save_point.is_(False),
            )
            .all()
        )
        # 只保留最近 3 个自动快照
        assert len(auto_states) == 3
        assert sorted(s.week for s in auto_states) == [5, 6, 7]

        save_points = (
            db.query(GameState)
            .filter(
                GameState.game_id == sample_game.game_id,
                GameState.is_save_point.is_(True),
            )
            .all()
        )
        assert len(save_points) == 1

        # 最新快照仍可正常加载
        loaded = repo.load_saved_game(sample_game.game_id, sample_user.user_id)
        assert loaded is not None
        assert loaded["player_name"] == "Player7"
