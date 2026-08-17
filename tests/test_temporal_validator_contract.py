"""Temporal validator contract tests.

No mocks. Pure logic tests for time consistency validation.
"""

from src.ai.harness.temporal_validator import (TemporalConsistencyValidator,
                                               _chinese_to_int,
                                               validate_temporal_consistency)
import pytest

pytestmark = [pytest.mark.unit]



class TestChineseToIntContract:
    """Contract tests for _chinese_to_int."""

    def test_single_digit(self):
        assert _chinese_to_int("三") == 3

    def test_two_digits(self):
        assert _chinese_to_int("三十五") == 35

    def test_with_ten(self):
        assert _chinese_to_int("二十") == 20

    def test_with_two(self):
        assert _chinese_to_int("两") == 2

    def test_hundred(self):
        assert _chinese_to_int("一百") == 100

    def test_empty(self):
        assert _chinese_to_int("") == 0


class TestTemporalConsistencyValidatorContract:
    """Contract tests for TemporalConsistencyValidator."""

    def test_extract_time_references(self):
        text = "昨天我去了学校，今年我要努力学习。"
        validator = TemporalConsistencyValidator()
        refs = validator.extract_time_references(text)
        types = [r["type"] for r in refs]
        assert "yesterday" in types
        assert "this_year" in types

    def test_check_season_consistency_spring(self):
        validator = TemporalConsistencyValidator()
        ok, info = validator.check_season_consistency("春暖花开", current_week=2)
        assert ok is True
        assert info["current_season"] == "春"

    def test_check_season_consistency_conflict(self):
        validator = TemporalConsistencyValidator()
        ok, info = validator.check_season_consistency("大雪纷飞", current_week=2)
        assert ok is False
        assert "大雪纷飞" in info["conflicts"]

    def test_check_season_consistency_flashback_exempt(self):
        validator = TemporalConsistencyValidator()
        ok, info = validator.check_season_consistency("回忆中大雪纷飞", current_week=2)
        assert ok is True  # flashback exempts

    def test_check_character_age_exact(self):
        validator = TemporalConsistencyValidator()
        ok, info = validator.check_character_age("他今年25岁", age=25)
        assert ok is True
        assert 25 in info["mentioned_ages"]

    def test_check_character_age_off_by_one_ok(self):
        validator = TemporalConsistencyValidator()
        ok, info = validator.check_character_age("他今年26岁", age=25)
        assert ok is True  # within +/- 1 tolerance

    def test_check_character_age_inconsistent(self):
        validator = TemporalConsistencyValidator()
        ok, info = validator.check_character_age("他今年30岁", age=25)
        assert ok is False
        assert 30 in info["inconsistent_ages"]

    def test_check_character_age_chinese(self):
        validator = TemporalConsistencyValidator()
        ok, info = validator.check_character_age("他今年三十五岁", age=35)
        assert ok is True
        assert 35 in info["mentioned_ages"]

    def test_get_season_spring(self):
        assert TemporalConsistencyValidator._get_season(2) == "春"

    def test_get_season_summer(self):
        assert TemporalConsistencyValidator._get_season(15) == "夏"

    def test_get_season_autumn(self):
        assert TemporalConsistencyValidator._get_season(30) == "秋"

    def test_get_season_winter(self):
        assert TemporalConsistencyValidator._get_season(40) == "冬"

    def test_get_season_cross_year(self):
        assert TemporalConsistencyValidator._get_season(48 + 5) == "春"

    def test_validate_passes(self):
        validator = TemporalConsistencyValidator()
        ok, evidence, details = validator.validate(
            "今天天气很好", context={"player_state": {"week": 2, "age": 25}}
        )
        assert ok is True
        assert details["season_check"]["current_season"] == "春"

    def test_validate_fails_season(self):
        validator = TemporalConsistencyValidator()
        ok, evidence, details = validator.validate(
            "冰天雪地", context={"player_state": {"week": 2, "age": 25}}
        )
        assert ok is False
        assert "季节" in evidence or "时间" in evidence

    def test_validate_fails_age(self):
        validator = TemporalConsistencyValidator()
        ok, evidence, details = validator.validate(
            "他今年50岁", context={"player_state": {"week": 2, "age": 25}}
        )
        assert ok is False
        assert "50" in evidence or "年龄" in evidence

    def test_module_level_function(self):
        ok, evidence, details = validate_temporal_consistency("今天", context={})
        assert ok is True
