"""Contracts for atomically rebasing an unplayed draft onto a new origin."""

from copy import deepcopy

import pytest

from src.database.models import Game, User
from src.game.story_origin import (
    StoryOriginLocked,
    StoryOriginRevisionConflict,
    rebase_draft_story_origin,
)


def _origin(*, revision: int = 1, start_date: str = "0960-03-12", age: int = 20):
    return {
        "revision": revision,
        "start_date": start_date,
        "starting_age": age,
        "era_description": "北宋初年的州城",
        "life_stage_description": "初入成年的人生阶段",
        "world_context": "驿路与坊市连接着地方社会",
    }


def _draft_state():
    return {
        "player_name": "阿衡",
        "life_vision": "亲手建立一项长久的事业",
        "age": 20,
        "week": 0,
        "current_round": 0,
        "timeline_version": 2,
        "timeline": {
            "version": 2,
            "start_date": "0960-03-12",
            "day_index": 0,
        },
        "day_history": [],
        "next_age_day": 365,
        "character_settings": {
            "story_origin": _origin(),
            "start_date": "0960-03-12",
            "era": {"year": 960, "era_description": "旧时代"},
            "age": {"age": 20, "birth_year": 940},
            "gender": {"gender": "female"},
            "world": {"description": "旧世界"},
            "family": {"family_background": "旧家庭"},
            "relationships": {"key_people": [{"name": "旧友"}]},
            "traits": {"personality": ["谨慎"]},
            "appearance": {"description": "旧形象"},
            "narrative_style_id": "auto-old-style",
            "constraint_level": "expert",
        },
        "relationships": {"旧友": 70},
        "characters": {"旧友": {"name": "旧友"}},
        "scheduled_events": [{"description": "旧约定"}],
        "narrative_style_id": "auto-old-style",
    }


def test_rebase_replaces_origin_and_invalidates_every_dependent_setting():
    original = _draft_state()
    snapshot = deepcopy(original)
    candidate = {
        **_origin(revision=99, start_date="2026-08-13", age=28),
        "era_description": "2020年代中期的现代都市",
        "life_stage_description": "职业发展逐渐进入稳定探索期",
        "world_context": "AI工具与数字内容行业快速变化",
    }

    updated = rebase_draft_story_origin(original, candidate, expected_revision=1)

    assert original == snapshot
    assert updated["character_settings"]["story_origin"]["revision"] == 2
    assert updated["timeline"]["start_date"] == "2026-08-13"
    assert updated["timeline"]["current_date"] == "2026-08-13"
    assert updated["timeline"]["day_index"] == 0
    assert updated["age"] == 28
    assert updated["next_age_day"] == 365
    assert updated["character_settings"]["gender"] == {"gender": "female"}
    assert updated["player_name"] == "阿衡"
    assert updated["life_vision"] == "亲手建立一项长久的事业"

    for key in ("world", "family", "relationships", "traits", "appearance"):
        assert key not in updated["character_settings"]
    assert "narrative_style_id" not in updated["character_settings"]
    assert updated["relationships"] == {}
    assert updated["characters"] == {}
    assert updated["scheduled_events"] == []
    assert updated["narrative_style_id"] is None


def test_rebase_rejects_stale_expected_revision_without_mutation():
    state = _draft_state()
    snapshot = deepcopy(state)

    with pytest.raises(StoryOriginRevisionConflict):
        rebase_draft_story_origin(state, _origin(), expected_revision=7)

    assert state == snapshot


@pytest.mark.parametrize(
    "played_patch",
    [
        {"timeline": {"version": 2, "start_date": "0960-03-12", "day_index": 1}},
        {"day_history": [{"day_index": 0}]},
        {"current_event_data": {"event_id": "day:0", "revision": 1}},
    ],
)
def test_rebase_is_permanently_locked_once_day_one_exists(played_patch):
    state = _draft_state()
    state.update(played_patch)

    with pytest.raises(StoryOriginLocked):
        rebase_draft_story_origin(state, _origin(), expected_revision=1)


@pytest.mark.integration
def test_rebased_origin_round_trips_through_real_json_database(db_session):
    user = User(private_id="ORIGIN-DRAFT", public_id="ORIGIN1")
    db_session.add(user)
    db_session.commit()
    game = Game(user_id=user.user_id, language="zh", initial_state=_draft_state())
    db_session.add(game)
    db_session.commit()

    stored = deepcopy(game.initial_state)
    updated = rebase_draft_story_origin(
        stored,
        _origin(start_date="2026-08-13", age=28),
        expected_revision=1,
    )
    game.initial_state = updated
    db_session.commit()
    db_session.expire_all()

    loaded = db_session.query(Game).filter(Game.game_id == game.game_id).one()
    assert loaded.initial_state["character_settings"]["story_origin"]["revision"] == 2
    assert loaded.initial_state["timeline"]["current_date"] == "2026-08-13"
    assert loaded.initial_state["age"] == 28
    assert "world" not in loaded.initial_state["character_settings"]
