"""Persistence and legacy selection contracts for protagonist portraits."""

from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
import pytest

from src.database.models import (
    Game,
    Image,
    PortraitCandidateBatch,
    PortraitCandidateSlot,
    PortraitImageGenerationJob,
    PortraitSelection,
    User,
)
from src.services.portrait_selection import selected_portrait, select_portrait, set_default_portrait

pytestmark = [pytest.mark.unit]


def create_owned_game(db) -> Game:
    user = User(private_id="candidate-owner", public_id="CAND0001")
    db.add(user)
    db.flush()
    game = Game(user_id=user.user_id, initial_state={})
    db.add(game)
    db.commit()
    return game


def add_two_active_portraits(db, game_id: int) -> tuple[Image, Image]:
    portraits = [
        Image(
            game_id=game_id,
            image_type="character",
            entity_name="林见微",
            entity_key="player_main",
            prompt_text=f"portrait {index}",
            storage_path=f"portraits/{index}.png",
            is_active=True,
            is_primary=index == 1,
        )
        for index in (1, 2)
    ]
    db.add_all(portraits)
    db.commit()
    return portraits[0], portraits[1]


def bad_image_id(db, kind: str, game_id: int) -> int:
    foreign = None
    if kind == "foreign_game":
        foreign = Game(user_id=db.get(Game, game_id).user_id, initial_state={})
        db.add(foreign)
        db.flush()
    image = Image(
        game_id=foreign.game_id if foreign else game_id,
        image_type="character",
        entity_name="其他人物",
        entity_key="npc_1" if kind == "npc" else "player_main",
        prompt_text="invalid choice",
        storage_path="invalid.png",
        is_active=kind != "inactive",
    )
    db.add(image)
    db.commit()
    return image.image_id


@pytest.mark.parametrize("bad_image_kind", ["foreign_game", "inactive", "npc"])
def test_bad_selection_preserves_current(db_session, tmp_path, bad_image_kind):
    game = create_owned_game(db_session)
    first, _ = add_two_active_portraits(db_session, game.game_id)
    first.storage_path = str(tmp_path / "first.png")
    (tmp_path / "first.png").write_bytes(b"image")
    db_session.commit()
    set_default_portrait(db_session, game.game_id, first.image_id)
    db_session.commit()
    before = selected_portrait(db_session, game.game_id).image_id
    with pytest.raises(ValueError):
        select_portrait(db_session, game.game_id, bad_image_id(db_session, bad_image_kind, game.game_id))
    assert selected_portrait(db_session, game.game_id).image_id == before


def test_ready_slot_selection_persists_and_staged_batch_does_not_override(db_session, tmp_path):
    from sqlalchemy.orm import Session
    game = create_owned_game(db_session)
    old, chosen = add_two_active_portraits(db_session, game.game_id)
    for image in (old, chosen):
        image.storage_path = str(tmp_path / f"{image.image_id}.png")
        (tmp_path / f"{image.image_id}.png").write_bytes(b"image")
    job = PortraitImageGenerationJob(game_id=game.game_id, user_id=game.user_id, request_json={"game_id": game.game_id})
    db_session.add(job)
    db_session.flush()
    batch = PortraitCandidateBatch(game_id=game.game_id, user_id=game.user_id, job_id=job.job_id, mode="fresh")
    db_session.add(batch)
    db_session.flush()
    db_session.add(PortraitCandidateSlot(batch_id=batch.batch_id, slot_index=1, status="ready", image_id=chosen.image_id))
    db_session.commit()
    set_default_portrait(db_session, game.game_id, old.image_id)
    db_session.commit()
    assert selected_portrait(db_session, game.game_id).image_id == old.image_id
    select_portrait(db_session, game.game_id, chosen.image_id)
    with Session(db_session.get_bind()) as fresh:
        assert selected_portrait(fresh, game.game_id).image_id == chosen.image_id
        assert fresh.get(PortraitSelection, game.game_id).is_user_selected is True


def test_selection_rejects_unready_or_missing_file(db_session, tmp_path):
    game = create_owned_game(db_session)
    old, candidate = add_two_active_portraits(db_session, game.game_id)
    set_default_portrait(db_session, game.game_id, old.image_id)
    job = PortraitImageGenerationJob(game_id=game.game_id, user_id=game.user_id, request_json={"game_id": game.game_id})
    db_session.add(job)
    db_session.flush()
    batch = PortraitCandidateBatch(game_id=game.game_id, user_id=game.user_id, job_id=job.job_id, mode="fresh")
    db_session.add(batch)
    db_session.flush()
    slot = PortraitCandidateSlot(batch_id=batch.batch_id, slot_index=1, status="queued", image_id=candidate.image_id)
    db_session.add(slot)
    candidate.storage_path = str(tmp_path / "missing.png")
    db_session.commit()
    with pytest.raises(ValueError, match="不可选择"):
        select_portrait(db_session, game.game_id, candidate.image_id)
    slot.status = "ready"
    db_session.commit()
    with pytest.raises(ValueError, match="文件不可用"):
        select_portrait(db_session, game.game_id, candidate.image_id)
    assert selected_portrait(db_session, game.game_id).image_id == old.image_id


def test_selection_route_checks_owner_and_returns_422(db_session):
    from src.api.routers.images import put_portrait_selection
    from src.api.schemas import SelectPortraitRequest
    game = create_owned_game(db_session)
    request = SelectPortraitRequest(game_id=game.game_id, image_id=999999)
    with pytest.raises(HTTPException) as foreign:
        put_portrait_selection(request, db_session, game.user_id + 1)
    assert foreign.value.status_code == 404
    with pytest.raises(HTTPException) as invalid:
        put_portrait_selection(request, db_session, game.user_id)
    assert invalid.value.status_code == 422


def test_selection_route_requires_authentication(client):
    response = client.put("/api/images/character/selection", json={"game_id": 1, "image_id": 1})
    assert response.status_code == 401


def test_first_slot_sets_default_but_cannot_override_manual_selection(db_session):
    game = create_owned_game(db_session)
    first, second = add_two_active_portraits(db_session, game.game_id)

    set_default_portrait(db_session, game.game_id, first.image_id)
    selection = db_session.get(PortraitSelection, game.game_id)
    assert selection.image_id == first.image_id
    assert selection.is_user_selected is False

    selection.image_id, selection.is_user_selected = second.image_id, True
    db_session.commit()
    set_default_portrait(db_session, game.game_id, first.image_id)

    db_session.expire_all()
    assert selected_portrait(db_session, game.game_id).image_id == second.image_id
    assert db_session.get(PortraitSelection, game.game_id).is_user_selected is True


def test_legacy_game_uses_newest_active_primary_main_character(db_session):
    game = create_owned_game(db_session)
    older, newer = add_two_active_portraits(db_session, game.game_id)
    newer.is_primary = True
    db_session.add(
        Image(
            game_id=game.game_id,
            image_type="character",
            entity_name="other",
            entity_key="npc_1",
            prompt_text="npc",
            storage_path="portraits/npc.png",
            is_active=True,
            is_primary=True,
        )
    )
    db_session.commit()

    assert db_session.get(PortraitSelection, game.game_id) is None
    assert selected_portrait(db_session, game.game_id).image_id == newer.image_id
    newer.is_active = False
    db_session.commit()
    assert selected_portrait(db_session, game.game_id).image_id == older.image_id


def test_legacy_game_with_one_active_primary_image_uses_that_image(db_session):
    game = create_owned_game(db_session)
    first = Image(
        game_id=game.game_id,
        image_type="character",
        entity_name="林见微",
        entity_key="player_main",
        prompt_text="legacy portrait",
        storage_path="portraits/legacy.png",
        is_active=True,
        is_primary=True,
    )
    db_session.add(first)
    db_session.commit()

    assert db_session.get(PortraitSelection, game.game_id) is None
    assert selected_portrait(db_session, game.game_id).image_id == first.image_id


def test_racing_default_insert_preserves_manual_choice_and_pending_slot(
    db_session, monkeypatch
):
    game = create_owned_game(db_session)
    first, second = add_two_active_portraits(db_session, game.game_id)
    job = PortraitImageGenerationJob(
        game_id=game.game_id,
        user_id=game.user_id,
        request_json={"game_id": game.game_id},
    )
    db_session.add(job)
    db_session.flush()
    batch = PortraitCandidateBatch(
        game_id=game.game_id,
        user_id=game.user_id,
        job_id=job.job_id,
        mode="initial",
    )
    db_session.add(batch)
    db_session.flush()
    slot = PortraitCandidateSlot(batch_id=batch.batch_id, slot_index=0)
    db_session.add(slot)
    db_session.add(
        PortraitSelection(game_id=game.game_id, image_id=second.image_id, is_user_selected=True)
    )
    db_session.commit()

    slot.status, slot.image_id = "completed", first.image_id
    real_get = db_session.get
    stale_read = True

    def get_with_racing_insert(model, key, *args, **kwargs):
        nonlocal stale_read
        if model is PortraitSelection and key == game.game_id and stale_read:
            stale_read = False
            return None
        return real_get(model, key, *args, **kwargs)

    # Force the helper's first read to be stale, as if another selection
    # committed just after it. The actual database row causes a real conflict.
    monkeypatch.setattr(db_session, "get", get_with_racing_insert)
    set_default_portrait(db_session, game.game_id, first.image_id)
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(PortraitSelection, game.game_id).image_id == second.image_id
    assert db_session.get(PortraitSelection, game.game_id).is_user_selected is True
    assert db_session.get(PortraitCandidateSlot, (batch.batch_id, 0)).image_id == first.image_id
    assert db_session.get(PortraitCandidateSlot, (batch.batch_id, 0)).status == "completed"


def test_batch_and_three_slots_persist_with_unique_slot_numbers(db_session):
    game = create_owned_game(db_session)
    job = PortraitImageGenerationJob(
        game_id=game.game_id,
        user_id=game.user_id,
        request_json={"game_id": game.game_id},
    )
    db_session.add(job)
    db_session.flush()
    batch = PortraitCandidateBatch(
        game_id=game.game_id,
        user_id=game.user_id,
        job_id=job.job_id,
        origin_revision=2,
        mode="initial",
        active_key=f"{game.game_id}:2",
    )
    db_session.add(batch)
    db_session.flush()
    db_session.add_all(
        [PortraitCandidateSlot(batch_id=batch.batch_id, slot_index=index) for index in (0, 1, 2)]
    )
    db_session.commit()
    db_session.expire_all()

    assert db_session.get(PortraitCandidateBatch, batch.batch_id).origin_revision == 2
    assert [
        slot.status
        for slot in db_session.query(PortraitCandidateSlot)
        .filter_by(batch_id=batch.batch_id)
        .order_by(PortraitCandidateSlot.slot_index)
    ] == ["queued", "queued", "queued"]

    db_session.add(PortraitCandidateSlot(batch_id=batch.batch_id, slot_index=1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

# Durable batch orchestration contracts.
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy.orm import sessionmaker
from src.database.models import GameState
from src.services.portrait_candidate_jobs import (
    enqueue_candidate_batch, run_candidate_batch, candidate_batch_state, retry_candidate_batch,
)


@pytest.fixture
def batch_setup(temp_db_file):
    Session = sessionmaker(bind=temp_db_file[0])
    with Session() as db:
        game = create_owned_game(db)
        game.initial_state = {"player_name": "林见微", "character_settings": {
            "age": 28, "gender": "女", "era": {"era_name": "宋代"},
            "story_origin": {"revision": 1}, "personality": "谨慎"}}
        db.commit()
        job = enqueue_candidate_batch(db, game.user_id, game.game_id, "initial")
        ids = game.user_id, game.game_id, job.job_id
    return Session, ids


@pytest.fixture
def fake_provider():
    class Provider:
        generated_slot_indices = []
        calls = []
        fail = set()
        def __init__(self, db):
            self.db = db
        def generate_character_candidate(self, **kwargs):
            index = kwargs["slot_index"]
            self.generated_slot_indices.append(index)
            self.calls.append(kwargs)
            if index in self.fail:
                raise RuntimeError("secret provider message")
            image = Image(game_id=kwargs["game_id"], image_type="character",
                entity_key="player_main", entity_name=kwargs["name"], prompt_text="prompt",
                storage_path=f"candidate-{index}.png", is_active=False,
                metadata_json={"batch_id": kwargs["batch_id"], "slot_index": index})
            self.db.add(image)
            self.db.commit()
            return image
    return Provider


@pytest.fixture
def batch_with_two_ready_slots(batch_setup):
    Session, ids = batch_setup
    with Session() as db:
        batch = db.query(PortraitCandidateBatch).filter_by(job_id=ids[2]).one()
        for index in (0, 1):
            image = Image(game_id=ids[1], image_type="character", entity_key="player_main",
                entity_name="林见微", prompt_text="saved", storage_path=f"saved-{index}.png", is_active=True)
            db.add(image)
            db.flush()
            slot = db.get(PortraitCandidateSlot, (batch.batch_id, index))
            slot.status, slot.image_id = "ready", image.image_id
        db.commit()
    return batch_setup


def test_batch_returns_before_provider_and_reuses_same_origin(db_session):
    owner = create_owned_game(db_session)
    first = enqueue_candidate_batch(db_session, owner.user_id, owner.game_id, "initial")
    second = enqueue_candidate_batch(db_session, owner.user_id, owner.game_id, "initial")
    assert first.job_id == second.job_id
    assert first.status == "queued"
    assert db_session.query(PortraitCandidateSlot).count() == 3


def test_retry_only_missing_slot_after_worker_restart(batch_with_two_ready_slots, fake_provider):
    Session, ids = batch_with_two_ready_slots
    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=fake_provider)
    assert fake_provider.generated_slot_indices == [2]
    with Session() as db:
        state = candidate_batch_state(db, ids[1], ids[0])
        assert state.completed_count == 3
        assert state.status == "succeeded"
        assert enqueue_candidate_batch(db, ids[0], ids[1], "initial").job_id == ids[2]


def test_partial_failure_retry_and_frozen_snapshot(batch_setup, fake_provider):
    Session, ids = batch_setup
    with Session() as db:
        db.add(GameState(game_id=ids[1], week=0, age=28, state_json={
            "player_name": "changed", "character_settings": {"story_origin": {"revision": 1}}}))
        db.commit()
    fake_provider.fail = {1}
    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=fake_provider)
    with Session() as db:
        state = candidate_batch_state(db, ids[1], ids[0])
        assert state.status == "partial_failed"
        assert state.completed_count == 2
        selected = state.selected_image_id
        assert state.slots[1].error_code == "image_generation_failed"
        retry_candidate_batch(db, state.batch_id, ids[0])
    fake_provider.fail = set()
    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=fake_provider)
    assert fake_provider.generated_slot_indices == [0, 1, 2, 1]
    assert all(call["name"] == "林见微" and call["era"] == "宋代" for call in fake_provider.calls)
    assert all(call["character_settings"]["age"] == 28 for call in fake_provider.calls)
    assert len({call["direction"] for call in fake_provider.calls}) == 3
    with Session() as db:
        assert candidate_batch_state(db, ids[1], ids[0]).selected_image_id == selected


def test_saved_inactive_image_reconciled_without_provider_call(batch_setup, fake_provider):
    Session, ids = batch_setup
    with Session() as db:
        batch = db.query(PortraitCandidateBatch).filter_by(job_id=ids[2]).one()
        image = fake_provider(db).generate_character_candidate(game_id=ids[1], name="林见微", batch_id=batch.batch_id, slot_index=0)
        image_id = image.image_id
    fake_provider.generated_slot_indices.clear()
    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=fake_provider)
    assert fake_provider.generated_slot_indices == [1, 2]
    with Session() as db:
        assert db.get(Image, image_id).is_active


def test_stale_origin_during_provider_does_not_activate(batch_setup, fake_provider):
    Session, ids = batch_setup
    class StaleProvider(fake_provider):
        def generate_character_candidate(self, **kwargs):
            image = super().generate_character_candidate(**kwargs)
            self.db.add(GameState(game_id=ids[1], week=0, age=28,
                state_json={"character_settings": {"story_origin": {"revision": 2}}}))
            self.db.commit()
            return image
    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=StaleProvider)
    with Session() as db:
        assert db.query(Image).filter_by(is_active=True).count() == 0
        assert db.get(PortraitSelection, ids[1]) is None
        assert db.get(PortraitImageGenerationJob, ids[2]).error_code == "story_origin_superseded"
    assert fake_provider.generated_slot_indices == [0]


def test_simultaneous_enqueue_uses_database_uniqueness(temp_db_file):
    Session = sessionmaker(bind=temp_db_file[0])
    with Session() as db:
        game = create_owned_game(db)
        user_id, game_id = game.user_id, game.game_id
    barrier = Barrier(2)
    def enqueue(_):
        with Session() as db:
            barrier.wait()
            return enqueue_candidate_batch(db, user_id, game_id, "initial").job_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(enqueue, range(2)))
    assert ids[0] == ids[1]
    with Session() as db:
        assert db.query(PortraitCandidateBatch).count() == 1
        assert db.query(PortraitCandidateSlot).count() == 3


def test_fresh_batch_keeps_legacy_selection_and_excludes_overlapping_modes(batch_setup, fake_provider):
    Session, ids = batch_setup
    with Session() as db:
        assert enqueue_candidate_batch(db, ids[0], ids[1], "fresh").job_id == ids[2]
        old, _ = add_two_active_portraits(db, ids[1])
        old.is_primary = True
        db.query(Image).filter(Image.image_id != old.image_id).update({"is_primary": False})
        db.commit()
        old_id = old.image_id
    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=fake_provider)
    with Session() as db:
        assert candidate_batch_state(db, ids[1], ids[0]).selected_image_id == old_id
        fresh = enqueue_candidate_batch(db, ids[0], ids[1], "fresh")
        assert fresh.job_id != ids[2]
        fresh_id = fresh.job_id
    run_candidate_batch(fresh_id, session_factory=Session, image_service_factory=fake_provider)
    with Session() as db:
        assert candidate_batch_state(db, ids[1], ids[0]).selected_image_id == old_id
        assert db.get(Image, old_id).is_active is True


def test_duplicate_worker_delivery_does_not_repeat_provider(batch_setup, fake_provider):
    from threading import Event
    Session, ids = batch_setup
    entered, release = Event(), Event()
    class SlowProvider(fake_provider):
        def generate_character_candidate(self, **kwargs):
            if kwargs["slot_index"] == 0:
                entered.set()
                assert release.wait(timeout=5)
            return super().generate_character_candidate(**kwargs)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run_candidate_batch, ids[2], session_factory=Session, image_service_factory=SlowProvider)
        assert entered.wait(timeout=5)
        try:
            duplicate = pool.submit(run_candidate_batch, ids[2], session_factory=Session, image_service_factory=SlowProvider)
            duplicate.result(timeout=5)
        finally:
            release.set()
        first.result(timeout=5)
    assert fake_provider.generated_slot_indices == [0, 1, 2]


def test_dispatch_and_startup_recovery_resume_candidate_slots(batch_with_two_ready_slots, fake_provider, monkeypatch):
    import src.services.portrait_image_jobs as jobs
    Session, ids = batch_with_two_ready_slots
    with Session() as db:
        db.get(PortraitImageGenerationJob, ids[2]).status = "running"
        db.commit()
    scheduled = []
    monkeypatch.setattr(jobs, "SessionLocal", Session)
    monkeypatch.setattr(jobs, "schedule_portrait_image_job", scheduled.append)
    assert jobs.recover_pending_portrait_image_jobs() == [ids[2]]
    assert scheduled == [ids[2]]
    jobs.run_portrait_image_job(ids[2], session_factory=Session, image_service_factory=fake_provider)
    assert fake_provider.generated_slot_indices == [2]


def test_retry_after_terminal_commit_before_scheduler_cleanup_is_dispatched(
    batch_setup, fake_provider, monkeypatch,
):
    """A retry accepted while the old callback is unwinding must not be lost."""
    from threading import Event
    import src.services.portrait_image_jobs as jobs
    Session, ids = batch_setup
    terminal_committed, allow_cleanup, retry_finished = Event(), Event(), Event()
    fake_provider.fail = {1}
    calls = []
    real_run = jobs.run_portrait_image_job

    def paused_worker(job_id):
        calls.append(job_id)
        real_run(job_id, session_factory=Session, image_service_factory=fake_provider)
        if len(calls) == 1:
            terminal_committed.set()
            assert allow_cleanup.wait(timeout=5)
        else:
            retry_finished.set()

    with ThreadPoolExecutor(max_workers=1) as pool:
        monkeypatch.setattr(jobs, "get_image_thread_pool", lambda: pool)
        monkeypatch.setattr(jobs, "run_portrait_image_job", paused_worker)
        jobs.schedule_portrait_image_job(ids[2])
        try:
            assert terminal_committed.wait(timeout=5)
            with Session() as db:
                state = candidate_batch_state(db, ids[1], ids[0])
                assert state.status == "partial_failed"
                assert state.completed_count == 2
                retry_candidate_batch(db, state.batch_id, ids[0])
            fake_provider.fail = set()
            jobs.schedule_portrait_image_job(ids[2])
        finally:
            allow_cleanup.set()
        assert retry_finished.wait(timeout=5), "accepted retry was stranded in queued state"
    assert calls == [ids[2], ids[2]]
    assert fake_provider.generated_slot_indices == [0, 1, 2, 1]
    with Session() as db:
        assert candidate_batch_state(db, ids[1], ids[0]).status == "succeeded"
