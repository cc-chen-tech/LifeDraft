"""HTTP contracts for durable, owned draft-origin replacement."""

from copy import deepcopy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.deps import get_current_user
from src.api.main import app
from src.api.routers import games as games_router
from src.database.models import Base, Game, GameState, User

pytestmark = [pytest.mark.api]



def _origin(revision=1, start_date="0960-01-01", age=20):
    return {
        "revision": revision,
        "start_date": start_date,
        "starting_age": age,
        "era_description": "北宋初年的州城",
        "life_stage_description": "初入成年的人生阶段",
        "world_context": "驿路与坊市连接地方社会",
    }


def _state():
    return {
        "player_name": "阿衡",
        "life_vision": "建立长久事业",
        "age": 20,
        "week": 0,
        "timeline_version": 2,
        "timeline": {"version": 2, "start_date": "0960-01-01", "day_index": 0},
        "day_history": [],
        "character_settings": {
            "story_origin": _origin(),
            "start_date": "0960-01-01",
            "era": {"year": 960},
            "age": {"age": 20, "birth_year": 940},
            "gender": {"gender": "female"},
            "world": {"description": "旧世界"},
        },
    }


class _RealStateAdapter:
    """Small adapter over the real SQLAlchemy test session used by the route."""

    def __init__(self, session):
        self.session = session

    def load_saved_game(self, game_id, user_id):
        game = (
            self.session.query(Game)
            .filter(Game.game_id == game_id, Game.user_id == user_id)
            .one_or_none()
        )
        if game is None:
            return None
        latest = (
            self.session.query(GameState)
            .filter(GameState.game_id == game_id)
            .order_by(GameState.state_id.desc())
            .first()
        )
        value = deepcopy(latest.state_json if latest else game.initial_state)
        value["_game_id"] = game_id
        return value

    def save_game_progress(self, game_id, player_state):
        self.session.add(
            GameState(
                game_id=game_id,
                week=player_state.week,
                age=player_state.age,
                state_json=player_state.to_dict(),
            )
        )
        self.session.commit()
        return True


@pytest.fixture
def owned_draft(client, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine, expire_on_commit=False)()
    user = User(private_id="ORIGIN-API", public_id="ORGAPI01")
    db_session.add(user)
    db_session.commit()
    game = Game(user_id=user.user_id, language="zh", initial_state=_state())
    db_session.add(game)
    db_session.commit()
    adapter = _RealStateAdapter(db_session)
    monkeypatch.setattr(games_router, "get_db", lambda: adapter)
    user_id = int(user.user_id)
    app.dependency_overrides[get_current_user] = lambda: user_id
    try:
        yield client, adapter, int(game.game_id), user_id
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        db_session.close()
        engine.dispose()


def test_patch_story_origin_persists_before_returning_success(owned_draft):
    client, adapter, game_id, user_id = owned_draft
    candidate = {
        **_origin(revision=99, start_date="2026-08-13", age=28),
        "era_description": "2020年代中期的现代都市",
        "life_stage_description": "职业发展逐渐进入稳定探索期",
        "world_context": "AI工具与数字内容行业快速变化",
    }

    response = client.patch(
        f"/api/games/{game_id}/story-origin",
        json={"expected_revision": 1, "story_origin": candidate},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["story_origin"]["revision"] == 2
    assert body["timeline"]["current_date"] == "2026-08-13"
    persisted = adapter.load_saved_game(game_id, user_id)
    assert persisted["character_settings"]["story_origin"] == body["story_origin"]
    assert persisted["timeline"] == body["timeline"]


def test_patch_story_origin_returns_structured_revision_conflict(owned_draft):
    client, _, game_id, _ = owned_draft

    response = client.patch(
        f"/api/games/{game_id}/story-origin",
        json={"expected_revision": 8, "story_origin": _origin()},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "story_origin_revision_conflict"}


def test_patch_story_origin_returns_structured_lock(owned_draft):
    client, adapter, game_id, user_id = owned_draft
    played = adapter.load_saved_game(game_id, user_id)
    played["current_event_data"] = {"event_id": "day:0", "revision": 1}
    adapter.save_game_progress(game_id, games_router.PlayerState.from_dict(played))

    response = client.patch(
        f"/api/games/{game_id}/story-origin",
        json={"expected_revision": 1, "story_origin": _origin()},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "story_origin_locked"}
