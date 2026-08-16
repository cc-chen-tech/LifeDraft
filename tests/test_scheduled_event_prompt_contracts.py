"""No-provider contracts for scheduled-event prompt field preservation."""

from config.feature_flags import reset_features, set_feature
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
            {
                "description": "陪母亲复查",
                "parties": ["林岚", "母亲"],
                "event_hint": "医院挂号",
            },
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
        {
            "era": {"era_name": "modern London"},
            "relationships": {"key_people": [{"name": "Maya", "role": "mentor"}]},
        },
        "en",
    )

    assert "Meet Maya at the archive" in prompt
    assert "Characters involved:" in prompt and "Maya" in prompt
    assert "Current time: Week 4, Round 4" in prompt
    assert "Player name: Alex" in prompt
    assert "[MANDATORY EVENT]" in prompt and "Return ONLY JSON" in prompt


def test_daily_scheduled_prompt_uses_daily_opening_and_transition_contract() -> None:
    state = {
        "player_name": "林岚",
        "life_vision": "建立一间让普通人安心阅读的社区书店",
        "week": 0,
        "current_round": 0,
        "timeline": {
            "version": 2,
            "day_index": 0,
            "day_number": 1,
            "current_date": "2026-08-16",
        },
        "day_history": [],
    }

    prompt = _generator("zh")._build_scheduled_event_prompt(
        [{"description": "和房东复核租约", "parties": ["房东"]}],
        state,
        {"name": "林岚"},
        "zh",
    )

    assert "首日人物开场" in prompt
    assert "第一段只能有一句" in prompt
    assert '"transition_text"' in prompt
    assert "第1周·周一" not in prompt
    assert "时间线标题约束" not in prompt


def test_daily_scheduled_prompt_includes_fresh_projection_hard_world_and_soft_context() -> (
    None
):
    set_feature("daily_world_projection_v1", True)
    try:
        state = {
            "player_name": "孙悟空",
            "week": 1,
            "current_round": 0,
            "timeline": {
                "version": 2,
                "day_index": 1,
                "current_date": "2026-08-02",
            },
            "day_history": [
                {
                    "day_index": 1,
                    "event_id": "event-1",
                    "revision": 1,
                    "story_date": "2026-08-02",
                    "event_description": "孙悟空已经返回花果山。",
                    "choice": "进入水帘洞",
                }
            ],
            "established_facts": [],
            "character_habits": [],
            "world_model_data": {
                "character_locations": {
                    "孙悟空": {"location": "旧东海", "region": "东海"}
                }
            },
            "world_projection_state": {
                "version": 1,
                "applied_through_day_index": 1,
                "pending_from_day_index": None,
                "world": {
                    "location_updates": [
                        {
                            "character": "孙悟空",
                            "location": "花果山",
                            "region": "傲来国",
                            "source": {
                                "event_id": "event-0",
                                "revision": 1,
                                "day_index": 0,
                            },
                        }
                    ]
                },
            },
        }

        prompt = _generator("zh")._build_scheduled_event_prompt(
            [{"description": "召集群猴议事", "parties": ["孙悟空"]}],
            state,
            {},
            "zh",
        )

        assert "【世界模型约束" in prompt
        assert "孙悟空 当前位置：花果山" in prompt
        assert "旧东海" in prompt
    finally:
        reset_features()


def test_daily_scheduled_prompt_includes_gap_tail_and_immutable_hard_fact() -> None:
    set_feature("daily_world_projection_v1", True)
    try:
        state = {
            "player_name": "孙悟空",
            "week": 1,
            "current_round": 0,
            "timeline": {
                "version": 2,
                "day_index": 1,
                "current_date": "2026-08-02",
            },
            "day_history": [
                {
                    "day_index": 1,
                    "event_id": "event-1",
                    "revision": 1,
                    "story_date": "2026-08-02",
                    "event_description": "孙悟空已经返回花果山。",
                    "choice": "进入水帘洞",
                }
            ],
            "established_facts": [
                {
                    "subject": "孙悟空",
                    "category": "identity",
                    "fact": "孙悟空是石猴",
                }
            ],
            "character_habits": [],
            "world_model_data": {},
            "world_projection_state": {
                "version": 1,
                "applied_through_day_index": 0,
                "pending_from_day_index": 1,
                "world": {},
            },
        }

        prompt = _generator("zh")._build_scheduled_event_prompt(
            [{"description": "召集群猴议事", "parties": ["孙悟空"]}],
            state,
            {},
            "zh",
        )

        assert "孙悟空是石猴" in prompt
        assert "孙悟空已经返回花果山。" in prompt
        assert "进入水帘洞" in prompt
    finally:
        reset_features()
