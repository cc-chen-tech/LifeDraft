from __future__ import annotations

from typing import Any

from src.game.story_service import StoryService
from src.ai.story_rewriter import StoryRewriter


def _modern_product_manager_settings() -> dict[str, Any]:
    return {
        "era": {"year": 2024, "era_description": "2024年中国现代都市"},
        "world": {"world_description": "现实中的上海互联网公司，普通产品经理成长线"},
        "occupation": {"occupation": "产品经理"},
        "relationships": {
            "key_people": [
                {"name": "陆昊然", "role": "导师"},
                {"name": "陈晓雨", "role": "闺蜜"},
                {"name": "林一凡", "role": "同期"},
            ]
        },
    }


def test_story_continuation_retries_when_choice_result_drifts_from_character_settings() -> None:
    class DriftThenValidGenerator:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def generate_completion(self, **kwargs: Any) -> str:
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return (
                    "夜之城的雨落在荒坂集团楼下，Viktor把神经接口推到林见微面前。"
                    "马老板和方蕾催她立刻处理陌生债务。"
                )
            return "陆昊然把复盘文档递给林见微，陈晓雨陪她逐条整理用户反馈。"

    generator = DriftThenValidGenerator()
    service = StoryService(generator, language="zh")  # type: ignore[arg-type]

    continuation = service.generate_story_continuation(
        event_description="林见微刚结束需求评审，陆昊然在会议室门口等她复盘。",
        chosen_option="和陆昊然复盘需求优先级",
        effects={"knowledge": 5, "relationships": {"陆昊然": 3}},
        character_settings=_modern_product_manager_settings(),
    )

    assert len(generator.calls) == 2
    assert "上一版选择后续写" in generator.calls[1]["prompt"]
    assert "陆昊然" in continuation
    assert "陈晓雨" in continuation
    assert "夜之城" not in continuation
    assert "荒坂" not in continuation
    assert "马老板" not in continuation


def test_regenerate_story_retries_when_story_drifts_from_character_settings() -> None:
    class DriftThenValidClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def call(self, **kwargs: Any) -> str:
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return (
                    "夜之城的雨落在荒坂集团楼下，Viktor把神经接口推到林见微面前。"
                    "马老板和方蕾催她立刻处理陌生债务。"
                )
            return "陆昊然把复盘文档递给林见微，陈晓雨陪她逐条整理用户反馈。"

    client = DriftThenValidClient()
    rewriter = StoryRewriter(client)  # type: ignore[arg-type]

    regenerated = rewriter.regenerate_story(
        player_state={"player_name": "林见微", "week": 1, "current_round": 1},
        character_settings=_modern_product_manager_settings(),
        story_context="上一轮林见微刚结束需求评审。",
        language="zh",
    )

    assert len(client.calls) == 2
    assert "快速一致性修正" in client.calls[1]["user_prompt"]
    assert "陆昊然" in regenerated
    assert "陈晓雨" in regenerated
    assert "夜之城" not in regenerated
    assert "荒坂" not in regenerated
    assert "马老板" not in regenerated
