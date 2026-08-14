from __future__ import annotations

import pytest

from src.game.story_origin import (
    normalize_legacy_story_origin,
    project_story_origin,
    validate_story_origin,
)


def _origin(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "revision": 1,
        "start_date": "2028-02-29",
        "starting_age": 20,
        "era_description": "2020年代末的现代都市",
        "life_stage_description": "刚刚进入职业探索期",
        "world_context": "数字内容与人工智能工具快速发展",
    }
    value.update(overrides)
    return value


def test_validate_story_origin_accepts_legal_leap_date_without_birth_year() -> None:
    result = validate_story_origin(_origin())

    assert result["start_date"] == "2028-02-29"
    assert result["starting_age"] == 20
    assert "birth_year" not in result


def test_validate_story_origin_rejects_invalid_gregorian_date() -> None:
    with pytest.raises(ValueError, match="invalid_story_origin_date"):
        validate_story_origin(_origin(start_date="2027-02-29"))


def test_validate_story_origin_enforces_explicit_feedback_date_and_age() -> None:
    with pytest.raises(ValueError, match="story_origin_feedback_mismatch"):
        validate_story_origin(
            _origin(start_date="2026-08-12", starting_age=27),
            explicit_constraints="改成2026年8月13日，28岁",
        )


def test_change_feedback_uses_the_requested_destination_not_the_old_values() -> None:
    result = validate_story_origin(
        _origin(
            start_date="2026-01-01",
            starting_age=28,
            era_description="2026年的现代都市",
        ),
        explicit_constraints="从960年、20岁改为2026年、28岁",
    )

    assert result["start_date"] == "2026-01-01"
    assert result["starting_age"] == 28


def test_candidate_text_cannot_keep_a_conflicting_old_numeric_era() -> None:
    with pytest.raises(ValueError, match="story_origin_text_time_conflict"):
        validate_story_origin(
            _origin(
                start_date="2026-01-01",
                starting_age=28,
                era_description="2020年代中期的现代都市",
                world_context="公元960年的都城仍以驿站传递消息",
            )
        )


@pytest.mark.parametrize(
    "old_era", ["1990年代的工业城市", "a mid-1990s industrial city"]
)
def test_candidate_text_cannot_keep_a_conflicting_old_decade(old_era: str) -> None:
    with pytest.raises(ValueError, match="story_origin_text_time_conflict"):
        validate_story_origin(
            _origin(
                start_date="2026-01-01",
                era_description=old_era,
            )
        )


def test_validate_story_origin_enforces_english_feedback_year_and_age() -> None:
    with pytest.raises(ValueError, match="story_origin_feedback_mismatch"):
        validate_story_origin(
            _origin(start_date="2025-01-01", starting_age=27),
            explicit_constraints="Please change it to year 2026, age 28.",
        )


def test_project_story_origin_derives_legacy_fields_without_mutating_origin() -> None:
    origin = _origin(
        start_date="2026-08-13",
        starting_age=28,
        era_description="2026年的上海数字内容行业",
        life_stage_description="职业发展进入稳定探索期",
    )

    settings = project_story_origin({"gender": {"gender": "女"}}, origin)

    assert settings["story_origin"] == origin
    assert settings["start_date"] == "2026-08-13"
    assert settings["era"]["year"] == 2026
    assert settings["age"] == {
        "age": 28,
        "birth_year": 1998,
        "age_description": "职业发展进入稳定探索期",
    }
    assert "birth_year" not in settings["story_origin"]


def test_legacy_origin_defaults_to_era_january_first() -> None:
    origin, needs_review = normalize_legacy_story_origin(
        {
            "era": {
                "year": 1899,
                "era_description": "十九世纪末的港口城市",
                "world_context": "航运和报业正在扩张",
            },
            "age": {"age": 25, "age_description": "青年"},
        }
    )

    assert origin["start_date"] == "1899-01-01"
    assert origin["starting_age"] == 25
    assert needs_review is False


def test_legacy_exact_date_wins_and_conflicting_narrative_requires_review() -> None:
    origin, needs_review = normalize_legacy_story_origin(
        {
            "start_date": "2026-08-13",
            "era": {
                "year": 1899,
                "era_description": "1899年的港口城市",
                "world_context": "旧报馆仍在扩张",
            },
            "age": {"age": 28, "age_description": "青年"},
        }
    )

    assert origin["start_date"] == "2026-08-13"
    assert origin["starting_age"] == 28
    assert needs_review is True
