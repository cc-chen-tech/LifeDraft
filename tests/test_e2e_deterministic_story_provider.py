"""Contracts for the isolated AI provider used by browser E2E tests."""

import json

from src.ai.client import AIClient
from src.ai.system_prompts import get_system_prompt
import pytest

pytestmark = [pytest.mark.e2e]


def test_e2e_provider_returns_story_and_options_without_openai_client(
    monkeypatch,
) -> None:
    """E2E event generation must not send the CI dummy key to a provider."""
    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    client = AIClient(api_key="dummy-key-for-testing")
    client.client = None

    story = client.call(
        system_prompt=get_system_prompt("story_novelist", "zh"),
        user_prompt="请生成第一轮故事。",
        max_tokens=2048,
    )
    options = client.call(
        system_prompt=get_system_prompt("option_generator", "zh"),
        user_prompt=f"故事：{story}",
        max_tokens=2048,
    )

    assert len(story) >= 350
    parsed = json.loads(options)
    assert [option["text"] for option in parsed["options"]] == [
        "核对会议纪要中的风险点",
        "约同事复盘分歧的依据",
        "先补齐明早汇报的数据",
    ]


def test_e2e_provider_streams_choice_continuation_without_openai_client(
    monkeypatch,
) -> None:
    """E2E choice completion must not fall through to the CI dummy key."""
    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    client = AIClient(api_key="dummy-key-for-testing")
    client.client = None
    streamed: list[str] = []

    continuation = client.call(
        system_prompt=get_system_prompt("story_continuation", "zh"),
        user_prompt="玩家选择核对会议纪要中的风险点。",
        max_tokens=2048,
        stream_callback=streamed.append,
    )

    assert len(continuation) >= 200
    assert streamed == [continuation]


@pytest.mark.parametrize("quality", ["fast", "expert", "master"])
@pytest.mark.parametrize("setting", ["现代", "南宋，李逍遥与赵灵儿"])
def test_e2e_daily_prose_satisfies_active_strict_budget(monkeypatch, quality, setting):
    """The fixture must pass production shape checks, not disable them."""
    from src.ai.budgets import (
        GenerationCallTracker,
        GenerationOperation,
        NarrativeKind,
        resolve_narrative_budget,
    )
    from src.ai.story_generator import _localized_story_shape_issues
    from src.ai.quick_validator import quick_validate_story

    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    client = AIClient(api_key="dummy-key-for-testing")
    client.client = None
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND, GenerationOperation.GENERATE, quality, "zh"
    )
    story = client.call(
        system_prompt=get_system_prompt("story_novelist", "zh"),
        user_prompt=f"请生成今日故事。{setting}",
        generation_tracker=GenerationCallTracker(budget),
    )
    assert not _localized_story_shape_issues(
        story,
        language="zh",
        target_min=budget.length.target_min,
        target_max=budget.length.target_max,
        use_localized_measurement=True,
    )
    result = quick_validate_story(
        story_text=story,
        character_settings={
            "name": "李逍遥",
            "era": {"name": "南宋", "period": "古代"},
        },
        available_people=["李逍遥", "赵灵儿"],
        language="zh",
    )
    assert result.passed, result.issues
    assert not any(modern in story for modern in ["投影", "产品日志", "工位"])


@pytest.mark.parametrize("era", ["现代", "南宋"])
def test_strict_daily_fixture_passes_real_generation_pipeline_offline(monkeypatch, era):
    from src.ai.generator import EventGenerator
    from src.game.daily_timeline import build_daily_timeline
    from src.game.state import PlayerState

    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "false")
    ai = EventGenerator(
        api_key="dummy-key-for-testing", use_cache=False, quality_level="expert"
    )
    ai.ai_client.client = (
        None  # Any unhandled model request fails, never calls a provider.
    )
    settings = {
        "name": "李逍遥",
        "era": {"name": era, "period": "古代" if era == "南宋" else "现代"},
        "age": {"age": 22},
        "relationships": {"key_people": []},
    }
    state = PlayerState(
        name="李逍遥",
        player_name="李逍遥",
        age=22,
        life_vision="成为优秀的人",
        character_settings=settings,
        timeline=build_daily_timeline(
            start_date="1200-01-01" if era == "南宋" else "2024-01-01", day_index=0
        ),
        timeline_version=2,
    )
    event = ai.generate_round_event(
        player_state=state.to_dict(),
        character_settings=settings,
        language="zh",
        round_number=0,
        round_context="",
    )
    assert event.delivery_notice is None
    assert len(event.event_description) >= 800
    assert len(event.options) == 3
    assert all("会议" not in option.text for option in event.options)


def test_e2e_judge_fixture_does_not_accept_unrelated_prose_or_enable_in_production(
    monkeypatch,
):
    from src.ai.budgets import (
        GenerationOperation,
        NarrativeKind,
        resolve_narrative_budget,
    )
    from src.ai.e2e_story_provider import deterministic_e2e_response

    budget = resolve_narrative_budget(
        NarrativeKind.ROUND, GenerationOperation.GENERATE, "expert", "zh"
    )
    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    assert (
        deterministic_e2e_response(
            get_system_prompt("consistency_validator", "zh"),
            user_prompt="李逍遥在南宋拿出智能手机。",
            narrative_budget=budget,
        )
        is None
    )
    monkeypatch.delenv("E2E_DETERMINISTIC_STORY")
    for kind in ["story_novelist", "option_generator", "consistency_validator"]:
        assert (
            deterministic_e2e_response(
                get_system_prompt(kind, "zh"),
                narrative_budget=budget,
            )
            is None
        )


def test_e2e_judge_rejects_modified_fixture_prose(monkeypatch):
    from src.ai.budgets import (
        GenerationOperation,
        NarrativeKind,
        resolve_narrative_budget,
    )
    from src.ai.e2e_story_provider import deterministic_e2e_response
    from config.prompts import get_consistency_validation_prompt

    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND, GenerationOperation.GENERATE, "expert", "zh"
    )
    story = deterministic_e2e_response(
        get_system_prompt("story_novelist", "zh"), narrative_budget=budget
    )
    assert story is not None
    prompt = get_consistency_validation_prompt(
        story_text=story + "主角拿出了智能手机。",
        constraints_text="南宋。",
        character_settings={},
        language="zh",
    )
    assert (
        deterministic_e2e_response(
            get_system_prompt("consistency_validator", "zh"),
            user_prompt=prompt,
            narrative_budget=budget,
        )
        is None
    )


@pytest.mark.parametrize("quality", ["fast", "expert", "master"])
def test_daily_fixture_passes_real_era_validator_but_anachronism_does_not(
    monkeypatch, quality
):
    """Neutral E2E prose must not hide a disabled production era validator."""
    from src.ai.budgets import (
        GenerationOperation,
        NarrativeKind,
        resolve_narrative_budget,
    )
    from src.ai.e2e_story_provider import deterministic_e2e_response
    from src.ai.harness.era_validator import validate_era_consistency

    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND, GenerationOperation.GENERATE, quality, "zh"
    )
    story = deterministic_e2e_response(
        get_system_prompt("story_novelist", "zh"),
        user_prompt="南宋，李逍遥与赵灵儿",
        narrative_budget=budget,
    )
    assert story is not None
    context = {"era": "南宋", "era_type": "ancient"}
    assert validate_era_consistency(story, context)[0]
    assert not validate_era_consistency(story + "李逍遥拿出手机拨打电话。", context)[0]
