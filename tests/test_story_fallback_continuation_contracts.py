from src.game.story_service import StoryService


def test_chinese_fallback_preserves_choice_and_effect_consequences() -> None:
    service = StoryService(ai_generator=object(), language="zh")

    text = service.generate_fallback_continuation(
        "追问真相",
        {"mood": -1, "knowledge": 2, "relationships": {"沈砚": 3, "陆川": -2}},
    )

    assert "你选择了追问真相" in text
    assert "心情因此有些波动" in text
    assert "获得了一些领悟" in text
    assert "与沈砚的关系变得更近" in text
    assert "与陆川的关系产生了一些微妙的变化" in text


def test_english_fallback_describes_positive_mood_and_knowledge() -> None:
    service = StoryService(ai_generator=object(), language="en")

    text = service.generate_fallback_continuation("investigate", {"mood": 1, "knowledge": 1})

    assert text.startswith("You chose to investigate.")
    assert "lifted your spirits" in text
    assert "gained some insights" in text
