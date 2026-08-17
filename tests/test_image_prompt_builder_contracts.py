"""No-provider image prompt contracts for safety and fallback behavior."""

from src.ai.image_config import SENSITIVE_WORDS
from src.ai.image_prompt_builder import DeepSeekPromptEnhancer, ImagePromptBuilder
import pytest

pytestmark = [pytest.mark.unit]



def test_character_prompt_keeps_user_feedback_and_removes_scifi_era_signals():
    builder = ImagePromptBuilder()

    prompt = builder.build_character_prompt(
        name="林岚",
        description="短发，穿深蓝色棉质外套",
        era="2026年中国，人工智能与全息投影融入日常生活",
        style_hint="纪实摄影",
        pose_hint="站在旧书院门口",
        feedback="外套领口要有磨损细节",
    )

    era_section = prompt[prompt.index("【时代背景】") : prompt.index("【外貌特征】")]
    assert "【必须执行的修改】外套领口要有磨损细节" in prompt
    assert "【姿势】站在旧书院门口" in prompt
    assert "【风格】纪实摄影" in prompt
    assert "人工智能" not in era_section
    assert "全息投影" not in era_section
    assert "2026" in era_section


def test_location_item_scene_and_simplification_prompts_preserve_shape_contracts():
    builder = ImagePromptBuilder()
    sensitive = SENSITIVE_WORDS[0]

    location = builder.build_location_prompt("旧书院", "雨夜的木质门廊", "民国")
    item = builder.build_item_prompt("祖传罗盘", "铜制表盘刻着星图", "民国", "静物摄影")
    scene = builder.build_scene_prompt(
        "林岚在门廊查看档案",
        [{"name": "林岚", "description": "短发建筑师"}],
        "民国",
    )
    simplified_scene, simplified_prompt = builder.simplify_prompt(
        f"{sensitive} 的画面", f"{sensitive} 的场景"
    )

    assert "不要出现任何人物" in location
    assert "物品居中" in item and "静物摄影" in item
    assert "林岚(短发建筑师)" in scene
    assert sensitive not in simplified_scene
    assert sensitive not in simplified_prompt


def test_prompt_fallbacks_keep_story_identity_and_extract_visual_anchor_fields():
    builder = ImagePromptBuilder()
    enhancer = DeepSeekPromptEnhancer()

    fallback = builder.build_fallback_prompt(
        {"name": "林岚", "age": 29, "gender": "女", "era": "民国", "appearance": "短发"}
    )
    scene, illustration_prompt = enhancer._fallback_scene_selection(
        "林岚撑伞走进旧书院，在门廊翻看档案。", {"name": "林岚", "era": "民国"}
    )
    anchor = enhancer._fallback_appearance_anchor(
        "林岚", "圆脸，乌黑长发，穿深蓝色外套", "民国"
    )

    assert fallback == "民国，29岁女性，林岚。短发。人物全身像，脚部可见，写实风格。"
    assert scene.startswith("林岚撑伞")
    assert "民国场景插画" in illustration_prompt and "林岚" in illustration_prompt
    assert anchor["is_fallback"] is True
    assert anchor["face_shape"] == "圆脸"
    assert anchor["hair_style"] == "长发"
    assert anchor["hair_color"] == "黑色"


def test_enhancer_reuses_aiclient_for_same_config() -> None:
    """P1-修复：相同（key/base/model）复用同一个 AIClient，不再每次新建 OpenAI 客户端。"""
    from src.ai.image_prompt_builder import DeepSeekPromptEnhancer

    first = DeepSeekPromptEnhancer._get_client("k1", "https://api.example.com/v1", "m1")
    second = DeepSeekPromptEnhancer._get_client("k1", "https://api.example.com/v1", "m1")
    different_model = DeepSeekPromptEnhancer._get_client(
        "k1", "https://api.example.com/v1", "m2"
    )
    different_base = DeepSeekPromptEnhancer._get_client(
        "k1", "https://other.example.com/v1", "m1"
    )

    assert first is second
    assert first is not different_model
    assert first is not different_base
    # 客户端应携带独立的 base_url 配置
    assert first.client.base_url is not None
