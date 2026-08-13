"""No-provider contracts for scheduled-event prompt field preservation."""

from src.game.round.event_generator import RoundEventGenerator


def _generator(language: str) -> RoundEventGenerator:
    return RoundEventGenerator(
        player_state_getter=lambda: None,
        ai_generator=None,
        language_getter=lambda: language,
        character_introduction_service=None,
        summary_selector=None,
        relationship_service=None,
    )


def test_chinese_scheduled_prompt_preserves_commitments_cast_and_timeline() -> None:
    prompt = _generator("zh")._build_scheduled_event_prompt(
        [
            {"description": "陪母亲复查", "parties": ["林岚", "母亲"], "event_hint": "医院挂号"},
            {"description": "交付修订图纸", "parties": ["林岚", "周老师"]},
        ],
        {"player_name": "林岚", "week": 2, "current_round": 1, "rounds_per_week": 3},
        {
            "era": {"era_description": "现代上海都市生活"},
            "relationships": {"key_people": [{"name": "周老师", "role": "导师"}]},
            "family": {"family_members": [{"name": "母亲", "relationship": "母女"}]},
        },
        "zh",
    )

    assert "陪母亲复查；交付修订图纸" in prompt
    assert "医院挂号" in prompt
    assert "第3周·周中" in prompt
    assert "林岚" in prompt and "周老师" in prompt and "母亲" in prompt
    assert "反向时代漂移红线" in prompt
    assert "【强制事件】" in prompt and "只返回JSON" in prompt


def test_english_scheduled_prompt_preserves_identity_and_round_coordinates() -> None:
    prompt = _generator("en")._build_scheduled_event_prompt(
        [{"description": "Meet Maya at the archive", "parties": ["Alex", "Maya"]}],
        {"player_name": "Alex", "week": 4, "current_round": 4, "rounds_per_week": 4},
        {"era": {"era_name": "modern London"}, "relationships": {"key_people": [{"name": "Maya", "role": "mentor"}]}},
        "en",
    )

    assert "Meet Maya at the archive" in prompt
    assert "Characters involved:" in prompt and "Maya" in prompt
    assert "Current time: Week 4, Round 4" in prompt
    assert "Player name: Alex" in prompt
    assert "[MANDATORY EVENT]" in prompt and "Return ONLY JSON" in prompt
