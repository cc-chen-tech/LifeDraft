"""Real DB and HTTP contracts for replaying scene-image SSE events."""

from __future__ import annotations

import json
import os
from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "scene-image-sse-replay-contract")

from src.api.deps import create_token
from src.api.main import app
from src.api.routers.images import (_get_event_key, _publish_scene_image_event,
                                    _scene_image_latest)
from src.database.models import Game, SessionLocal, User, init_db


def _event(
    *,
    game_id: int,
    week: int,
    round_number: int,
    stage: str,
    event_type: str,
    image_url: str | None = None,
    message: str | None = None,
) -> dict[str, object]:
    event: dict[str, object] = {
        "type": event_type,
        "game_id": game_id,
        "week": week,
        "round_number": round_number,
        "stage": stage,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if image_url is not None:
        event["image_url"] = image_url
    if message is not None:
        event["message"] = message
        event["code"] = "provider_timeout"
        event["retryable"] = True
    return event


def test_scene_image_sse_replay_replaces_stale_key_and_isolates_games() -> None:
    """The frontend receives current fields for its game, never stale or foreign events."""
    init_db()
    suffix = uuid4().hex[:12]
    db = SessionLocal()
    owned_event_keys: list[str] = []
    try:
        owner = User(
            private_id=f"scene-sse-owner-{suffix}",
            public_id=f"SSE{suffix[:7]}",
            display_name="Scene SSE Owner",
        )
        db.add(owner)
        db.flush()
        game = Game(user_id=owner.user_id, language="zh", initial_state={})
        db.add(game)
        db.flush()
        owned_game_id = int(game.game_id)
        token = create_token(int(owner.user_id))
        db.commit()

        stale = _event(
            game_id=owned_game_id,
            week=3,
            round_number=2,
            stage="event",
            event_type="scene_image_ready",
            image_url="/api/images/file/stale.png",
        )
        current = _event(
            game_id=owned_game_id,
            week=3,
            round_number=2,
            stage="event",
            event_type="scene_image_ready",
            image_url="/api/images/file/current.png",
        )
        failed = _event(
            game_id=owned_game_id,
            week=3,
            round_number=2,
            stage="result",
            event_type="scene_image_failed",
            message="Image provider timed out",
        )
        foreign = _event(
            game_id=owned_game_id + 1,
            week=3,
            round_number=2,
            stage="event",
            event_type="scene_image_ready",
            image_url="/api/images/file/foreign.png",
        )
        for event in (stale, current, failed, foreign):
            _publish_scene_image_event(event)

        owned_event_keys = [
            _get_event_key(owned_game_id, 3, 2, "event"),
            _get_event_key(owned_game_id, 3, 2, "result"),
        ]
        foreign_key = _get_event_key(owned_game_id + 1, 3, 2, "event")

        response = TestClient(app).get(
            f"/api/images/scene/events/{owned_game_id}?once=true",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        event_lines = (
            line.decode("utf-8") if isinstance(line, bytes) else line
            for line in response.iter_lines()
        )
        events = [
            json.loads(line[6:])
            for line in event_lines
            if line.startswith("data: ")
        ]
        assert {(event["week"], event["round_number"], event["stage"]) for event in events} == {
            (3, 2, "event"),
            (3, 2, "result"),
        }
        assert {event["game_id"] for event in events} == {owned_game_id}

        by_stage = {event["stage"]: event for event in events}
        assert by_stage["event"]["type"] == "scene_image_ready"
        assert by_stage["event"]["image_url"] == "/api/images/file/current.png"
        assert by_stage["result"] == {
            "type": "scene_image_failed",
            "game_id": owned_game_id,
            "week": 3,
            "round_number": 2,
            "stage": "result",
            "timestamp": by_stage["result"]["timestamp"],
            "message": "Image provider timed out",
            "code": "provider_timeout",
            "retryable": True,
        }
        assert foreign_key in _scene_image_latest
    finally:
        for key in owned_event_keys:
            _scene_image_latest.pop(key, None)
        if "foreign_key" in locals():
            _scene_image_latest.pop(foreign_key, None)
        db.rollback()
        if "owned_game_id" in locals():
            db.query(Game).filter(Game.game_id == owned_game_id).delete()
        db.query(User).filter(User.private_id == f"scene-sse-owner-{suffix}").delete()
        db.commit()
        db.close()


def test_scene_image_cache_prunes_expired_and_overflow_entries() -> None:
    """P3-内存修复：过期事件与超出总量上限的最旧事件被淘汰。"""
    import time

    from src.api.routers import images as images_module
    from src.api.routers.images import (
        SCENE_EVENT_CACHE_MAX_ENTRIES,
        SCENE_EVENT_CACHE_TTL,
        _scene_image_published_at,
        _scene_image_state_lock,
    )

    with _scene_image_state_lock:
        images_module._scene_image_latest.clear()
        _scene_image_published_at.clear()
        try:
            expired_key = _get_event_key(99001, 0, 0, "event")
            images_module._scene_image_latest[expired_key] = _event(
                game_id=99001, week=0, round_number=0, stage="event",
                event_type="scene_image_ready",
            )
            _scene_image_published_at[expired_key] = time.time() - SCENE_EVENT_CACHE_TTL - 1

            fresh_key = _get_event_key(99002, 1, 0, "result")
            images_module._scene_image_latest[fresh_key] = _event(
                game_id=99002, week=1, round_number=0, stage="result",
                event_type="scene_image_ready",
            )
            _scene_image_published_at[fresh_key] = time.time()

            images_module._prune_scene_image_cache_locked()
            assert expired_key not in images_module._scene_image_latest
            assert fresh_key in images_module._scene_image_latest

            # 总量上限：超过上限时按最旧淘汰
            original_cap = SCENE_EVENT_CACHE_MAX_ENTRIES
            images_module.SCENE_EVENT_CACHE_MAX_ENTRIES = 3
            try:
                for i in range(5):
                    key = _get_event_key(99100 + i, i, 0, "event")
                    images_module._scene_image_latest[key] = _event(
                        game_id=99100 + i, week=i, round_number=0, stage="event",
                        event_type="scene_image_ready",
                    )
                    _scene_image_published_at[key] = time.time() + i
                images_module._prune_scene_image_cache_locked()
                assert len(images_module._scene_image_latest) <= 3
            finally:
                images_module.SCENE_EVENT_CACHE_MAX_ENTRIES = original_cap
        finally:
            images_module._scene_image_latest.clear()
            _scene_image_published_at.clear()
