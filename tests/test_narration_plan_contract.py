import pytest

from src.ai.narration_plan import (
    NarrationPlanValidationError,
    NarrationPlanGenerator,
    parse_narration_plan,
)


def test_narration_plan_accepts_only_minimax_native_emotions() -> None:
    plan = parse_narration_plan(
        {
            "segments": [
                {
                    "paragraph_index": 0,
                    "emotion": "fearful",
                    "speed": 0.92,
                    "pause_after_ms": 280,
                    "vocal_cue": "(whispers)",
                }
            ]
        },
        paragraph_count=1,
    )

    assert plan.segments[0].emotion == "fearful"
    assert plan.segments[0].vocal_cue == "(whispers)"


def test_narration_plan_reports_concrete_errors_for_model_retry() -> None:
    with pytest.raises(NarrationPlanValidationError) as exc_info:
        parse_narration_plan(
            {
                "segments": [
                    {
                        "paragraph_index": 0,
                        "emotion": "tense",
                        "speed": 3.0,
                        "pause_after_ms": -1,
                        "vocal_cue": "(not-a-minimax-cue)",
                    }
                ]
            },
            paragraph_count=1,
        )

    message = str(exc_info.value)
    assert "emotion must be one of" in message
    assert "speed must be between" in message
    assert "pause_after_ms must be between" in message
    assert "vocal_cue must be one of" in message


def test_narration_plan_requires_one_segment_per_paragraph() -> None:
    with pytest.raises(NarrationPlanValidationError, match="expected 2 segments"):
        parse_narration_plan(
            {"segments": [{"paragraph_index": 0, "emotion": "calm"}]},
            paragraph_count=2,
        )


def test_narration_plan_generator_retries_with_validation_feedback() -> None:
    class Client:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def call(self, **kwargs):
            self.prompts.append(kwargs["user_prompt"])
            if len(self.prompts) == 1:
                return '{"segments":[{"paragraph_index":0,"emotion":"tense","speed":1,"pause_after_ms":0,"vocal_cue":""}]}'
            return '{"segments":[{"paragraph_index":0,"emotion":"fearful","speed":1,"pause_after_ms":0,"vocal_cue":""}]}'

    client = Client()
    plan = NarrationPlanGenerator(client).generate("门后传来一声轻响。")

    assert plan["source"] == "story-model"
    assert plan["segments"][0]["emotion"] == "fearful"
    assert "Unsupported" not in client.prompts[1]
    assert "emotion must be one of" in client.prompts[1]
