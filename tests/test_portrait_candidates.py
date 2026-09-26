"""Persistence and legacy selection contracts for protagonist portraits."""

from sqlalchemy.exc import IntegrityError
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
from src.services.portrait_selection import selected_portrait, set_default_portrait

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
