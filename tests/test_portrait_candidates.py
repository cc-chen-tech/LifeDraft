"""Persistence and legacy selection contracts for protagonist portraits."""

from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
import time
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
from src.services.portrait_selection import (is_selectable_candidate, selected_portrait,
                                             select_portrait, set_default_portrait)

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


def test_only_current_and_latest_staged_batch_are_selectable(db_session, tmp_path):
    game = create_owned_game(db_session)
    images = []
    for label in ("A", "B", "C"):
        path = tmp_path / f"{label}.png"
        path.write_bytes(b"image")
        image = Image(game_id=game.game_id, image_type="character", entity_name="林见微",
                      entity_key="player_main", prompt_text=label,
                      storage_path=str(path), is_active=True, is_primary=False)
        db_session.add(image)
        db_session.flush()
        job = PortraitImageGenerationJob(game_id=game.game_id, user_id=game.user_id,
                                         request_json={"game_id": game.game_id, "origin_revision": None})
        db_session.add(job)
        db_session.flush()
        batch = PortraitCandidateBatch(game_id=game.game_id, user_id=game.user_id,
                                       job_id=job.job_id, mode="fresh")
        db_session.add(batch)
        db_session.flush()
        db_session.add(PortraitCandidateSlot(batch_id=batch.batch_id, slot_index=0,
                                             status="ready", image_id=image.image_id))
        images.append(image)
    db_session.add(PortraitSelection(game_id=game.game_id, image_id=images[1].image_id,
                                     is_user_selected=True))
    db_session.commit()

    assert is_selectable_candidate(db_session, game.game_id, images[1].image_id)
    assert is_selectable_candidate(db_session, game.game_id, images[2].image_id)
    with pytest.raises(ValueError, match="不可选择"):
        select_portrait(db_session, game.game_id, images[0].image_id)
    assert selected_portrait(db_session, game.game_id).image_id == images[1].image_id
    assert select_portrait(db_session, game.game_id, images[2].image_id).image_id == images[2].image_id


def test_legacy_current_main_image_can_be_selected(db_session, tmp_path):
    game = create_owned_game(db_session)
    image, _ = add_two_active_portraits(db_session, game.game_id)
    path = tmp_path / "legacy.png"
    path.write_bytes(b"image")
    image.storage_path = str(path)
    db_session.commit()
    assert select_portrait(db_session, game.game_id, image.image_id).image_id == image.image_id


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


def test_three_candidate_provider_calls_overlap_and_all_slots_finish(batch_setup, fake_provider):
    """One slow provider call must not keep the other two slots queued."""
    from threading import Barrier, BrokenBarrierError

    Session, ids = batch_setup
    entered = Barrier(3, timeout=3)

    class OverlappingProvider(fake_provider):
        def generate_character_candidate(self, **kwargs):
            try:
                entered.wait()
            except BrokenBarrierError as exc:
                raise AssertionError("three slots did not reach the provider together") from exc
            return super().generate_character_candidate(**kwargs)

    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=OverlappingProvider)

    with Session() as db:
        state = candidate_batch_state(db, ids[1], ids[0])
        assert state.status == "succeeded"
        assert state.completed_count == 3
        assert [slot.status for slot in state.slots] == ["ready", "ready", "ready"]
        assert len({slot.image_id for slot in state.slots}) == 3


def test_candidate_slot_workers_keep_request_correlation(batch_setup, fake_provider):
    from src.observability.request_context import (RequestContext,
                                                   current_request_context,
                                                   request_context)

    from threading import Barrier

    Session, ids = batch_setup
    seen = {}
    overlap = Barrier(3)

    class ContextProvider(fake_provider):
        def generate_character_candidate(self, **kwargs):
            seen[kwargs["slot_index"]] = current_request_context()
            overlap.wait(timeout=5)
            return super().generate_character_candidate(**kwargs)

    context = RequestContext(request_id="portrait-request-1", operation_id="portrait-operation-1")
    with request_context(context):
        run_candidate_batch(ids[2], session_factory=Session, image_service_factory=ContextProvider)

        assert current_request_context() == context

    assert set(seen) == {0, 1, 2}
    for index, worker in seen.items():
        assert worker.request_id == context.request_id
        assert (worker.user_id, worker.game_id, worker.job_id) == ids
        assert worker.operation_id == f"portrait-job-{ids[2]}"
        assert worker.segment_index == index
        assert worker.attempt_id == f"portrait-job-{ids[2]}-attempt-1-slot-{index}"


def test_parallel_batches_limit_total_provider_calls(batch_setup, fake_provider):
    """Several games cannot multiply provider concurrency without a bound."""
    from copy import deepcopy
    from threading import Event, Lock

    Session, ids = batch_setup
    with Session() as db:
        second_game = Game(user_id=ids[0], initial_state=deepcopy(db.get(Game, ids[1]).initial_state))
        db.add(second_game)
        db.commit()
        second_job_id = enqueue_candidate_batch(db, ids[0], second_game.game_id, "initial").job_id
    entered_three, release = Event(), Event()
    lock = Lock()
    active = peak = 0

    class CountedProvider(fake_provider):
        def generate_character_candidate(self, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                if active == 3:
                    entered_three.set()
            try:
                assert release.wait(timeout=5)
                return super().generate_character_candidate(**kwargs)
            finally:
                with lock:
                    active -= 1

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(run_candidate_batch, job_id, session_factory=Session,
                            image_service_factory=CountedProvider)
                for job_id in (ids[2], second_job_id)]
        assert entered_three.wait(timeout=5)
        time.sleep(0.1)
        release.set()
        for job in jobs:
            job.result(timeout=10)

    assert peak == 3
    with Session() as db:
        assert db.get(PortraitImageGenerationJob, ids[2]).status == "succeeded"
        assert db.get(PortraitImageGenerationJob, second_job_id).status == "succeeded"


def test_manual_choice_survives_a_slower_parallel_slot(batch_setup, fake_provider, monkeypatch):
    from threading import Event

    Session, ids = batch_setup
    slow_entered, release_slow = Event(), Event()

    class SlowFirstProvider(fake_provider):
        def generate_character_candidate(self, **kwargs):
            if kwargs["slot_index"] == 0:
                slow_entered.set()
                assert release_slow.wait(timeout=5)
            return super().generate_character_candidate(**kwargs)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run_candidate_batch, ids[2], session_factory=Session,
                             image_service_factory=SlowFirstProvider)
        assert slow_entered.wait(timeout=5)
        try:
            with Session() as db:
                batch = db.query(PortraitCandidateBatch).filter_by(job_id=ids[2]).one()
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    db.expire_all()
                    slot = db.get(PortraitCandidateSlot, (batch.batch_id, 1))
                    if slot.status == "ready":
                        break
                    time.sleep(0.02)
                else:
                    pytest.fail("a later slot did not finish while slot 0 was blocked")
                chosen_id = slot.image_id
                monkeypatch.setattr(
                    "src.services.portrait_selection.ImageStorageService.get_image_data",
                    lambda *_args: b"image",
                )
                select_portrait(db, ids[1], chosen_id)
        finally:
            release_slow.set()
        future.result(timeout=5)

    with Session() as db:
        assert candidate_batch_state(db, ids[1], ids[0]).status == "succeeded"
        assert selected_portrait(db, ids[1]).image_id == chosen_id
        assert db.get(PortraitSelection, ids[1]).is_user_selected is True


def test_batch_finalization_cannot_resurrect_a_superseded_job(batch_setup, fake_provider):
    """A newer story origin must win even when it arrives during batch finalization."""
    from threading import current_thread
    from sqlalchemy import event, text
    from sqlalchemy.exc import OperationalError

    Session, ids = batch_setup
    coordinator_thread = current_thread()
    superseded = False
    supersession_waited_for_finalization = False

    def replace_origin():
        with Session() as concurrent:
            concurrent.execute(text("PRAGMA busy_timeout=100"))
            concurrent.add(GameState(game_id=ids[1], week=0, age=28, state_json={
                "character_settings": {"story_origin": {"revision": 2}}}))
            concurrent.commit()
            enqueue_candidate_batch(concurrent, ids[0], ids[1], "initial")

    def supersede_before_slot_count(execute_state):
        nonlocal superseded, supersession_waited_for_finalization
        if (superseded or current_thread() is not coordinator_thread
                or "portrait_candidate_slots" not in str(execute_state.statement)):
            return
        superseded = True
        try:
            replace_origin()
        except OperationalError:
            # The coordinator's game-row write lock correctly makes this
            # update wait until after its terminal commit.
            supersession_waited_for_finalization = True

    event.listen(Session.class_, "do_orm_execute", supersede_before_slot_count)
    try:
        run_candidate_batch(ids[2], session_factory=Session, image_service_factory=fake_provider)
    finally:
        event.remove(Session.class_, "do_orm_execute", supersede_before_slot_count)

    assert superseded
    if supersession_waited_for_finalization:
        replace_origin()
    with Session() as db:
        old = db.get(PortraitImageGenerationJob, ids[2])
        if supersession_waited_for_finalization:
            assert old.status == "succeeded"
            assert candidate_batch_state(db, ids[1], ids[0]).origin_revision == 2
        else:
            assert old.status == "failed"
            assert old.error_code == "story_origin_superseded"


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
    assert sorted(fake_provider.generated_slot_indices) == [0, 1, 1, 2]
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
    assert sorted(fake_provider.generated_slot_indices) == [1, 2]
    with Session() as db:
        assert db.get(Image, image_id).is_active


def test_stale_origin_during_provider_does_not_activate(batch_setup, fake_provider):
    Session, ids = batch_setup
    from threading import Event
    all_images_saved = Barrier(3, timeout=5)
    origin_updated = Event()
    deleted_paths = []

    class StaleProvider(fake_provider):
        def generate_character_candidate(self, **kwargs):
            image = super().generate_character_candidate(**kwargs)
            all_images_saved.wait()
            if kwargs["slot_index"] == 0:
                self.db.add(GameState(game_id=ids[1], week=0, age=28,
                    state_json={"character_settings": {"story_origin": {"revision": 2}}}))
                self.db.commit()
                origin_updated.set()
            else:
                assert origin_updated.wait(timeout=5)
            return image

        def delete_image_files(self, images):
            deleted_paths.extend(image.storage_path for image in images)

    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=StaleProvider)
    with Session() as db:
        assert db.query(Image).filter_by(is_active=True).count() == 0
        assert db.query(Image).count() == 0
        assert db.get(PortraitSelection, ids[1]) is None
        assert db.get(PortraitImageGenerationJob, ids[2]).error_code == "story_origin_superseded"
    assert sorted(fake_provider.generated_slot_indices) == [0, 1, 2]
    assert sorted(deleted_paths) == ["candidate-0.png", "candidate-1.png", "candidate-2.png"]


def test_stale_cleanup_preserves_a_deactivated_but_selected_ready_slot(batch_setup, fake_provider):
    from src.services.portrait_candidate_jobs import _discard_stale_candidate_images

    Session, ids = batch_setup
    deleted_paths = []

    class StorageAwareProvider(fake_provider):
        def delete_image_files(self, images):
            deleted_paths.extend(image.storage_path for image in images)

    with Session() as db:
        batch = db.query(PortraitCandidateBatch).filter_by(job_id=ids[2]).one()
        ready = Image(game_id=ids[1], image_type="character", entity_key="player_main",
                      entity_name="林见微", prompt_text="ready", storage_path="ready.png",
                      is_active=False, metadata_json={"batch_id": batch.batch_id, "slot_index": 0})
        unused = Image(game_id=ids[1], image_type="character", entity_key="player_main",
                       entity_name="林见微", prompt_text="unused", storage_path="unused.png",
                       is_active=False, metadata_json={"batch_id": batch.batch_id, "slot_index": 1})
        db.add_all([ready, unused])
        db.flush()
        slot = db.get(PortraitCandidateSlot, (batch.batch_id, 0))
        slot.status, slot.image_id = "ready", ready.image_id
        db.get(PortraitImageGenerationJob, ids[2]).image_id = ready.image_id
        db.add(PortraitSelection(game_id=ids[1], image_id=ready.image_id,
                                 is_user_selected=True))
        db.commit()
        ready_id, unused_id = ready.image_id, unused.image_id

    with Session() as db:
        batch = db.query(PortraitCandidateBatch).filter_by(job_id=ids[2]).one()
        _discard_stale_candidate_images(db, batch, StorageAwareProvider)
        assert db.get(Image, ready_id) is not None
        assert db.get(Image, unused_id) is None
        assert db.get(PortraitCandidateSlot, (batch.batch_id, 0)).image_id == ready_id
        assert db.get(PortraitSelection, ids[1]).image_id == ready_id
    assert deleted_paths == ["unused.png"]


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
    assert sorted(fake_provider.generated_slot_indices) == [0, 1, 2]


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
    assert sorted(fake_provider.generated_slot_indices) == [0, 1, 1, 2]
    with Session() as db:
        assert candidate_batch_state(db, ids[1], ids[0]).status == "succeeded"

# Feedback edits use the real durable worker; only the paid provider is faked.
from src.services.portrait_image_jobs import PortraitImageJobService, run_portrait_image_job


@pytest.fixture
def ready_three_slot_batch(batch_setup, fake_provider, tmp_path):
    Session, ids = batch_setup
    run_candidate_batch(ids[2], session_factory=Session, image_service_factory=fake_provider)
    with Session() as db:
        for image in db.query(Image):
            path = tmp_path / f'{image.image_id}.png'
            path.write_bytes(b'original')
            image.storage_path = str(path)
        db.commit()
    return Session, ids


def enqueue_feedback_job(db, source_id):
    source = db.get(Image, source_id)
    return PortraitImageJobService(db).enqueue(db.get(Game, source.game_id).user_id, {
        'game_id': source.game_id, 'operation': 'regenerate',
        'source_image_id': source_id, 'feedback': '换一件明代衣服',
    })[0].job_id


def finish_feedback_job(Session, job_id, callback=None, fail=False):
    class EditProvider:
        def __init__(self, db):
            self.db = db
        def regenerate_image(self, **kwargs):
            source = self.db.get(Image, kwargs['image_id'])
            if callback:
                callback(self.db, source)
            if fail:
                raise RuntimeError('provider failure')
            image = Image(game_id=source.game_id, image_type='character', entity_key='player_main',
                          entity_name=source.entity_name, prompt_text='edited',
                          storage_path=source.storage_path + '.new', is_active=False)
            self.db.add(image)
            self.db.commit()
            return [image]
        def delete_image_files(self, images):
            from pathlib import Path
            for image in images:
                Path(image.storage_path).unlink(missing_ok=True)
    run_portrait_image_job(job_id, session_factory=Session, image_service_factory=EditProvider)


def complete_feedback_job(Session, source_id):
    with Session() as db:
        job_id = enqueue_feedback_job(db, source_id)
    finish_feedback_job(Session, job_id)
    return job_id


def test_feedback_replaces_only_target_slot(ready_three_slot_batch):
    Session, ids = ready_three_slot_batch
    with Session() as db:
        source_id = selected_portrait(db, ids[1]).image_id
        others = [i.image_id for i in db.query(Image) if i.image_id != source_id]
    job_id = complete_feedback_job(Session, source_id)
    with Session() as db:
        job = db.get(PortraitImageGenerationJob, job_id)
        assert job.status == 'succeeded'
        assert all(db.get(Image, i).is_active for i in others)
        assert selected_portrait(db, ids[1]).image_id == job.image_id
        assert db.query(PortraitCandidateSlot).filter_by(image_id=job.image_id, status='ready').count() == 1


def test_selection_changed_during_edit_is_not_stolen(ready_three_slot_batch):
    Session, ids = ready_three_slot_batch
    with Session() as db:
        source_id = selected_portrait(db, ids[1]).image_id
        other_id = db.query(Image).filter(Image.image_id != source_id).first().image_id
        pending = enqueue_feedback_job(db, source_id)
    finish_feedback_job(Session, pending, lambda db, source: select_portrait(db, ids[1], other_id))
    with Session() as db:
        assert selected_portrait(db, ids[1]).image_id == other_id
        assert db.get(Image, other_id).is_active


@pytest.mark.parametrize('supersede', [False, True])
def test_failed_or_superseded_edit_preserves_source(ready_three_slot_batch, supersede):
    from pathlib import Path
    Session, ids = ready_three_slot_batch
    with Session() as db:
        source = selected_portrait(db, ids[1])
        source_id, source_path = source.image_id, source.storage_path
        pending = enqueue_feedback_job(db, source_id)
    def change_origin(db, source):
        db.add(GameState(game_id=ids[1], week=0, age=28,
                         state_json={'character_settings': {'story_origin': {'revision': 2}}}))
        db.commit()
    finish_feedback_job(Session, pending, change_origin if supersede else None, fail=not supersede)
    with Session() as db:
        assert selected_portrait(db, ids[1]).image_id == source_id
        assert db.query(PortraitCandidateSlot).filter_by(image_id=source_id, status='ready').count() == 1
        assert Path(source_path).exists()


def test_feedback_does_not_reuse_unrelated_candidate_job(ready_three_slot_batch):
    Session, ids = ready_three_slot_batch
    with Session() as db:
        staged = enqueue_candidate_batch(db, ids[0], ids[1], 'fresh')
        source_id = selected_portrait(db, ids[1]).image_id
        edit_id = enqueue_feedback_job(db, source_id)
        assert edit_id != staged.job_id
        assert enqueue_feedback_job(db, source_id) == edit_id


@pytest.mark.parametrize('failures', [{0, 1, 2}, {1}])
def test_fresh_batch_keeps_choice_and_retries_only_missing(ready_three_slot_batch, fake_provider, failures, monkeypatch):
    Session, ids = ready_three_slot_batch
    with Session() as db:
        old = selected_portrait(db, ids[1]).image_id
        fresh_id = enqueue_candidate_batch(db, ids[0], ids[1], 'fresh').job_id
        assert selected_portrait(db, ids[1]).image_id == old
    fake_provider.generated_slot_indices.clear()
    fake_provider.fail = failures
    run_candidate_batch(fresh_id, session_factory=Session, image_service_factory=fake_provider)
    with Session() as db:
        state = candidate_batch_state(db, ids[1], ids[0])
        assert state.selected_image_id == old
        ready = [s.image_id for s in state.slots if s.status == 'ready']
        if ready:
            monkeypatch.setattr('src.services.portrait_selection.ImageStorageService.get_image_data', lambda *a: b'image')
            select_portrait(db, ids[1], ready[0])
        retry_candidate_batch(db, state.batch_id, ids[0])
    fake_provider.fail = set()
    run_candidate_batch(fresh_id, session_factory=Session, image_service_factory=fake_provider)
    assert sorted(fake_provider.generated_slot_indices) == sorted([0, 1, 2] + list(failures))


def test_source_slot_changed_during_edit_is_not_overwritten(ready_three_slot_batch):
    from pathlib import Path
    Session, ids = ready_three_slot_batch
    with Session() as db:
        source = selected_portrait(db, ids[1])
        source_id, path = source.image_id, source.storage_path
        pending = enqueue_feedback_job(db, source_id)
    def replace_slot(db, source):
        slot = db.query(PortraitCandidateSlot).filter_by(image_id=source.image_id).one()
        other = db.query(Image).filter(Image.image_id != source.image_id).first()
        slot.image_id = other.image_id
        db.commit()
    finish_feedback_job(Session, pending, replace_slot)
    with Session() as db:
        job = db.get(PortraitImageGenerationJob, pending)
        assert job.status == 'failed'
        assert job.error_code == 'portrait_source_superseded'
        assert db.get(Image, source_id).is_active
        assert Path(path).exists()


def test_legacy_edit_preserves_staged_candidates(ready_three_slot_batch):
    Session, ids = ready_three_slot_batch
    with Session() as db:
        ready_ids = [i.image_id for i in db.query(Image)]
        legacy = Image(game_id=ids[1], image_type='character', entity_key='player_main',
                       entity_name='legacy', prompt_text='legacy', storage_path='legacy.png',
                       is_primary=True, is_active=True)
        db.add(legacy)
        db.flush()
        db.get(PortraitSelection, ids[1]).image_id = legacy.image_id
        db.commit()
        source_id = legacy.image_id
    pending = complete_feedback_job(Session, source_id)
    with Session() as db:
        assert all(db.get(Image, image_id).is_active for image_id in ready_ids)
        assert selected_portrait(db, ids[1]).image_id == db.get(PortraitImageGenerationJob, pending).image_id


def test_feedback_route_rejects_unselected_candidate(ready_three_slot_batch):
    from src.api.routers.images import _enqueue_main_portrait_regeneration
    Session, ids = ready_three_slot_batch
    with Session() as db:
        selected_id = selected_portrait(db, ids[1]).image_id
        other = db.query(Image).filter(Image.image_id != selected_id).first()
        with pytest.raises(HTTPException) as rejected:
            _enqueue_main_portrait_regeneration(db, ids[0], other.image_id, 'regenerate', '短发')
        assert rejected.value.status_code == 422
        assert db.query(PortraitImageGenerationJob).count() == 1


def test_selection_revalidates_after_feedback_replaces_source(ready_three_slot_batch, monkeypatch):
    from threading import Event
    Session, ids = ready_three_slot_batch
    storage_started, replacement_finished = Event(), Event()
    with Session() as db:
        source_id = selected_portrait(db, ids[1]).image_id
        pending = enqueue_feedback_job(db, source_id)

    def blocking_read(*args, **kwargs):
        storage_started.set()
        assert replacement_finished.wait(timeout=5), 'feedback replacement did not finish'
        return b'image'

    monkeypatch.setattr('src.services.portrait_selection.ImageStorageService.get_image_data', blocking_read)

    def select_old_source():
        with Session() as db:
            try:
                select_portrait(db, ids[1], source_id)
            except ValueError:
                return 'rejected'
            return 'selected'

    with ThreadPoolExecutor(max_workers=1) as executor:
        selection = executor.submit(select_old_source)
        try:
            assert storage_started.wait(timeout=5), 'selection did not reach storage'
            finish_feedback_job(Session, pending)
        finally:
            replacement_finished.set()
        assert selection.result(timeout=5) == 'rejected'
    with Session() as db:
        job = db.get(PortraitImageGenerationJob, pending)
        row = db.get(PortraitSelection, ids[1])
        assert job.status == 'succeeded'
        assert row.image_id == job.image_id
        assert db.get(Image, row.image_id).is_active
        assert db.query(PortraitCandidateSlot).filter_by(image_id=row.image_id, status='ready').count() == 1


def test_get_portrait_selection_restores_legacy_choice_and_checks_owner(db_session):
    from src.api.routers.images import get_portrait_selection
    game = create_owned_game(db_session)
    assert get_portrait_selection(game.game_id, db_session, game.user_id) is None
    first, second = add_two_active_portraits(db_session, game.game_id)
    assert get_portrait_selection(game.game_id, db_session, game.user_id).image_id == first.image_id
    db_session.add(PortraitSelection(game_id=game.game_id, image_id=second.image_id, is_user_selected=True))
    db_session.commit()
    assert get_portrait_selection(game.game_id, db_session, game.user_id).image_id == second.image_id
    with pytest.raises(HTTPException) as exc:
        get_portrait_selection(game.game_id, db_session, game.user_id + 1)
    assert exc.value.status_code == 404


def test_get_portrait_selection_requires_authentication(client):
    assert client.get('/api/images/character/selection?game_id=1').status_code == 401


def test_default_repairs_inactive_selection_and_preserves_valid_user_choice(db_session):
    game = create_owned_game(db_session)
    old, replacement = add_two_active_portraits(db_session, game.game_id)
    old.is_active = False
    db_session.add(PortraitSelection(game_id=game.game_id, image_id=old.image_id, is_user_selected=True))
    db_session.commit()
    set_default_portrait(db_session, game.game_id, replacement.image_id)
    db_session.commit()
    assert selected_portrait(db_session, game.game_id).image_id == replacement.image_id
    row = db_session.get(PortraitSelection, game.game_id)
    assert row.image_id == replacement.image_id
    assert not row.is_user_selected
    row.is_user_selected = True
    old.is_active = True
    db_session.commit()
    set_default_portrait(db_session, game.game_id, old.image_id)
    assert row.image_id == replacement.image_id
    assert row.is_user_selected


def test_active_legacy_nonprimary_variant_can_be_selected(db_session, tmp_path):
    game = create_owned_game(db_session)
    _, variant = add_two_active_portraits(db_session, game.game_id)
    path = tmp_path / 'variant.png'
    path.write_bytes(b'image')
    variant.storage_path = str(path)
    db_session.commit()
    assert select_portrait(db_session, game.game_id, variant.image_id).image_id == variant.image_id
    assert selected_portrait(db_session, game.game_id).image_id == variant.image_id


def test_new_origin_batch_repairs_deactivated_selection(ready_three_slot_batch, fake_provider):
    Session, ids = ready_three_slot_batch
    with Session() as db:
        old_id = selected_portrait(db, ids[1]).image_id
        db.query(Image).filter_by(game_id=ids[1]).update({'is_active': False})
        db.add(GameState(game_id=ids[1], week=1, age=28, state_json={
            'character_settings': {'story_origin': {'revision': 2}, 'era': {'era_name': '明代'}}}))
        db.commit()
        new_job = enqueue_candidate_batch(db, ids[0], ids[1], 'initial').job_id
    run_candidate_batch(new_job, session_factory=Session, image_service_factory=fake_provider)
    with Session() as db:
        state = candidate_batch_state(db, ids[1], ids[0])
        assert state.completed_count == 3 and state.origin_revision == 2
        assert state.selected_image_id != old_id
        assert state.selected_image_id in [slot.image_id for slot in state.slots]
        assert selected_portrait(db, ids[1]).image_id == state.selected_image_id


def test_feedback_missing_reference_job_has_safe_actionable_error(ready_three_slot_batch):
    from src.services.image.character_service import CharacterImageService
    Session, ids = ready_three_slot_batch
    class BrokenReferenceService(CharacterImageService):
        def __init__(self, db):
            # Neither provider nor storage constructors are necessary for this failure.
            self.db = db
        def _get_image_data(self, original):
            raise OSError('private-storage-secret')
        def generate_character_image(self, **kwargs):
            pytest.fail('missing candidate reference must not call paid generation')
    with Session() as db:
        source = selected_portrait(db, ids[1])
        source_id = source.image_id
        job_id = enqueue_feedback_job(db, source_id)
    run_portrait_image_job(job_id, session_factory=Session, image_service_factory=BrokenReferenceService)
    with Session() as db:
        job = db.get(PortraitImageGenerationJob, job_id)
        assert job.status == 'failed'
        assert job.error_code == 'portrait_reference_unavailable'
        assert '参考图片' in job.error_message and '重试' in job.error_message
        assert 'private-storage-secret' not in job.error_message
        assert selected_portrait(db, ids[1]).image_id == source_id
        assert db.get(Image, source_id).is_active
