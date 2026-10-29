"""Contracts for the isolated AI provider used by browser E2E tests."""

import json

from src.ai.client import AIClient
from src.ai.system_prompts import get_system_prompt
import pytest

pytestmark = [pytest.mark.e2e]


@pytest.mark.parametrize("quality", ["fast", "expert", "master"])
@pytest.mark.parametrize("setting", ["现代", "南宋，李逍遥与赵灵儿"])
def test_e2e_story_passes_the_daily_generation_shape_gate(monkeypatch, quality, setting):
    from src.ai.budgets import (
        GenerationCallTracker,
        GenerationOperation,
        NarrativeKind,
        resolve_narrative_budget,
    )
    from src.ai.story_generator import _localized_story_shape_issues

    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    budget = resolve_narrative_budget(
        NarrativeKind.ROUND, GenerationOperation.GENERATE, quality, "zh"
    )
    client = AIClient(api_key="dummy-key-for-testing")
    client.client = None
    story = client.call(
        system_prompt=get_system_prompt("story_novelist", "zh"),
        user_prompt=f"请生成今日故事。{setting}",
        generation_tracker=GenerationCallTracker(budget),
    )
    assert (
        _localized_story_shape_issues(
            story,
            language="zh",
            target_min=budget.length.target_min,
            target_max=budget.length.target_max,
            use_localized_measurement=True,
        )
        == []
    )


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


def test_e2e_provider_serves_optional_consistency_judge_without_network(monkeypatch):
    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    client = AIClient(api_key="dummy-key-for-testing")
    client.client = None
    result = json.loads(
        client.call(
            system_prompt=get_system_prompt("consistency_validator", "zh"),
            user_prompt="检查确定性故事。",
        )
    )
    assert result == {"issues": [], "should_retry": False}


def test_provider_is_disabled_outside_e2e(monkeypatch):
    from src.ai.e2e_story_provider import deterministic_e2e_response

    monkeypatch.delenv("E2E_DETERMINISTIC_STORY", raising=False)
    for kind in ["story_novelist", "option_generator", "consistency_validator"]:
        assert deterministic_e2e_response(get_system_prompt(kind, "zh")) is None


def test_ancient_fixture_passes_real_era_validator_but_anachronism_does_not(monkeypatch):
    from src.ai.e2e_story_provider import deterministic_e2e_response
    from src.ai.harness.era_validator import validate_era_consistency

    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    story = deterministic_e2e_response(
        get_system_prompt("story_novelist", "zh"),
        user_prompt="南宋，李逍遥与赵灵儿",
    )
    context = {"era": "南宋", "era_type": "ancient"}
    assert "李逍遥" in story and "赵灵儿" in story
    assert validate_era_consistency(story, context)[0]
    assert not validate_era_consistency(story + "李逍遥拿出手机拨打电话。", context)[0]
