"""Provider-free contracts for player-visible round-story fallback grounding."""

from src.ai.story_generator import StoryGenerator


def test_chinese_fallback_preserves_era_trait_and_relationship_anchor() -> None:
    story = StoryGenerator._build_round_story_fallback(
        player_state={"player_name": "林岚", "week": 4},
        character_settings={
            "era": {"era_description": "民国上海"},
            "traits": {"traits_description": "谨慎的建筑师"},
            "relationships": {
                "key_people": [
                    {"name": "沈宁", "role": "大学同学", "relationship": "长期搭档"}
                ]
            },
        },
        language="zh",
        round_number=1,
    )

    assert "在民国上海的背景下" in story
    assert "周中，林岚" in story
    assert "你把谨慎的建筑师放在心里" in story
    assert "沈宁这位大学同学仍在你的关系网里" in story
    assert "只推进一个小决策" not in story
    assert "调整节奏的机会" in story


def test_english_fallback_uses_generic_day_and_preserves_relationship_anchor() -> None:
    story = StoryGenerator._build_round_story_fallback(
        player_state={"player_name": "Alex"},
        character_settings={
            "relationships": {
                "key_people": [{"name": "Morgan", "role": "producer"}]
            }
        },
        language="en",
        round_number=9,
    )

    assert story.startswith("Today, Alex does not encounter a dramatic turn")
    assert "Morgan still matters in your relationship network" in story
    assert "immediate clues" in story
