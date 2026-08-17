"""No-provider contracts for deterministic image prompt fallbacks."""

from src.ai.image_prompt_builder import DeepSeekPromptEnhancer, ImagePromptBuilder
import pytest

pytestmark = [pytest.mark.unit]



def test_era_sanitization_falls_back_when_only_scifi_visual_cues_remain() -> None:
    builder = ImagePromptBuilder()

    assert builder._sanitize_era_for_image("") == "现代"
    safe = builder._sanitize_era_for_image("2028年中国，AI、全息投影与霓虹")
    assert "AI" not in safe and "全息投影" not in safe and "霓虹" not in safe
    assert "2028" in safe


def test_default_character_prompt_keeps_realistic_full_body_composition() -> None:
    prompt = ImagePromptBuilder().build_character_prompt(
        name="林岚", description="短发建筑师", era="1990年代上海"
    )

    assert "【人物】林岚" in prompt
    assert "【姿势】自然站立姿态" in prompt
    assert "【风格】写实摄影风格，电影质感" in prompt
    assert "全身完整展示" in prompt


def test_fallback_scene_is_bounded_and_anchor_extracts_legacy_visual_traits() -> None:
    enhancer = DeepSeekPromptEnhancer()
    story = "雨夜旧书院。" * 40
    scene, prompt = enhancer._fallback_scene_selection(story, {"name": "顾川", "era": "民国"})
    anchor = enhancer._fallback_appearance_anchor("顾川", "方脸，金色短发", "民国")

    assert scene == story[:150]
    assert "顾川" in prompt and "民国场景插画" in prompt
    assert anchor["face_shape"] == "方脸"
    assert anchor["hair_style"] == "短发"
    assert anchor["hair_color"] == "金色"
    assert anchor["generated_from"] == "方脸，金色短发"
    assert anchor["version"] == 1 and anchor["is_fallback"] is True
