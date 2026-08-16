"""Local contracts for summary response normalization and recovery fields."""

import json

import pytest

from src.ai.summary_generator import SummaryGenerator
from src.game.world_projection_schema import WorldProjectionExtractionError


class _DeterministicSummaryClient:
    def __init__(self, responses: list[str]):
        self.responses = responses

    def call(self, **_kwargs: object) -> str:
        return self.responses.pop(0)


class _TimedOutProjectionClient:
    def call(self, **_kwargs: object) -> str:
        raise TimeoutError("provider timeout")


def test_story_compression_keeps_structured_updates_and_cleans_summary_artifacts() -> None:
    client = _DeterministicSummaryClient(
        [
            json.dumps(
                {
                    "summary": '```json\n{"summary":"林岚完成了档案核验。"}',
                    "storyline_updates": [{"id": "archive", "status": "advanced"}],
                    "fact_updates": [{"subject": "林岚", "fact": "掌握线索"}],
                    "event_concluded": False,
                    "foreshadowing_seeds": ["旧书院的钥匙"],
                    "habit_updates": [{"character": "林岚", "habit": "核验来源"}],
                }
            )
        ]
    )

    result = SummaryGenerator(client).compress_story(
        story="林岚在旧书院核对档案。",
        choice="继续追查",
        language="zh",
    )

    assert result == {
        "summary": "林岚完成了档案核验。",
        "storyline_updates": [{"id": "archive", "status": "advanced"}],
        "fact_updates": [{"subject": "林岚", "fact": "掌握线索"}],
        "event_concluded": False,
        "foreshadowing_seeds": ["旧书院的钥匙"],
        "habit_updates": [{"character": "林岚", "habit": "核验来源"}],
    }


def test_split_summary_paths_fill_missing_world_categories_with_empty_lists() -> None:
    narrative_client = _DeterministicSummaryClient(
        [json.dumps({"summary": "Ada reviewed the archive.", "event_concluded": True})]
    )
    world_client = _DeterministicSummaryClient(
        [json.dumps({"fact_updates": [{"subject": "Ada", "fact": "has the key"}]})]
    )

    narrative = SummaryGenerator(narrative_client).compress_narrative(
        story="Ada reviewed the archive.", choice="wait", language="en"
    )
    world = SummaryGenerator(world_client).extract_world_updates(
        story="Ada reviewed the archive.", choice="wait", language="en"
    )

    assert narrative == {
        "summary": "Ada reviewed the archive.",
        "event_concluded": True,
        "storyline_updates": [],
    }
    assert world["fact_updates"] == [{"subject": "Ada", "fact": "has the key"}]
    assert world["foreshadowing_seeds"] == []
    assert world["habit_updates"] == []
    assert world["location_updates"] == []
    assert world["career_updates"] == []
    assert world["commitment_updates"] == []
    assert world["causal_updates"] == []


def test_weekly_summary_filters_invalid_bonus_effects_without_losing_summary() -> None:
    client = _DeterministicSummaryClient(
        [
            json.dumps(
                {
                    "summary": "本周完成了关键访谈。",
                    "bonus_effects": {
                        "energy": -8,
                        "mood": 99,
                        "knowledge": 6.8,
                        "wealth": "invalid",
                    },
                }
            )
        ]
    )

    result = SummaryGenerator(client).generate_weekly_summary(
        rounds=[{"story": "林岚完成访谈"}], character_settings={}, language="zh"
    )

    assert result == {
        "summary": "本周完成了关键访谈。",
        "bonus_effects": {"energy": -8, "knowledge": 6},
    }


def test_combined_postprocess_returns_both_narrative_and_world_fields() -> None:
    """P1-成本优化：compress_and_extract 一次调用同时返回 narrative 与 world 字段。"""
    client = _DeterministicSummaryClient(
        [
            json.dumps(
                {
                    "summary": "林岚在旧书院找到了钥匙，并决定追查档案去向。",
                    "event_concluded": False,
                    "storyline_updates": [
                        {"action": "new", "description": "追查档案去向"}
                    ],
                    "fact_updates": [
                        {"action": "new", "subject": "旧书院", "fact": "藏有钥匙"}
                    ],
                    "foreshadowing_seeds": [],
                    "habit_updates": [],
                    "location_updates": [],
                    "career_updates": [],
                    "commitment_updates": [],
                    "causal_updates": [],
                },
                ensure_ascii=False,
            )
        ]
    )

    result = SummaryGenerator(client).compress_and_extract(
        story="林岚走进旧书院，在角落发现一枚铜钥匙。",
        choice="拿起钥匙",
        language="zh",
        pending_storylines=None,
        established_facts=None,
        character_habits=None,
    )

    assert "summary" in result
    assert result["event_concluded"] is False
    assert result["storyline_updates"][0]["action"] == "new"
    assert result["fact_updates"][0]["subject"] == "旧书院"
    for key in (
        "foreshadowing_seeds",
        "habit_updates",
        "location_updates",
        "career_updates",
        "commitment_updates",
        "causal_updates",
    ):
        assert result[key] == []


def test_combined_postprocess_falls_back_deterministically_on_failure() -> None:
    """P1-成本优化：合并调用失败时返回确定性兜底，包含全部字段。"""
    client = _DeterministicSummaryClient(["not-json-at-all"])

    result = SummaryGenerator(client).compress_and_extract(
        story="林岚在旧书院整理档案。",
        choice="继续整理",
        language="zh",
    )

    assert result["event_concluded"] is True
    assert result["summary"]
    assert result["storyline_updates"] == []
    assert result["fact_updates"] == []
    assert result["causal_updates"] == []


def test_combined_postprocess_prompt_embeds_story_once_with_both_schemas() -> None:
    """P1-成本优化：合并 prompt 只嵌入一次故事正文，且包含两套字段要求。"""
    from config.prompts import get_combined_choice_postprocess_prompt

    prompt = get_combined_choice_postprocess_prompt(
        story="林岚在旧书院发现铜钥匙。",
        choice="拿起钥匙",
        language="zh",
        pending_storylines=None,
        established_facts=None,
        character_habits=None,
    )

    assert prompt.count("林岚在旧书院发现铜钥匙。") == 1
    assert '"summary"' in prompt
    assert '"storyline_updates"' in prompt
    assert '"fact_updates"' in prompt
    assert '"causal_updates"' in prompt
    assert "只返回JSON" in prompt


def test_daily_projection_provider_timeout_raises_instead_of_returning_empty() -> None:
    generator = SummaryGenerator(_TimedOutProjectionClient())

    with pytest.raises(WorldProjectionExtractionError) as caught:
        generator.extract_daily_world_projection(
            "黑袍人抵达东海。",
            [{"text": "进入龙宫"}],
            {"character_locations": {"黑袍人": {"location": "花果山"}}},
            language="zh",
        )

    assert caught.value.code == "provider_timeout"
