import pytest

from config.feature_flags import get_feature, reset_features, set_feature
from src.ai.generation_budget import get_daily_generation_budget
from src.game.daily_timeline import (
    DAILY_TIMELINE_TOTAL_DAYS,
    advance_daily_timeline,
    build_daily_timeline,
    migrate_legacy_state,
    resolve_scheduled_date,
)
from src.game.state import PlayerState
from src.game.scheduled_events import ScheduledEvent
from src.game.game_initializer import GameInitializer
from src.game.world_model_updater import WorldModelUpdater

pytestmark = [pytest.mark.unit]



@pytest.fixture(autouse=True)
def _reset_feature_flags() -> None:
    reset_features()
    yield
    reset_features()


@pytest.mark.parametrize(
    ("level", "expected_range"),
    [
        ("fast", (350, 500)),
        ("expert", (500, 800)),
        ("master", (800, 1200)),
        ("unknown", (500, 800)),
    ],
)
def test_daily_story_generation_budgets(
    level: str, expected_range: tuple[int, int]
) -> None:
    budget = get_daily_generation_budget(level)

    assert (budget.min_length, budget.max_length) == expected_range


@pytest.mark.parametrize(
    ("start_date", "day_index", "expected"),
    [
        ("2024-02-28", 1, "2024-02-29"),
        ("2024-02-28", 2, "2024-03-01"),
        ("2023-12-31", 1, "2024-01-01"),
    ],
)
def test_timeline_uses_real_gregorian_dates(
    start_date: str, day_index: int, expected: str
) -> None:
    timeline = build_daily_timeline(start_date=start_date, day_index=day_index)

    assert timeline["current_date"] == expected


def test_timeline_serializes_complete_public_progress() -> None:
    timeline = build_daily_timeline(start_date="2026-08-13", day_index=0)

    assert timeline == {
        "version": 2,
        "start_date": "2026-08-13",
        "current_date": "2026-08-13",
        "day_index": 0,
        "day_number": 1,
        "completed_days": 0,
        "week_number": 1,
        "weekday": 4,
        "total_days": 672,
    }


def test_advancing_day_365_increments_age_once() -> None:
    state = {
        "timeline": build_daily_timeline(start_date="2024-01-01", day_index=364),
        "age": 22,
        "next_age_day": 365,
    }

    result = advance_daily_timeline(state)

    assert result["day_index"] == 365
    assert state["age"] == 23
    assert state["next_age_day"] == 730


def test_day_672_finishes_without_advancing_to_day_673() -> None:
    state = {
        "timeline": build_daily_timeline(
            start_date="2024-01-01", day_index=DAILY_TIMELINE_TOTAL_DAYS - 1
        ),
        "age": 22,
        "next_age_day": 730,
    }

    result = advance_daily_timeline(state)

    assert result["day_index"] == DAILY_TIMELINE_TOTAL_DAYS
    assert result["completed_days"] == DAILY_TIMELINE_TOTAL_DAYS
    assert result["game_over"] is True


def test_player_state_reports_game_over_after_day_672() -> None:
    state = PlayerState(
        timeline=build_daily_timeline(
            start_date="2024-01-01", day_index=DAILY_TIMELINE_TOTAL_DAYS
        ),
        timeline_version=2,
    )

    assert state.is_game_over() is True


def test_invalid_start_date_is_rejected() -> None:
    with pytest.raises(ValueError, match="start_date"):
        build_daily_timeline(start_date="2023-02-29", day_index=0)


def test_legacy_history_maps_to_first_monday_wednesday_and_sunday() -> None:
    legacy = {
        "week": 0,
        "current_round": 2,
        "age": 22,
        "character_settings": {"era": {"year": 2026}},
        "round_history": [
            {"week": 0, "round": 0, "event_description": "周一", "choice": "A"},
            {"week": 0, "round": 1, "event_description": "周中", "choice": "B"},
            {"week": 0, "round": 2, "event_description": "周末", "choice": "C"},
        ],
    }

    migrated = migrate_legacy_state(legacy)

    assert migrated["timeline"]["start_date"] == "2026-01-05"
    assert [entry["story_date"] for entry in migrated["day_history"]] == [
        "2026-01-05",
        "2026-01-07",
        "2026-01-11",
    ]
    assert migrated["timeline"]["current_date"] == "2026-01-12"


def test_pending_legacy_event_keeps_current_mapped_date() -> None:
    legacy = {
        "week": 1,
        "current_round": 1,
        "age": 22,
        "character_settings": {"era": {"year": 2024}},
        "round_history": [],
        "current_event_data": {"event_description": "尚未选择", "options": []},
    }

    migrated = migrate_legacy_state(legacy)

    assert migrated["timeline"]["current_date"] == "2024-01-10"
    assert migrated["current_event_data"]["story_date"] == "2024-01-10"
    assert migrated["current_event_data"]["event_id"] == "day:9"
    assert migrated["current_event_data"]["revision"] == 1


def test_legacy_migration_is_idempotent() -> None:
    legacy = {
        "week": 2,
        "current_round": 0,
        "age": 23,
        "character_settings": {"era": {"year": 2025}},
        "round_history": [{"week": 1, "round": 2, "event_description": "旧故事"}],
    }

    once = migrate_legacy_state(legacy)
    twice = migrate_legacy_state(once)

    assert twice == once


def test_legacy_migration_preserves_event_and_result_prose() -> None:
    migrated = migrate_legacy_state(
        {
            "character_settings": {"era": {"year": 2026}},
            "round_history": [
                {
                    "week": 0,
                    "round": 0,
                    "event_description": "事件正文",
                    "story_continuation": "选择结果续文",
                    "choice": "选择 A",
                }
            ],
        }
    )

    record = migrated["day_history"][0]
    assert record["event_description"] == "事件正文\n\n选择结果续文"
    assert record["legacy_event_description"] == "事件正文"
    assert record["legacy_story_continuation"] == "选择结果续文"


def test_daily_timeline_feature_flag_defaults_off_and_can_be_enabled() -> None:
    assert get_feature("daily_timeline_v2") is False

    set_feature("daily_timeline_v2", True)
    assert get_feature("daily_timeline_v2") is True


def test_player_state_load_migrates_legacy_save_only_when_flag_enabled() -> None:
    legacy = {
        "age": 22,
        "week": 1,
        "current_round": 2,
        "character_settings": {"era": {"year": 2026}},
    }

    disabled = PlayerState.from_dict(legacy)
    assert disabled.timeline is None

    set_feature("daily_timeline_v2", True)
    enabled = PlayerState.from_dict(legacy)
    assert enabled.timeline is not None
    assert enabled.timeline["current_date"] == "2026-01-18"


def test_legacy_scheduled_event_is_migrated_to_exact_date() -> None:
    legacy = {
        "week": 0,
        "current_round": 0,
        "character_settings": {"era": {"year": 2026}},
        "scheduled_events": [
            {
                "event_id": "promise-1",
                "scheduled_week": 1,
                "scheduled_round": 1,
                "status": "pending",
            }
        ],
    }

    migrated = migrate_legacy_state(legacy)

    assert migrated["scheduled_events"][0]["scheduled_date"] == "2026-01-14"


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("明天", "2026-08-14"),
        ("后天", "2026-08-15"),
        ("10天后", "2026-08-23"),
        ("下周一", "2026-08-17"),
        ("下周日", "2026-08-23"),
    ],
)
def test_relative_scheduling_uses_gregorian_calendar(
    phrase: str, expected: str
) -> None:
    assert resolve_scheduled_date("2026-08-13", phrase) == expected


def test_new_game_uses_selected_start_date_and_synchronizes_birth_year() -> None:
    set_feature("daily_timeline_v2", True)
    settings = {
        "start_date": "2028-02-29",
        "era": {"year": 2026, "era_description": "现代"},
        "age": {"age": 20, "birth_year": 2006},
    }

    loop, _ = GameInitializer(game_db=None).initialize_game_from_settings(
        settings, "林舟", "认真生活"
    )

    assert loop.player_state.timeline["current_date"] == "2028-02-29"
    assert loop.player_state.timeline["day_number"] == 1
    assert loop.player_state.character_settings["era"]["year"] == 2028
    assert loop.player_state.character_settings["age"]["birth_year"] == 2008


def test_new_daily_game_defaults_to_era_january_first() -> None:
    set_feature("daily_timeline_v2", True)

    loop, _ = GameInitializer(game_db=None).initialize_game_from_settings(
        {"era": {"year": 1899}, "age": {"age": 25}}, "顾清", "生活"
    )

    assert loop.player_state.timeline["start_date"] == "1899-01-01"


def test_daily_state_triggers_scheduled_events_by_exact_date() -> None:
    state = PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-13", day_index=2),
        timeline_version=2,
        scheduled_events=[
            ScheduledEvent(
                event_id="today", scheduled_date="2026-08-15", status="pending"
            ).to_dict(),
            ScheduledEvent(
                event_id="later", scheduled_date="2026-08-16", status="pending"
            ).to_dict(),
        ],
    )

    assert [item["event_id"] for item in state.get_pending_scheduled_events()] == [
        "today"
    ]


def test_daily_new_commitment_uses_exact_relative_date() -> None:
    state = PlayerState(
        timeline=build_daily_timeline(start_date="2026-08-13", day_index=0),
        timeline_version=2,
    )

    WorldModelUpdater.process_scheduled_events(
        state,
        [
            {
                "description": "明天去码头",
                "parties": ["林舟"],
                "time_reference": "明天",
                "scheduled_week": 0,
                "scheduled_round": 1,
            }
        ],
        current_round=0,
    )

    assert state.scheduled_events[0]["scheduled_date"] == "2026-08-14"
