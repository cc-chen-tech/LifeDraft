"""Offline failure injection through real workers and production JSON formatting."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy.orm import Session as SqlSession, sessionmaker

from config.logging_config import JsonLogFormatter
from src.ai.image_generator import ImageGenerator
from src.database.models import Game, Image, PortraitImageGenerationJob, User
from src.game.round.illustration_service import RoundIllustrationService
from src.services import portrait_image_jobs as jobs
from src.services.image_storage import ImageStorageError, ImageStorageService

pytestmark = [pytest.mark.integration]
PRIVATE = "private story sk-private-test-secret"


def _records(caplog, event):
    payloads = [json.loads(JsonLogFormatter().format(record)) for record in caplog.records]
    assert "private story" not in json.dumps(payloads)
    assert "sk-private-test-secret" not in json.dumps(payloads)
    return [record for record in payloads if record.get("event") == event]


def _job(db, suffix, operation="generate"):
    user = User(private_id=f"diag-{suffix}", public_id=f"DIAG{suffix:04d}")
    db.add(user)
    db.flush()
    game = Game(user_id=user.user_id, initial_state={})
    db.add(game)
    db.flush()
    job = PortraitImageGenerationJob(game_id=game.game_id, user_id=user.user_id,
        request_json={"operation": operation, "game_id": game.game_id, "entity_name": "person",
                      "description": PRIVATE, "era": "modern"}, status="queued")
    db.add(job)
    db.commit()
    return job.job_id, game.game_id, user.user_id


def test_two_users_worker_failures_and_restart_keep_stable_identity(temp_db_file, caplog):
    caplog.set_level(logging.INFO)
    factory = sessionmaker(bind=temp_db_file[0])
    with factory() as db:
        identities = [_job(db, index) for index in (1, 2)]
    barrier = Barrier(2)

    class FailingProvider:
        def __init__(self, db): pass
        def generate_character_image(self, **kwargs):
            barrier.wait(timeout=5)
            raise RuntimeError(PRIVATE)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(jobs.run_portrait_image_job, identity[0],
                    session_factory=factory, image_service_factory=FailingProvider) for identity in identities]
        for future in futures:
            future.result(timeout=10)
    events = _records(caplog, "portrait_job_finished")
    assert len(events) == 2
    for job_id, game_id, user_id in identities:
        event = next(event for event in events if event["job_id"] == job_id)
        assert (event["game_id"], event["user_id"]) == (game_id, user_id)
        assert event["outcome"] == "failed"
        assert event["operation_id"] == f"portrait-job-{job_id}"
        assert event["attempt_id"]
    first = next(event for event in events if event["job_id"] == identities[0][0])
    with factory() as db:
        db.get(PortraitImageGenerationJob, identities[0][0]).status = "running"
        db.commit()
        jobs.requeue_interrupted_portrait_jobs(db)
    barrier = Barrier(1)
    jobs.run_portrait_image_job(identities[0][0], session_factory=factory, image_service_factory=FailingProvider)
    last = _records(caplog, "portrait_job_finished")[-1]
    assert last["operation_id"] == first["operation_id"]
    assert last["attempt_id"] != first["attempt_id"]
    assert last["user_id"] == first["user_id"]
    assert _records(caplog, "portrait_job_recovered")


def test_failure_reporting_survives_failed_database_write(temp_db_file, caplog):
    caplog.set_level(logging.INFO)
    engine = temp_db_file[0]
    with SqlSession(engine) as db:
        job_id, game_id, user_id = _job(db, 3)

    class FailingSession(SqlSession):
        broken = False
        def commit(self):
            if self.broken:
                raise OSError(PRIVATE)
            return super().commit()

    class FailingProvider:
        def __init__(self, db): self.db = db
        def generate_character_image(self, **kwargs):
            self.db.broken = True
            raise RuntimeError(PRIVATE)

    with pytest.raises(OSError):
        jobs.run_portrait_image_job(job_id,
            session_factory=sessionmaker(bind=engine, class_=FailingSession), image_service_factory=FailingProvider)
    failed = _records(caplog, "portrait_job_finished")
    assert failed and failed[-1]["job_id"] == job_id
    persistence = _records(caplog, "portrait_job_failure_persistence")
    assert persistence[-1]["outcome"] == "failed"
    assert (persistence[-1]["user_id"], persistence[-1]["game_id"]) == (user_id, game_id)


def test_scheduler_observes_future_failure(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(jobs, "get_image_thread_pool", lambda: pool)
        def fail(_job_id): raise RuntimeError(PRIVATE)
        monkeypatch.setattr(jobs, "run_portrait_image_job", fail)
        jobs.schedule_portrait_image_job(90001)
    events = _records(caplog, "portrait_worker_crashed")
    assert len(events) == 1
    assert events[0]["job_id"] == 90001
    assert events[0]["outcome"] == "failed"


@pytest.mark.parametrize("failure", ["mkdir", "write"])
def test_local_storage_failure_is_typed_and_has_stage_without_filename(tmp_path, monkeypatch, caplog, failure):
    caplog.set_level(logging.INFO)
    storage = ImageStorageService(local_path=tmp_path)
    def fail(*args, **kwargs): raise PermissionError(PRIVATE)
    if failure == "mkdir":
        monkeypatch.setattr(Path, "mkdir", fail)
    else:
        monkeypatch.setattr("builtins.open", fail)
    with pytest.raises(ImageStorageError):
        storage.save_image(b"image", 77, "character", PRIVATE)
    events = _records(caplog, "image_storage_finished")
    assert events[-1]["game_id"] == 77
    assert events[-1]["outcome"] == "failed"
    assert events[-1]["phase"] == "storage"


def test_unreadable_selected_reference_emits_fallback_identity(db_session, caplog):
    caplog.set_level(logging.INFO)
    _, game_id, _ = _job(db_session, 4)
    image = Image(game_id=game_id, image_type="character", entity_key="player_main",
        entity_name="person", prompt_text=PRIVATE, storage_path="missing.png")
    db_session.add(image)
    db_session.commit()
    class BrokenStorage:
        def get_image_data(self, *args): raise OSError(PRIVATE)
    service = RoundIllustrationService(object(), BrokenStorage(), db_session)
    assert service._get_image_url_as_base64({"image_id": image.image_id}, game_id) is None
    event = _records(caplog, "image_reference_fallback")[-1]
    assert event["asset_id"] == image.image_id
    assert event["game_id"] == game_id
    assert event["used_fallback"] is True


def test_typed_http_failure_preserves_status_for_provider_telemetry():
    generator = ImageGenerator(api_key="fake", base_url="https://unused.example/v1")
    error = generator._provider_error_for_http(503, operation="generate")
    assert getattr(error, "status_code", None) == 503
    assert error.code == "image_provider_http_503_generate"


@pytest.mark.parametrize("mode", ["success", "partial", "superseded"])
def test_candidate_batch_reports_each_slot_and_terminal_state(temp_db_file, caplog, mode):
    from src.services.portrait_candidate_jobs import enqueue_candidate_batch, run_candidate_batch
    caplog.set_level(logging.INFO)
    factory = sessionmaker(bind=temp_db_file[0])
    with factory() as db:
        _, game_id, user_id = _job(db, 5)
        queued = enqueue_candidate_batch(db, user_id, game_id, "initial")
        job_id = queued.job_id
        if mode == "superseded":
            db.get(Game, game_id).initial_state = {"character_settings": {"story_origin": {"revision": 2}}}
            db.commit()
    class Provider:
        def __init__(self, db): self.db = db
        def generate_character_candidate(self, **kwargs):
            if mode == "partial" and kwargs["slot_index"] == 1:
                raise RuntimeError(PRIVATE)
            image = Image(game_id=game_id, image_type="character", entity_key="player_main",
                entity_name="person", prompt_text=PRIVATE, storage_path="fake.png", is_active=False,
                metadata_json={"batch_id": kwargs["batch_id"], "slot_index": kwargs["slot_index"]})
            self.db.add(image)
            self.db.commit()
            return image
    run_candidate_batch(job_id, session_factory=factory, image_service_factory=Provider)
    terminal = _records(caplog, "portrait_job_finished")[-1]
    assert terminal["job_id"] == job_id
    assert terminal["user_id"] == user_id
    assert terminal["outcome"] == {"success": "succeeded", "partial": "partial_failed", "superseded": "superseded"}[mode]
    slots = _records(caplog, "portrait_slot_finished")
    assert len(slots) == (0 if mode == "superseded" else 3)
    assert all(event["batch_id"] and event["job_id"] == job_id for event in slots)
    for event in slots:
        assert (event["user_id"], event["game_id"]) == (user_id, game_id)
        assert event["segment_index"] == event["slot_index"]
        assert event["attempt_id"] == f"portrait-job-{job_id}-attempt-1-slot-{event['slot_index']}"
    if mode != "superseded":
        assert len({event["attempt_id"] for event in slots}) == 3
        assert len(_records(caplog, "portrait_job_started")) == 1
        assert len(_records(caplog, "portrait_job_finished")) == 1


def test_scene_provider_success_then_database_failure_is_not_delivery_success(db_session, tmp_path, monkeypatch, caplog):
    from src.services.image.scene_service import SceneImageService
    from src.services.image import ImageServiceError
    caplog.set_level(logging.INFO)
    _, game_id, _ = _job(db_session, 6)
    class Provider:
        def analyze_story_for_illustration(self, **kwargs): return "scene", "scene"
        def generate_image(self, **kwargs): return b"fake-image", "scene"
    service = SceneImageService(db_session, image_client=Provider(),
                                storage_service=ImageStorageService(local_path=tmp_path))
    def fail(): raise OSError(PRIVATE)
    monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(ImageServiceError):
        service.generate_round_scene_image(game_id, 1, "scene", {}, "person", week=0)
    events = _records(caplog, "image_delivery_finished")
    assert events[-1]["phase"] == "persistence"
    assert events[-1]["outcome"] == "failed"
    assert events[-1]["game_id"] == game_id
    assert not any(event["outcome"] == "succeeded" for event in events)


@pytest.mark.parametrize("kind", ["opening", "candidate", "character", "round_worker"])
def test_other_image_paths_report_persistence_failure(db_session, tmp_path, monkeypatch, caplog, kind):
    from src.services.image.scene_service import SceneImageService
    from src.services.image.character_service import CharacterImageService
    from src.services.portrait_candidate_jobs import enqueue_candidate_batch
    from src.database.models import PortraitCandidateBatch
    caplog.set_level(logging.INFO)
    _, game_id, user_id = _job(db_session, 7)
    class Provider:
        def analyze_story_for_illustration(self, **kwargs): return "scene", "scene"
        def generate_image(self, **kwargs): return b"fake-image", "scene"
        def generate_opening_illustration(self, **kwargs): return b"fake-image", "scene", "scene"
        def generate_character_images(self, **kwargs): return [(b"fake-image", "scene")], None
        def generate_appearance_anchor(self, **kwargs): return {}
    storage = ImageStorageService(local_path=tmp_path)
    if kind == "candidate":
        job = enqueue_candidate_batch(db_session, user_id, game_id, "initial")
        batch_id = db_session.query(PortraitCandidateBatch).filter_by(job_id=job.job_id).one().batch_id
    commit = db_session.commit
    commit_count = 0
    def fail():
        nonlocal commit_count
        commit_count += 1
        if kind in ("opening", "character") and commit_count == 1:
            return commit()
        raise OSError(PRIVATE)
    monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(Exception):
        if kind == "opening":
            SceneImageService(db_session, Provider(), storage).generate_opening_illustration(
                game_id, "scene", {}, "person")
        elif kind == "candidate":
            CharacterImageService(db_session, Provider(), storage).generate_character_candidate(
                game_id=game_id, name="person", description="scene", era="modern",
                character_settings={}, direction="one", batch_id=batch_id, slot_index=0)
        elif kind == "character":
            CharacterImageService(db_session, Provider(), storage).generate_character_image(
                game_id, "person", "scene", "modern")
        else:
            RoundIllustrationService(Provider(), storage, db_session)._generate_round_illustration_sync(
                game_id, 1, "scene", {}, "person", [], week=0)
    events = _records(caplog, "image_delivery_finished")
    assert len(events) == 1
    assert events[0]["phase"] == "persistence"
    assert events[0]["outcome"] == "failed"
    assert events[0]["game_id"] == game_id


@pytest.mark.parametrize("modular", [False, True])
def test_facade_reference_failure_reports_selected_asset(db_session, tmp_path, caplog, modular):
    from src.services.image_service import ImageService
    from src.services.image import ImageService as ModularImageService
    caplog.set_level(logging.INFO)
    _, game_id, _ = _job(db_session, 8)
    image = Image(game_id=game_id, image_type="character", entity_key="player_main",
        entity_name="person", prompt_text=PRIVATE, storage_path="missing.png", is_active=True, is_primary=True)
    db_session.add(image)
    db_session.commit()
    service = (ModularImageService if modular else ImageService).__new__(ModularImageService if modular else ImageService)
    service.db = db_session
    service.storage_service = ImageStorageService(local_path=tmp_path)
    assert service._get_player_image_base64(game_id, image.image_id) == (None, None)
    event = _records(caplog, "image_reference_fallback")[-1]
    assert event["asset_id"] == image.image_id
    assert event["game_id"] == game_id


def test_round_worker_future_failure_is_observed(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    service = RoundIllustrationService(object(), object(), object())
    def fail(*args, **kwargs): raise RuntimeError(PRIVATE)
    monkeypatch.setattr(service, "_generate_round_illustration_sync", fail)
    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr("src.game.round.illustration_service.get_image_thread_pool", lambda: pool)
        service.generate_round_illustration_async(77, 1, "scene", {}, "person", [], week=0)
    event = _records(caplog, "image_worker_crashed")[-1]
    assert event["game_id"] == 77
    assert event["outcome"] == "failed"


def test_enqueue_links_request_to_durable_job(db_session, caplog):
    from src.observability.request_context import RequestContext, request_context
    caplog.set_level(logging.INFO)
    _, game_id, user_id = _job(db_session, 9)
    with request_context(RequestContext(request_id="browser-enqueue", operation_id="browser-op")):
        job, _ = jobs.PortraitImageJobService(db_session).enqueue(user_id, {
            "game_id": game_id, "entity_name": "person", "description": PRIVATE})
    event = _records(caplog, "portrait_job_queued")[-1]
    assert event["request_id"] == "browser-enqueue"
    assert (event["job_id"], event["game_id"], event["user_id"]) == (job.job_id, game_id, user_id)


def test_session_close_failure_does_not_leak_worker_identity(temp_db_file):
    from src.observability.request_context import current_request_context
    engine = temp_db_file[0]
    with SqlSession(engine) as db:
        job_id, _, _ = _job(db, 10)
    class BrokenClose(SqlSession):
        def close(self):
            super().close()
            raise OSError(PRIVATE)
    class Provider:
        def __init__(self, db): pass
        def generate_character_image(self, **kwargs): raise RuntimeError(PRIVATE)
    before = current_request_context()
    with pytest.raises(OSError):
        jobs.run_portrait_image_job(job_id, session_factory=sessionmaker(bind=engine, class_=BrokenClose),
                                    image_service_factory=Provider)
    assert current_request_context() == before


def test_job_commit_failure_is_reported_as_persistence(temp_db_file, caplog):
    from types import SimpleNamespace
    caplog.set_level(logging.INFO)
    engine = temp_db_file[0]
    with SqlSession(engine) as db:
        job_id, _, _ = _job(db, 11)
    class FailSuccessCommit(SqlSession):
        def commit(self):
            if any(isinstance(item, PortraitImageGenerationJob) and item.status == "succeeded" for item in self.dirty):
                raise OSError(PRIVATE)
            return super().commit()
    class Provider:
        def __init__(self, db): pass
        def generate_character_image(self, **kwargs): return [SimpleNamespace(image_id=41)]
    jobs.run_portrait_image_job(job_id, session_factory=sessionmaker(bind=engine, class_=FailSuccessCommit),
                                image_service_factory=Provider)
    events = _records(caplog, "portrait_job_finished")
    assert len(events) == 1
    assert events[0]["phase"] == "persistence"
    assert events[0]["outcome"] == "failed"


def test_real_generator_events_inherit_worker_identity_and_provider_code(temp_db_file, caplog, monkeypatch):
    from src.ai.image_exceptions import ImageProviderError
    from src.services.image import ImageProviderServiceError
    caplog.set_level(logging.INFO)
    model_logger = logging.getLogger("model")
    # Prior logging configuration may already attach the capture handler.
    # Use one local capture path and restore both attributes after this test.
    monkeypatch.setattr(model_logger, "handlers", [caplog.handler])
    monkeypatch.setattr(model_logger, "propagate", False)
    provider_calls = []
    factory = sessionmaker(bind=temp_db_file[0])
    with factory() as db:
        job_id, game_id, user_id = _job(db, 12)
    class Provider:
        def __init__(self, db): pass
        def generate_character_image(self, **kwargs):
            generator = ImageGenerator(api_key="fake", base_url="https://unused.example/v1")
            def offline(**kwargs):
                provider_calls.append(kwargs)
                generator._raise_for_minimax_error({
                    "base_resp": {"status_code": 2056, "status_msg": PRIVATE}, "trace_id": "safe-trace-12"}, PRIVATE)
            generator._call_api = offline
            try:
                generator.generate_image(PRIVATE)
            except ImageProviderError as error:
                raise ImageProviderServiceError.from_provider(error) from error
    jobs.run_portrait_image_job(job_id, session_factory=factory, image_service_factory=Provider)
    assert len(provider_calls) == 1
    _records(caplog, "portrait_job_finished")  # Applies the production formatter privacy assertions.
    events = [record.model_event for record in caplog.records if hasattr(record, "model_event")]
    assert len(events) == 1
    event = events[0]
    assert (event["job_id"], event["game_id"], event["user_id"]) == (job_id, game_id, user_id)
    assert event["provider_code"] == "minimax_2056"
    assert event["provider_trace_id"] == "safe-trace-12"
    assert event["outcome"] == "failure"


def test_stale_scene_generation_has_superseded_terminal_event(caplog):
    caplog.set_level(logging.INFO)
    class Provider:
        def analyze_story_for_illustration(self, **kwargs): return "scene", "scene"
        def generate_image(self, **kwargs): return b"image", "scene"
    service = RoundIllustrationService(Provider(), object(), object())
    service._generate_round_illustration_sync(77, 1, "scene", {}, "person", [],
                                             week=0, validity_callback=lambda: False)
    event = _records(caplog, "image_delivery_finished")[-1]
    assert event["outcome"] == "superseded"
    assert event["game_id"] == 77
    assert event["persisted"] is False
