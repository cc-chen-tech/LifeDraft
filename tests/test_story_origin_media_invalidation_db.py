"""Origin rebase persistence invalidates every origin-scoped media record."""

import pytest

from src.database.models import Game, GameState, Image, PortraitImageGenerationJob, User
from src.database.state_repository import StateRepository
from src.game.state import PlayerState
from src.game.story_origin import StoryOriginLocked, StoryOriginRevisionConflict

pytestmark = [pytest.mark.integration]



def _legacy_origin_state():
    return {
        "age": 20,
        "week": 0,
        "character_settings": {
            "story_origin": {
                "revision": 1,
                "start_date": "0960-01-01",
                "starting_age": 20,
                "era_description": "北宋初年的州城",
                "life_stage_description": "初入成年的人生阶段",
                "world_context": "驿路与坊市连接地方社会",
            }
        },
    }


def test_origin_snapshot_and_media_invalidation_commit_together(db_session):
    user = User(private_id="ORIGIN-MEDIA", public_id="ORGMED01")
    db_session.add(user)
    db_session.commit()
    game = Game(
        user_id=user.user_id,
        narrative_style_id="auto-old",
        initial_state=_legacy_origin_state(),
    )
    db_session.add(game)
    db_session.commit()
    image = Image(
        game_id=game.game_id,
        image_type="character",
        entity_name="阿衡",
        entity_key="player_main",
        prompt_text="旧提示词",
        storage_path="old.png",
        is_active=True,
    )
    job = PortraitImageGenerationJob(
        game_id=game.game_id,
        user_id=user.user_id,
        entity_key="player_main",
        request_json={"game_id": game.game_id, "origin_revision": 1},
        status="running",
    )
    db_session.add_all([image, job])
    db_session.commit()
    state = PlayerState.from_dict(
        {
            "age": 28,
            "week": 0,
            "timeline_version": 2,
            "timeline": {"version": 2, "start_date": "2026-08-13", "day_index": 0},
            "character_settings": {
                "story_origin": {
                    "revision": 2,
                    "start_date": "2026-08-13",
                    "starting_age": 28,
                    "era_description": "现代都市",
                    "life_stage_description": "职业探索期",
                    "world_context": "AI行业快速变化",
                }
            },
        }
    )

    StateRepository.save_story_origin_progress_in_session(
        db_session, int(game.game_id), int(user.user_id), state
    )
    db_session.expire_all()

    assert db_session.get(Image, image.image_id).is_active is False
    invalidated_job = db_session.get(PortraitImageGenerationJob, job.job_id)
    assert invalidated_job.status == "failed"
    assert invalidated_job.error_code == "story_origin_superseded"
    assert db_session.get(Game, game.game_id).narrative_style_id is None


def test_origin_commit_rechecks_expected_revision_before_any_write(db_session):
    user = User(private_id="ORIGIN-CAS", public_id="ORGCAS01")
    db_session.add(user)
    db_session.commit()
    game = Game(user_id=user.user_id, initial_state=_legacy_origin_state())
    db_session.add(game)
    db_session.commit()
    image = Image(
        game_id=game.game_id,
        image_type="character",
        entity_name="阿衡",
        entity_key="player_main",
        prompt_text="仍然有效的提示词",
        storage_path="still-valid.png",
        is_active=True,
    )
    db_session.add(image)
    db_session.commit()
    candidate = PlayerState.from_dict(
        {
            **_legacy_origin_state(),
            "age": 28,
            "character_settings": {
                "story_origin": {
                    "revision": 2,
                    "start_date": "2026-08-13",
                    "starting_age": 28,
                    "era_description": "2020年代中期的现代都市",
                    "life_stage_description": "职业发展逐渐进入稳定探索期",
                    "world_context": "AI工具与数字内容行业快速变化",
                }
            },
        }
    )

    with pytest.raises(StoryOriginRevisionConflict):
        StateRepository.save_story_origin_progress_in_session(
            db_session,
            int(game.game_id),
            int(user.user_id),
            candidate,
            expected_revision=0,
        )

    db_session.rollback()
    db_session.expire_all()
    assert db_session.query(GameState).filter_by(game_id=game.game_id).count() == 0
    assert db_session.get(Image, image.image_id).is_active is True


def test_origin_commit_rechecks_played_lock_after_candidate_generation(db_session):
    user = User(private_id="ORIGIN-LOCK", public_id="ORGLOCK1")
    db_session.add(user)
    db_session.commit()
    game = Game(user_id=user.user_id, initial_state=_legacy_origin_state())
    db_session.add(game)
    db_session.commit()

    played_state = {
        **_legacy_origin_state(),
        "current_event_data": {"event_id": "day:0", "revision": 1},
    }
    db_session.add(
        GameState(
            game_id=game.game_id,
            week=0,
            age=20,
            state_json=played_state,
        )
    )
    db_session.commit()
    candidate = PlayerState.from_dict(
        {
            **_legacy_origin_state(),
            "age": 28,
            "character_settings": {
                "story_origin": {
                    "revision": 2,
                    "start_date": "2026-08-13",
                    "starting_age": 28,
                    "era_description": "2020年代中期的现代都市",
                    "life_stage_description": "职业发展逐渐进入稳定探索期",
                    "world_context": "AI工具与数字内容行业快速变化",
                }
            },
        }
    )

    with pytest.raises(StoryOriginLocked):
        StateRepository.save_story_origin_progress_in_session(
            db_session,
            int(game.game_id),
            int(user.user_id),
            candidate,
            expected_revision=1,
        )

    db_session.rollback()
    assert db_session.query(GameState).filter_by(game_id=game.game_id).count() == 1
