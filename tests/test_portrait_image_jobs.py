"""Durable main-character portrait generation job contracts."""

from unittest.mock import MagicMock

from sqlalchemy.orm import sessionmaker

import src.services.portrait_image_jobs as portrait_jobs
from src.database.models import Game, GameState, Image, PortraitImageGenerationJob, User
from src.services.portrait_image_jobs import (
    PortraitImageJobService,
    recover_pending_portrait_image_jobs,
    requeue_interrupted_portrait_jobs,
    run_portrait_image_job,
)
import pytest

pytestmark = [pytest.mark.unit]



def _request(game_id: int) -> dict:
    return {
        "game_id": game_id,
        "image_type": "character",
        "entity_name": "林见微",
        "description": "28岁，现代都市",
        "entity_key": "player_main",
        "era": "现代",
        "extra_context": {"playerName": "林见微"},
        "feedback": None,
    }


def _game(db_session):
    user = User(private_id="portrait-job-user", public_id="PJOB0001")
    db_session.add(user)
    db_session.flush()
    game = Game(user_id=user.user_id, initial_state={})
    db_session.add(game)
    db_session.commit()
    return user, game


def test_enqueue_reuses_the_only_active_main_character_job(db_session):
    user, game = _game(db_session)
    service = PortraitImageJobService(db_session)

    first, reused_first = service.enqueue(user.user_id, _request(game.game_id))
    second, reused_second = service.enqueue(user.user_id, _request(game.game_id))

    assert reused_first is False
    assert reused_second is True
    assert second.job_id == first.job_id
    assert (
        db_session.query(PortraitImageGenerationJob)
        .filter(PortraitImageGenerationJob.game_id == game.game_id)
        .count()
        == 1
    )
    assert first.status == "queued"
    assert first.entity_key == "player_main"
    assert first.request_json == _request(game.game_id)


def test_requeue_interrupted_jobs_preserves_the_original_request(db_session):
    user, game = _game(db_session)
    job, _ = PortraitImageJobService(db_session).enqueue(user.user_id, _request(game.game_id))
    job.status = "running"
    job.attempt_count = 1
    db_session.commit()

    recovered_ids = requeue_interrupted_portrait_jobs(db_session)
    db_session.refresh(job)

    assert recovered_ids == [job.job_id]
    assert job.status == "queued"
    assert job.attempt_count == 1
    assert job.request_json == _request(game.game_id)


def test_startup_requeues_running_jobs_and_reschedules_all_queued_work(temp_db_file, monkeypatch):
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    setup_db = Session()
    user, game = _game(setup_db)
    running, _ = PortraitImageJobService(setup_db).enqueue(user.user_id, _request(game.game_id))
    queued_game = Game(user_id=user.user_id, initial_state={})
    setup_db.add(queued_game)
    setup_db.commit()
    queued, _ = PortraitImageJobService(setup_db).enqueue(
        user.user_id,
        _request(queued_game.game_id),
    )
    running.status = "running"
    queued.status = "queued"
    setup_db.commit()
    running_id, queued_id = running.job_id, queued.job_id
    setup_db.close()

    scheduled: list[int] = []
    monkeypatch.setattr(portrait_jobs, "SessionLocal", Session)
    monkeypatch.setattr(portrait_jobs, "schedule_portrait_image_job", scheduled.append)

    recovered = recover_pending_portrait_image_jobs()

    assert sorted(recovered) == sorted([running_id, queued_id])
    assert sorted(scheduled) == sorted([running_id, queued_id])


def test_worker_persists_image_result_with_an_independent_session(temp_db_file):
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    setup_db = Session()
    user, game = _game(setup_db)
    job, _ = PortraitImageJobService(setup_db).enqueue(user.user_id, _request(game.game_id))
    job_id = job.job_id
    setup_db.close()

    generated_image = MagicMock()
    generated_image.image_id = 41

    class FakeImageService:
        def __init__(self, _db):
            pass

        def generate_character_image(self, **_kwargs):
            return [generated_image]

    run_portrait_image_job(job_id, session_factory=Session, image_service_factory=FakeImageService)

    verify_db = Session()
    completed = verify_db.get(PortraitImageGenerationJob, job_id)
    assert completed.status == "succeeded"
    assert completed.image_id == 41
    assert completed.attempt_count == 1
    assert completed.error_code is None
    verify_db.close()


@pytest.mark.parametrize("operation", ["regenerate", "regenerate_fresh"])
def test_worker_runs_portrait_regeneration_in_background(temp_db_file, operation):
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    setup_db = Session()
    user, game = _game(setup_db)
    source = Image(
        game_id=game.game_id, image_type="character", entity_name="林见微",
        entity_key="player_main", prompt_text="old", storage_path="old.png", is_active=True,
    )
    setup_db.add(source)
    setup_db.commit()
    game_id = game.game_id
    source_id = source.image_id
    request = {
        "game_id": game.game_id,
        "entity_key": "player_main",
        "operation": operation,
        "source_image_id": source_id,
        "feedback": "短发",
        "new_description": "29岁古装人物",
        "use_deepseek_prompt": False,
    }
    job, _ = PortraitImageJobService(setup_db).enqueue(user.user_id, request)
    job_id = job.job_id
    setup_db.close()

    deleted_paths = []

    class FakeImageService:
        def __init__(self, db):
            self.db = db

        def candidate(self):
            image = Image(
                game_id=game_id, image_type="character", entity_name="林见微",
                entity_key="player_main", prompt_text="new", storage_path="new.png",
                is_active=False,
            )
            self.db.add(image)
            self.db.commit()
            return [image]

        def regenerate_image(self, *, image_id, feedback, new_description, defer_activation):
            assert operation == "regenerate"
            assert (image_id, feedback, new_description) == (source_id, "短发", "29岁古装人物")
            assert defer_activation is True
            return self.candidate()

        def regenerate_fresh_image(self, *, image_id, use_deepseek_prompt, defer_activation):
            assert operation == "regenerate_fresh"
            assert image_id == source_id
            assert use_deepseek_prompt is False
            assert defer_activation is True
            return self.candidate()

        def delete_image_files(self, images):
            deleted_paths.extend(image.storage_path for image in images)

    run_portrait_image_job(job_id, session_factory=Session, image_service_factory=FakeImageService)

    verify_db = Session()
    completed = verify_db.get(PortraitImageGenerationJob, job_id)
    assert completed.status == "succeeded"
    assert verify_db.get(Image, source_id).is_active is False
    assert verify_db.get(Image, completed.image_id).is_active is True
    assert deleted_paths == ["old.png"]
    verify_db.close()


@pytest.mark.parametrize("initial_revision", [None, 1])
def test_superseded_regeneration_does_not_replace_a_newer_portrait(temp_db_file, initial_revision):
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    setup_db = Session()
    user, game = _game(setup_db)
    if initial_revision is not None:
        game.initial_state = {"character_settings": {"story_origin": {"revision": initial_revision}}}
    source = Image(
        game_id=game.game_id, image_type="character", entity_name="林见微",
        entity_key="player_main", prompt_text="old", storage_path="old.png", is_active=True,
    )
    setup_db.add(source)
    setup_db.commit()
    game_id, source_id = game.game_id, source.image_id
    job, _ = PortraitImageJobService(setup_db).enqueue(user.user_id, {
        "game_id": game_id, "entity_key": "player_main", "operation": "regenerate",
        "source_image_id": source_id,
    })
    job_id = job.job_id
    setup_db.close()
    deleted_paths = []
    image_ids = {}

    class FakeImageService:
        def __init__(self, db):
            self.db = db

        def regenerate_image(self, *, image_id, feedback, new_description, defer_activation):
            assert image_id == source_id
            assert defer_activation is True
            candidate = Image(
                game_id=game_id, image_type="character", entity_name="林见微",
                entity_key="player_main", prompt_text="stale", storage_path="stale.png",
                is_active=False,
            )
            newer = Image(
                game_id=game_id, image_type="character", entity_name="林见微",
                entity_key="player_main", prompt_text="current", storage_path="current.png",
                is_active=True,
            )
            self.db.add_all([candidate, newer])
            self.db.get(Image, source_id).is_active = False
            self.db.add(GameState(
                game_id=game_id, week=0, age=28,
                state_json={"character_settings": {"story_origin": {"revision": (initial_revision or 0) + 1}}},
            ))
            self.db.commit()
            image_ids.update(candidate=candidate.image_id, newer=newer.image_id)
            return [candidate]

        def delete_image_files(self, images):
            deleted_paths.extend(image.storage_path for image in images)

    run_portrait_image_job(job_id, session_factory=Session, image_service_factory=FakeImageService)

    verify_db = Session()
    assert verify_db.get(PortraitImageGenerationJob, job_id).status == "failed"
    assert verify_db.get(Image, image_ids["newer"]).is_active is True
    assert verify_db.get(Image, image_ids["candidate"]).is_active is False
    assert deleted_paths == ["stale.png"]
    verify_db.close()


def test_worker_records_a_safe_failure_without_provider_or_prompt_details(temp_db_file):
    engine, _ = temp_db_file
    Session = sessionmaker(bind=engine)
    setup_db = Session()
    user, game = _game(setup_db)
    job, _ = PortraitImageJobService(setup_db).enqueue(user.user_id, _request(game.game_id))
    job_id = job.job_id
    setup_db.close()

    class FailingImageService:
        def __init__(self, _db):
            pass

        def generate_character_image(self, **_kwargs):
            raise RuntimeError("provider response included a private prompt")

    run_portrait_image_job(job_id, session_factory=Session, image_service_factory=FailingImageService)

    verify_db = Session()
    failed = verify_db.get(PortraitImageGenerationJob, job_id)
    assert failed.status == "failed"
    assert failed.error_code == "image_generation_failed"
    assert failed.error_message == "人物形象生成失败，请稍后重试"
    assert "private prompt" not in failed.error_message
    verify_db.close()
