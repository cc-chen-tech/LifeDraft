"""Async portrait job API contracts."""

import asyncio

import pytest
from fastapi import HTTPException

from src.api.routers import images
from src.api.schemas import GenerateImageRequest, RegenerateFreshImageRequest, RegenerateImageRequest
from src.database.models import Game, Image, User

pytestmark = [pytest.mark.api]



def _request(game_id: int) -> GenerateImageRequest:
    return GenerateImageRequest(
        game_id=game_id,
        image_type="character",
        entity_name="林见微",
        description="28岁，现代都市",
        entity_key="player_main",
        era="现代",
    )


def _game(db_session):
    user = User(private_id="portrait-api-user", public_id="PJOB0002")
    db_session.add(user)
    db_session.flush()
    game = Game(user_id=user.user_id, initial_state={})
    db_session.add(game)
    db_session.commit()
    return user, game


def test_enqueue_endpoint_returns_accepted_and_reuses_active_job(db_session, monkeypatch):
    user, game = _game(db_session)
    scheduled_job_ids: list[int] = []
    monkeypatch.setattr(images, "schedule_portrait_image_job", scheduled_job_ids.append)

    first = asyncio.run(images.enqueue_character_portrait(_request(game.game_id), db_session, user.user_id))
    second = asyncio.run(images.enqueue_character_portrait(_request(game.game_id), db_session, user.user_id))

    assert first.status == "queued"
    assert second.job_id == first.job_id
    assert scheduled_job_ids == [first.job_id, first.job_id]


def test_latest_endpoint_returns_safe_failed_job_for_its_owner(db_session, monkeypatch):
    user, game = _game(db_session)
    monkeypatch.setattr(images, "schedule_portrait_image_job", lambda _job_id: None)
    queued = asyncio.run(images.enqueue_character_portrait(_request(game.game_id), db_session, user.user_id))
    job = db_session.get(images.PortraitImageGenerationJob, queued.job_id)
    job.status = "failed"
    job.error_code = "minimax_capacity"
    job.error_message = "图片生成额度暂时不可用，请稍后再试"
    db_session.commit()

    latest = asyncio.run(images.get_latest_character_portrait_job(game.game_id, db_session, user.user_id))

    assert latest.job_id == queued.job_id
    assert latest.status == "failed"
    assert latest.error_code == "minimax_capacity"
    assert latest.error_message == "图片生成额度暂时不可用，请稍后再试"


def test_enqueue_endpoint_rejects_non_player_main_requests(db_session):
    user, game = _game(db_session)
    request = _request(game.game_id)
    request.entity_key = "npc_1"

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(images.enqueue_character_portrait(request, db_session, user.user_id))

    assert exc_info.value.status_code == 422


def test_job_lookup_does_not_expose_another_users_portrait_job(db_session, monkeypatch):
    user, game = _game(db_session)
    monkeypatch.setattr(images, "schedule_portrait_image_job", lambda _job_id: None)
    queued = asyncio.run(images.enqueue_character_portrait(_request(game.game_id), db_session, user.user_id))
    other_user = User(private_id="portrait-api-other", public_id="PJOB0003")
    db_session.add(other_user)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            images.get_character_portrait_job(queued.job_id, db_session, other_user.user_id)
        )

    assert exc_info.value.status_code == 404


def test_regeneration_endpoint_queues_an_owned_main_portrait(db_session, monkeypatch):
    user, game = _game(db_session)
    source = Image(
        game_id=game.game_id,
        image_type="character",
        entity_name="林见微",
        entity_key="player_main",
        prompt_text="portrait",
        storage_path="portrait.png",
        is_active=True,
    )
    db_session.add(source)
    db_session.commit()
    scheduled: list[int] = []
    monkeypatch.setattr(images, "schedule_portrait_image_job", scheduled.append)

    first = asyncio.run(images.enqueue_character_regeneration(
        RegenerateImageRequest(image_id=source.image_id, feedback="短发", new_description="29岁古装人物"),
        db_session,
        user.user_id,
    ))
    second = asyncio.run(images.enqueue_character_regeneration(
        RegenerateImageRequest(image_id=source.image_id, feedback="短发", new_description="29岁古装人物"),
        db_session,
        user.user_id,
    ))

    assert first.status == "queued"
    assert second.job_id == first.job_id
    assert scheduled == [first.job_id, first.job_id]
    queued = db_session.get(images.PortraitImageGenerationJob, first.job_id)
    assert queued.request_json["source_image_id"] == source.image_id
    assert queued.request_json["feedback"] == "短发"
    assert queued.request_json["new_description"] == "29岁古装人物"
    assert queued.request_json["operation"] == "regenerate"


def test_regeneration_endpoint_rejects_other_users_image(db_session):
    user, game = _game(db_session)
    source = Image(
        game_id=game.game_id,
        image_type="character",
        entity_name="林见微",
        entity_key="player_main",
        prompt_text="portrait",
        storage_path="portrait.png",
        is_active=True,
    )
    db_session.add(source)
    other = User(private_id="portrait-api-other-regen", public_id="PJOB0004")
    db_session.add(other)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(images.enqueue_character_regeneration(
            RegenerateImageRequest(image_id=source.image_id, feedback="短发"),
            db_session,
            other.user_id,
        ))
    assert exc_info.value.status_code == 404


def test_fresh_regeneration_endpoint_queues_without_running_image_provider(db_session, monkeypatch):
    user, game = _game(db_session)
    source = Image(
        game_id=game.game_id,
        image_type="character",
        entity_name="林见微",
        entity_key="player_main",
        prompt_text="portrait",
        storage_path="portrait.png",
        is_active=True,
    )
    db_session.add(source)
    db_session.commit()
    monkeypatch.setattr(images, "schedule_portrait_image_job", lambda _job_id: None)

    queued = asyncio.run(images.enqueue_character_fresh_regeneration(
        RegenerateFreshImageRequest(image_id=source.image_id, use_deepseek_prompt=False),
        db_session,
        user.user_id,
    ))

    assert queued.status == "queued"
    stored = db_session.get(images.PortraitImageGenerationJob, queued.job_id)
    assert stored.request_json["operation"] == "regenerate_fresh"
    assert stored.request_json["source_image_id"] == source.image_id
    assert stored.request_json["use_deepseek_prompt"] is False


def test_regeneration_endpoint_rejects_npc_portrait(db_session):
    user, game = _game(db_session)
    source = Image(
        game_id=game.game_id,
        image_type="character",
        entity_name="路人",
        entity_key="npc_1",
        prompt_text="portrait",
        storage_path="npc.png",
        is_active=True,
    )
    db_session.add(source)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(images.enqueue_character_regeneration(
            RegenerateImageRequest(image_id=source.image_id, feedback="短发"),
            db_session,
            user.user_id,
        ))
    assert exc_info.value.status_code == 422
