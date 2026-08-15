"""Provider-free contracts for image router local delivery boundaries."""

import json
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.routers.images import (
    _get_event_key,
    _publish_scene_image_event,
    _scene_failure_detail,
    _scene_image_latest,
    get_image_file,
    scene_image_events,
    verify_game_ownership,
    verify_image_ownership,
)
from src.database.models import Game, User
from src.database.models import Image as ImageModel
from src.services.image_storage import ImageStorageService


def _owner_game(db_session) -> tuple[User, Game]:
    owner = User(
        private_id="image-delivery-owner",
        public_id="imgdly01",
        display_name="Delivery Owner",
    )
    db_session.add(owner)
    db_session.flush()
    game = Game(user_id=owner.user_id, language="zh", initial_state={"player_name": "林岚"})
    db_session.add(game)
    db_session.commit()
    return owner, game


def _request() -> Request:
    return Request({"type": "http", "headers": [], "method": "GET", "path": "/"})


@pytest.mark.asyncio
async def test_local_image_file_returns_stored_bytes_with_webp_cache_metadata() -> None:
    storage = ImageStorageService()
    game_id = 780_001
    image_type = "contract-local-delivery"
    filename = "scene.webp"
    expected_bytes = b"RIFF-contract-webp-bytes"
    image_path = storage.local_path / str(game_id) / image_type / filename
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(expected_bytes)

    try:
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game
        response = await get_image_file(game_id, image_type, filename, db=mock_db, user=1)

        assert response.body == expected_bytes
        assert response.media_type == "image/webp"
        assert response.headers["cache-control"] == "public, max-age=3600"
        assert "expires" in response.headers
    finally:
        image_path.unlink(missing_ok=True)
        for directory in (image_path.parent, image_path.parent.parent):
            try:
                directory.rmdir()
            except OSError:
                pass


@pytest.mark.asyncio
async def test_owned_scene_event_stream_preserves_cached_payload(db_session) -> None:
    owner, game = _owner_game(db_session)
    event = {
        "type": "scene_image_ready",
        "game_id": int(game.game_id),
        "week": 5,
        "round_number": 3,
        "stage": "result",
        "image_url": "/api/images/file/scene.webp",
    }
    event_key = _get_event_key(int(game.game_id), 5, 3, "result")
    _publish_scene_image_event(event)

    try:
        response = await scene_image_events(
            _request(), int(game.game_id), once=True, db=db_session, user=int(owner.user_id)
        )
        chunk = await response.body_iterator.__anext__()
        raw_event = chunk.decode() if isinstance(chunk, bytes) else chunk
        payload = json.loads(raw_event.removeprefix("data: ").strip())

        assert response.media_type == "text/event-stream"
        assert payload == event
    finally:
        _scene_image_latest.pop(event_key, None)


def test_image_ownership_rejects_missing_and_foreign_resources(db_session) -> None:
    owner, game = _owner_game(db_session)
    other = User(
        private_id="image-delivery-other",
        public_id="imgdly02",
        display_name="Other Owner",
    )
    image = ImageModel(
        game_id=game.game_id,
        image_type="character",
        entity_name="林岚",
        prompt_text="portrait",
        storage_path="contracts/linlan.webp",
        storage_type="local",
    )
    db_session.add_all([other, image])
    db_session.commit()

    assert verify_image_ownership(db_session, int(image.image_id), int(owner.user_id)) == image
    with pytest.raises(HTTPException) as missing_game:
        verify_game_ownership(db_session, 987_654, int(owner.user_id))
    with pytest.raises(HTTPException) as foreign_game:
        verify_game_ownership(db_session, int(game.game_id), int(other.user_id))
    with pytest.raises(HTTPException) as missing_image:
        verify_image_ownership(db_session, 987_654, int(owner.user_id))

    assert missing_game.value.status_code == 404
    assert foreign_game.value.status_code == 404
    assert missing_image.value.status_code == 404


def test_scene_failure_detail_exposes_only_safe_public_fields() -> None:
    detailed = _scene_failure_detail(
        {
            "code": "provider_timeout",
            "message": "稍后重试",
            "retryable": False,
            "provider_trace_id": "trace-image-123",
            "internal_error": "do-not-leak",
        }
    )
    defaulted = _scene_failure_detail({})

    assert detailed == {
        "code": "provider_timeout",
        "message": "稍后重试",
        "retryable": False,
        "provider_trace_id": "trace-image-123",
    }
    assert defaulted == {
        "code": "image_generation_failed",
        "message": "场景插画生成失败，请稍后重试",
        "retryable": True,
    }
