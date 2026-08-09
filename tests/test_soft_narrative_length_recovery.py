"""Contracts for soft narrative length and terminal continuity recovery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.ai.harness import ConstraintCheckResult, ValidationResult
from src.ai.harness.quality_level import QualityLevel
from src.ai.models import EventOption, GameEvent
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator

_STORY_SENTENCE = (
    "林岚与陈越在影院会议室核对施工方案、预算风险和合作条款，"
    "并把每项分歧写进备忘录，等着对方决定下一步。"
)


def _story_with_length(length: int) -> str:
    repeated = _STORY_SENTENCE * (length // len(_STORY_SENTENCE) + 2)
    story = repeated[: length - 1] + "。"
    assert len(story) == length
    return story


class LengthDriftClient:
    """Deterministic provider that requests one consistency repair."""

    def __init__(self, story: str):
        self.story = story
        self.calls: list[dict[str, Any]] = []

    def call(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        if kwargs.get("temperature") == 0.3:
            return (
                '{"should_retry": true, "retry_reason": "fixture", "issues": ['
                '{"dimension": "temporal", "severity": "CRITICAL", '
                '"description": "fixture conflict", "fix_suggestion": "repair"}]}'
            )
        return self.story


class FailAfterFirstStoryClient:
    def __init__(self, story: str):
        self.story = story
        self.calls = 0

    def call(self, **_kwargs: Any) -> str:
        self.calls += 1
        if self.calls == 1:
            return self.story
        raise TimeoutError("repair deadline exhausted")


class SequenceThenFailClient:
    def __init__(self, stories: list[str]):
        self.stories = iter(stories)

    def call(self, **_kwargs: Any) -> str:
        try:
            return next(self.stories)
        except StopIteration as exc:
            raise TimeoutError("generation deadline exhausted") from exc


class ThreeOptionGenerator:
    def generate_options_only(self, **kwargs: Any) -> GameEvent:
        story = str(kwargs["story_description"])
        return GameEvent(
            event_description=story,
            options=[
                EventOption(text="细读合作条款", effects={}),
                EventOption(text="请伙伴一起把关", effects={}),
                EventOption(text="先锁定关键风险", effects={}),
            ],
        )

    def validate_and_fix_relationships(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def validate_options_consistency(
        self,
        *_args: Any,
        **_kwargs: Any,
    ) -> list[str]:
        return []


class FailingOptionGenerator(ThreeOptionGenerator):
    def generate_options_only(self, **_kwargs: Any) -> GameEvent:
        raise TimeoutError("option deadline exhausted")


class PassingPipeline:
    def validate(self, **_kwargs: Any) -> ValidationResult:
        return ValidationResult(passed=True, score=100.0)


@dataclass
class SingleFailurePipeline:
    constraint_type: str

    def validate(self, **_kwargs: Any) -> ValidationResult:
        return ValidationResult(
            passed=False,
            score=55.0,
            critical_failures=[
                ConstraintCheckResult(
                    constraint_type=self.constraint_type,
                    priority="CRITICAL",
                    passed=False,
                    evidence="deterministic contract fixture",
                )
            ],
            total_checked=1,
        )


class MinimalWorldModel:
    continuity_ledger = None

    def build_constraints_text(self, _language: str) -> str:
        return "No additional fixture constraints."

    def get_established_profile_names(self) -> list[str]:
        return []


@pytest.mark.parametrize(
    "harness_enabled", [False, True], ids=["harness-off", "harness-on"]
)
@pytest.mark.parametrize("story_length", [1329, 1710, 2315])
def test_expert_length_drift_keeps_story_and_three_options(
    monkeypatch: pytest.MonkeyPatch,
    harness_enabled: bool,
    story_length: int,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", str(harness_enabled).lower())
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    story = _story_with_length(story_length)
    client = LengthDriftClient(story)
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)
    if harness_enabled:
        generator._validation_pipeline = PassingPipeline()

    event = generator.generate_round_event(
        player_state={"game_id": 7, "week": 4, "current_round": story_length},
        language="zh",
        round_number=0,
        round_context="",
        character_settings={},
        option_generator=ThreeOptionGenerator(),
        world_model=MinimalWorldModel(),
    )

    assert event.event_description == story
    assert len(event.options) == 3


def test_failed_shape_repair_recovers_latest_story_and_three_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "false")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    story = _story_with_length(1329)
    client = FailAfterFirstStoryClient(story)

    event = StoryGenerator(
        client, quality_level=QualityLevel.EXPERT
    ).generate_round_event(
        player_state={"game_id": 8, "week": 4, "current_round": 0},
        language="zh",
        round_number=0,
        round_context="",
        character_settings={},
        option_generator=FailingOptionGenerator(),
    )

    assert client.calls == 2
    assert event.event_description == story
    assert len(event.options) == 3


def test_fallback_uses_latest_complete_story_not_longest_story(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    longer_first_story = _story_with_length(1000)
    latest_complete_story = _story_with_length(900).replace("林岚", "周宁", 1)
    generator = StoryGenerator(
        SequenceThenFailClient([longer_first_story, latest_complete_story]),
        quality_level=QualityLevel.EXPERT,
    )
    generator._validation_pipeline = PassingPipeline()

    event = generator.generate_round_event(
        player_state={"game_id": 12, "week": 4, "current_round": 0},
        language="zh",
        round_number=0,
        round_context="",
        character_settings={},
        option_generator=FailingOptionGenerator(),
    )

    assert event.event_description == latest_complete_story
    assert len(event.options) == 3


def test_expert_consistency_rewrite_inherits_expert_token_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    story = _story_with_length(900)
    client = LengthDriftClient(story)
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)

    result = generator._validate_and_retry_story(
        story_text=story,
        world_model=MinimalWorldModel(),
        player_state={"game_id": 9, "week": 4, "current_round": 0},
        character_settings={},
        language="zh",
        original_prompt="Generate the round.",
        sys_prompt="Write prose.",
    )

    repair_calls = [call for call in client.calls if call.get("temperature") == 0.7]
    assert result == story
    assert len(repair_calls) == 1
    assert repair_calls[0]["max_tokens"] == 4096


def test_presentation_only_harness_failure_does_not_deny_story(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    story = _story_with_length(900)
    generator = StoryGenerator(
        LengthDriftClient(story),
        quality_level=QualityLevel.EXPERT,
    )
    generator._validation_pipeline = SingleFailurePipeline("decision_point_ending")

    event = generator.generate_round_event(
        player_state={"game_id": 10, "week": 4, "current_round": 0},
        language="zh",
        round_number=0,
        round_context="",
        character_settings={},
        option_generator=ThreeOptionGenerator(),
    )

    assert event.event_description == story
    assert len(event.options) == 3


def test_severe_continuity_harness_failure_remains_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    story = _story_with_length(900)
    generator = StoryGenerator(
        LengthDriftClient(story),
        quality_level=QualityLevel.EXPERT,
    )
    generator._validation_pipeline = SingleFailurePipeline("established_facts")

    with pytest.raises(
        StoryGenerationFailure,
        match="Story harness validation failed after final attempt",
    ):
        generator.generate_round_event(
            player_state={"game_id": 11, "week": 4, "current_round": 0},
            language="zh",
            round_number=0,
            round_context="",
            character_settings={},
            option_generator=ThreeOptionGenerator(),
        )
