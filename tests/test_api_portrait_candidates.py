"""Authenticated candidate batch API contracts."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.routers import images
from src.api.deps import get_current_user, get_session
from src.database.models import Game, User

pytestmark = [pytest.mark.api]

@pytest.fixture
def candidate_client(db_session, monkeypatch):
    user = User(private_id="batch-api", public_id="BATCHAPI")
    db_session.add(user)
    db_session.flush()
    game = Game(user_id=user.user_id, initial_state={})
    db_session.add(game)
    db_session.commit()
    app = FastAPI()
    app.include_router(images.router, prefix="/images")
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user.user_id
    monkeypatch.setattr(images, "schedule_portrait_image_job", lambda job_id: None)
    return TestClient(app), game, app


def test_create_and_recover_batch_state(candidate_client):
    client, game, _ = candidate_client
    response = client.post("/images/character/candidates", json={"game_id": game.game_id, "mode": "initial"})
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert len(data["slots"]) == 3
    assert data["completed_count"] == 0
    assert client.get(f"/images/character/candidates?game_id={game.game_id}").json() == data
    assert client.post(f'/images/character/candidates/{data["batch_id"]}/retry').status_code == 202


def test_wrong_owner_rejected_for_create_read_retry(candidate_client):
    client, game, app = candidate_client
    data = client.post("/images/character/candidates", json={"game_id": game.game_id}).json()
    app.dependency_overrides[get_current_user] = lambda: game.user_id + 10
    assert client.post("/images/character/candidates", json={"game_id": game.game_id}).status_code in (403, 404)
    assert client.get(f"/images/character/candidates?game_id={game.game_id}").status_code in (403, 404)
    assert client.post(f'/images/character/candidates/{data["batch_id"]}/retry').status_code in (403, 404)


def test_legacy_game_has_no_batch_and_no_generation(candidate_client):
    client, game, _ = candidate_client
    assert client.get(f"/images/character/candidates?game_id={game.game_id}").json() is None
