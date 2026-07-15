"""Local contracts for summary response normalization and recovery fields."""

import json

from src.ai.summary_generator import SummaryGenerator


class _DeterministicSummaryClient:
    def __init__(self, responses: list[str]):
        self.responses = responses

    def call(self, **_kwargs: object) -> str:
        return self.responses.pop(0)


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
