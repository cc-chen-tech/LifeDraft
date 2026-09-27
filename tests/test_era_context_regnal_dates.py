"""Real-provider opening regression: Ming settings must not become modern."""

import pytest

from src.ai.quick_validator import QuickValidator, quick_validate_story
from src.ai.harness.era_validator import validate_era_consistency

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("description", ["明永乐十九年", "大明宣德元年"])
def test_explicit_historical_era_does_not_inherit_modern_relationship_default(description):
    settings = {"era": {"era_description": description}, "relationships": {"key_people": []}}
    context = QuickValidator.extract_era_context(settings)
    assert context["era_type"] != "modern"
    # Minimal excerpt of the real DeepSeek draft that caused a wasted retry.
    result = quick_validate_story(
        "于谦二十三岁这年春天，心里装着一件比科举考题更沉的事。",
        character_settings=settings,
        language="zh",
    )
    assert not any("现代背景检测到古代" in issue for issue in result.issues)
    assert validate_era_consistency("于谦拿出手机刷抖音。", context)[0] is False


def test_unrecognized_explicit_era_is_not_assumed_modern():
    context = QuickValidator.extract_era_context({
        "era": {"era_description": "架空琉璃纪元"},
        "relationships": {"key_people": []},
    })
    assert context["era_type"] == ""


def test_unspecified_realistic_era_keeps_modern_default():
    context = QuickValidator.extract_era_context({"occupation": "剪辑师"})
    assert context["era_type"] == "modern"


@pytest.mark.parametrize("food", ["粥是小米的，上面浮着一层米油", "他从篮子里拿出一只苹果"])
def test_historical_food_is_not_a_modern_brand(food):
    assert validate_era_consistency(food, {"era": "明永乐十九年", "era_type": "ancient"})[0]


@pytest.mark.parametrize("modern", ["小米手机", "苹果电脑", "苹果公司", "小米公司"])
def test_unambiguous_modern_brand_or_device_still_rejected(modern):
    assert not validate_era_consistency(modern, {"era": "明永乐十九年", "era_type": "ancient"})[0]
