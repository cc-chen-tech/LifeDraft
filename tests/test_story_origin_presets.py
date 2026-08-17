"""Preset compatibility contracts for canonical story origins."""

from src.game.story_origin import normalize_preset_story_origin
import pytest

pytestmark = [pytest.mark.unit]



def test_legacy_preset_prefers_legal_start_date_and_marks_era_conflict():
    normalized = normalize_preset_story_origin(
        {
            "start_date": "2026-08-13",
            "era": {
                "year": 960,
                "era_description": "公元960年的北宋州城",
                "world_context": "宋初社会",
            },
            "age": {"age": 28, "age_description": "事业探索期"},
            "gender": {"gender": "female"},
        }
    )

    assert normalized["story_origin"]["start_date"] == "2026-08-13"
    assert normalized["story_origin"]["starting_age"] == 28
    assert normalized["story_origin_needs_review"] is True
    assert normalized["gender"] == {"gender": "female"}


def test_legacy_preset_without_date_uses_era_year_january_first():
    normalized = normalize_preset_story_origin(
        {
            "era": {"year": 960, "era_description": "北宋初年"},
            "age": {"age": 20},
        }
    )

    assert normalized["story_origin"]["start_date"] == "0960-01-01"
    assert normalized["start_date"] == "0960-01-01"
    assert normalized["age"]["birth_year"] == 940
    assert normalized.get("story_origin_needs_review") is None


def test_canonical_preset_is_saved_with_read_only_compatibility_projection():
    normalized = normalize_preset_story_origin(
        {
            "story_origin": {
                "revision": 3,
                "start_date": "2024-02-29",
                "starting_age": 28,
                "era_description": "2020年代中期的现代都市",
                "life_stage_description": "职业稳定探索期",
                "world_context": "AI工具快速变化",
            },
            "gender": {"gender": "male"},
        }
    )

    assert normalized["story_origin"]["revision"] == 3
    assert normalized["era"]["year"] == 2024
    assert normalized["age"]["age"] == 28
    assert normalized["age"]["birth_year"] == 1996
    assert "birth_year" not in normalized["story_origin"]
