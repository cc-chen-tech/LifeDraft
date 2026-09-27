"""Public plaza: authorization, revocation, and live persisted chapters."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.deps import create_token
from src.api.main import app
from src.database.models import Game, GameState, SessionLocal, StoryPublication, User

pytestmark = pytest.mark.integration


@pytest.fixture
def published_story_data():
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        owner = User(private_id=f"plaza-owner-{suffix}", public_id=suffix, display_name="写故事的人")
        other = User(private_id=f"plaza-other-{suffix}", public_id=uuid4().hex[:8], display_name="别人")
        db.add_all([owner, other])
        db.flush()
        state = {
            "player_name": "林晚",
            "private_note": "绝不可公开的备注",
            "day_history": [
                {"day_index": 0, "story_date": "2026-09-01", "event_description": "第一天的故事", "choice": "回家", "transition_text": "天色渐暗", "options": [{"text": "秘密选项"}], "effects_applied": {"wealth": 999}},
                {"day_index": 1, "story_date": "2026-09-02", "event_description": "历史中尚未选择的草稿"},
            ],
            "current_event_data": {"event_description": "还未完成的第二天"},
        }
        game = Game(user_id=owner.user_id, language="zh", initial_state=state, is_public=True)
        db.add(game)
        db.flush()
        db.add(GameState(game_id=game.game_id, week=0, age=23, state_json=state))
        db.commit()
        yield int(owner.user_id), int(other.user_id), int(game.game_id)
    finally:
        for user in db.query(User).filter(User.private_id.in_([f"plaza-owner-{suffix}", f"plaza-other-{suffix}"])).all():
            db.delete(user)
        db.commit()
        db.close()


def _auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(user_id)}"}


def test_anonymous_browse_read_and_live_new_chapters(published_story_data):
    owner_id, _, game_id = published_story_data
    client = TestClient(app)
    assert client.get("/api/plaza").json()["items"] == []
    assert client.get("/api/plaza/mine").status_code == 401
    assert client.put(f"/api/plaza/mine/{game_id}", json={"enabled": True}).status_code == 401

    enabled = client.put(f"/api/plaza/mine/{game_id}", headers=_auth(owner_id), json={"enabled": True})
    assert enabled.status_code == 200
    public_id = enabled.json()["public_id"]
    assert enabled.json()["enabled"] is True

    listed = client.get("/api/plaza").json()
    assert any(item["public_id"] == public_id for item in listed["items"])
    story = client.get(f"/api/plaza/{public_id}")
    assert story.status_code == 200
    assert story.headers["cache-control"] == "no-store"
    assert story.json()["title"] == "林晚"
    assert story.json()["author_name"] == "写故事的人"
    assert [chapter["text"] for chapter in story.json()["chapters"]] == ["第一天的故事\n\n天色渐暗"]
    assert "绝不可公开" not in story.text
    assert "秘密选项" not in story.text
    assert "wealth" not in story.text
    assert "还未完成" not in story.text
    assert "game_id" not in story.json()
    assert "user_id" not in story.json()

    db = SessionLocal()
    try:
        previous = db.query(GameState).filter(GameState.game_id == game_id).order_by(GameState.state_id.desc()).first()
        next_state = dict(previous.state_json)
        next_state["day_history"] = [
            *next_state["day_history"],
            {"day_index": 1, "story_date": "2026-09-02", "event_description": "第二天已完成", "choice": "出发"},
        ]
        db.add(GameState(game_id=game_id, week=0, age=23, state_json=next_state))
        db.commit()
    finally:
        db.close()

    assert [chapter["text"] for chapter in client.get(f"/api/plaza/{public_id}").json()["chapters"]] == ["第一天的故事\n\n天色渐暗", "第二天已完成"]


def test_only_owner_can_switch_and_off_revokes_existing_link(published_story_data):
    owner_id, other_id, game_id = published_story_data
    client = TestClient(app)
    assert client.put(f"/api/plaza/mine/{game_id}", headers=_auth(other_id), json={"enabled": True}).status_code == 404
    assert client.get("/api/plaza/mine", headers=_auth(other_id)).json() == []

    enabled = client.put(f"/api/plaza/mine/{game_id}", headers=_auth(owner_id), json={"enabled": True}).json()
    public_id = enabled["public_id"]
    assert client.get(f"/api/plaza/{public_id}").status_code == 200
    assert client.put(f"/api/plaza/mine/{game_id}", headers=_auth(owner_id), json={"enabled": False}).status_code == 200
    assert client.get(f"/api/plaza/{public_id}").status_code == 404
    assert all(item["public_id"] != public_id for item in client.get("/api/plaza").json()["items"])
    reenabled = client.put(f"/api/plaza/mine/{game_id}", headers=_auth(owner_id), json={"enabled": True}).json()
    assert reenabled["public_id"] == public_id
    assert client.get(f"/api/plaza/{public_id}").status_code == 200


def test_unfinished_story_cannot_be_published_and_search_uses_public_fields(published_story_data):
    owner_id, _, game_id = published_story_data
    client = TestClient(app)
    db = SessionLocal()
    try:
        game = db.query(Game).filter(Game.game_id == game_id).one()
        empty = {"player_name": "未开始", "day_history": [], "current_event_data": {"event_description": "仅草稿"}}
        db.add(GameState(game_id=game_id, week=0, age=23, state_json=empty))
        db.commit()
        assert client.put(f"/api/plaza/mine/{game_id}", headers=_auth(owner_id), json={"enabled": True}).status_code == 409

        legacy = {"player_name": "旧故事", "round_history": [{"week": 0, "round": 0, "event_description": "旧章节", "story_continuation": "旧续篇", "choice": "继续"}]}
        db.add(GameState(game_id=game_id, week=0, age=23, state_json=legacy))
        db.commit()
        public_id = client.put(f"/api/plaza/mine/{game_id}", headers=_auth(owner_id), json={"enabled": True}).json()["public_id"]
        assert client.get(f"/api/plaza/{public_id}").json()["chapters"][0]["text"] == "旧章节\n\n旧续篇"
        assert client.get("/api/plaza", params={"q": "旧故事"}).json()["items"][0]["public_id"] == public_id
        assert client.get("/api/plaza", params={"q": "绝不可公开"}).json()["items"] == []
    finally:
        db.close()


def test_list_skips_rewound_empty_stories_without_losing_pagination(published_story_data):
    owner_id, _, game_id = published_story_data
    client = TestClient(app)
    public_id = client.put(f"/api/plaza/mine/{game_id}", headers=_auth(owner_id), json={"enabled": True}).json()["public_id"]
    db = SessionLocal()
    try:
        empty = {"player_name": "回溯后还没有章节", "day_history": []}
        newer = Game(user_id=owner_id, language="zh", initial_state=empty)
        db.add(newer)
        db.flush()
        db.add(GameState(game_id=newer.game_id, week=0, age=23, state_json=empty))
        db.add(StoryPublication(game_id=newer.game_id, public_id=uuid4().hex, enabled=True))
        db.commit()
        page = client.get("/api/plaza", params={"limit": 1}).json()
        assert [item["public_id"] for item in page["items"]] == [public_id]
        assert page["has_more"] is False
        assert page["next_offset"] == 2
    finally:
        db.close()
