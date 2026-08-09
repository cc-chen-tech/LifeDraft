"""Contracts for the isolated AI provider used by browser E2E tests."""

import json

from src.ai.client import AIClient
from src.ai.system_prompts import get_system_prompt


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
