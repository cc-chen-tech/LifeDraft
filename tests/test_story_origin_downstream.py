"""Canonical-origin precedence in story and image generation contexts."""

from config.prompts._helpers import (
    _build_era_anachronism_constraints,
    _build_full_character_context,
)
from config.prompts.character_prompts import get_character_setting_prompt
from src.services.image_service import ImageService
import pytest

pytestmark = [pytest.mark.unit]



def _conflicting_settings():
    return {
        "story_origin": {
            "revision": 2,
            "start_date": "2026-08-13",
            "starting_age": 28,
            "era_description": "2020年代中期的现代都市",
            "life_stage_description": "职业发展逐渐进入稳定探索期",
            "world_context": "AI工具与数字内容行业快速变化",
        },
        "era": {
            "year": 960,
            "era_name": "北宋",
            "era_description": "公元960年的北宋州城",
            "world_context": "宋初社会",
        },
        "age": {"age": 20, "age_description": "初入成年"},
        "gender": {"gender": "女性"},
    }


def test_story_context_uses_origin_instead_of_conflicting_legacy_projections():
    context, _ = _build_full_character_context(_conflicting_settings(), "zh")

    assert "2026年" in context
    assert "28岁" in context
    assert "2020年代中期的现代都市" in context
    assert "960" not in context
    assert "20岁" not in context


def test_world_generation_prompt_cannot_reintroduce_old_era_fields():
    prompt = get_character_setting_prompt(
        "world", "阿衡", "建立现代AI教育公司", _conflicting_settings(), "zh"
    )

    assert "2026-08-13" in prompt
    assert "2020年代中期的现代都市" in prompt
    assert "公元960年的北宋州城" not in prompt


def test_anachronism_and_portrait_context_both_prefer_origin():
    constraints = _build_era_anachronism_constraints(_conflicting_settings(), "zh")
    service = object.__new__(ImageService)
    char_info = service._build_char_info(_conflicting_settings(), "阿衡")

    assert "现代" in constraints
    assert "古代/前现代" not in constraints
    assert char_info["age"] == 28
    assert "2020年代中期" in char_info["era"]
