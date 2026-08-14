from __future__ import annotations

import pytest

from src.game.game_initializer import GameInitializer


def test_initializer_projects_only_the_canonical_origin_time() -> None:
    normalized = GameInitializer._normalize_daily_start_date(
        {
            "story_origin": {
                "revision": 2,
                "start_date": "2026-08-13",
                "starting_age": 28,
                "era_description": "2020年代中期的现代都市",
                "life_stage_description": "职业发展逐渐进入稳定探索期",
                "world_context": "AI工具与数字内容行业快速变化",
            },
            "start_date": "0960-01-01",
            "era": {"year": 960, "era_name": "北宋", "era_description": "公元960年"},
            "age": {"age": 20, "birth_year": 940},
        }
    )

    assert normalized["start_date"] == "2026-08-13"
    assert normalized["era"]["year"] == 2026
    assert "era_name" not in normalized["era"]
    assert normalized["age"]["age"] == 28
    assert normalized["age"]["birth_year"] == 1998


def test_initializer_rejects_a_conflicting_legacy_origin() -> None:
    with pytest.raises(ValueError, match="story_origin_needs_review"):
        GameInitializer._normalize_daily_start_date(
            {
                "start_date": "2026-08-13",
                "era": {
                    "year": 960,
                    "era_description": "公元960年的都城",
                    "world_context": "驿站承担远途通信",
                },
                "age": {"age": 20, "age_description": "青年"},
            }
        )
