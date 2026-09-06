import json

import pytest

from src.ai.narration_plan import (
    NarrationPlanValidationError,
    NarrationPlanGenerator,
    parse_narration_plan,
)
from src.services.story_voice_reading import StoryVoiceReadingService


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


def test_narration_plan_generator_records_ai_observability() -> None:
    class Client:
        def call(self, **kwargs):
            return (
                '{"segments":[{"paragraph_index":0,"emotion":"calm",'
                '"speed":1,"pause_after_ms":0,"vocal_cue":""}]}'
            )

    generator = NarrationPlanGenerator(Client())
    generator.generate("门后传来一声轻响。")

    assert generator.last_metrics["source"] == "ai"
    assert generator.last_metrics["fallback_reason"] is None
    assert generator.last_metrics["ai_attempts"] == 1
    assert len(generator.last_metrics["output_token_budgets"]) == 1
    assert generator.last_metrics["duration_ms"] >= 0


def test_narration_plan_generator_records_validation_retry_metrics() -> None:
    class Client:
        def __init__(self) -> None:
            self.calls = 0

        def call(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return '{"segments":[]}'
            return (
                '{"segments":[{"paragraph_index":0,"emotion":"calm",'
                '"speed":1,"pause_after_ms":0,"vocal_cue":""}]}'
            )

    generator = NarrationPlanGenerator(Client())
    generator.generate("门后传来一声轻响。")

    assert generator.last_metrics["source"] == "ai"
    assert generator.last_metrics["ai_attempts"] == 2
    assert len(generator.last_metrics["output_token_budgets"]) == 2
    assert (
        generator.last_metrics["output_token_budgets"][1]
        > generator.last_metrics["output_token_budgets"][0]
    )


def test_narration_plan_generation_disables_text_truncation_recovery() -> None:
    class Client:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            return (
                '{"segments":[{"paragraph_index":0,"emotion":"calm",'
                '"speed":1,"pause_after_ms":0,"vocal_cue":""}]}'
            )

    client = Client()
    NarrationPlanGenerator(client).generate("门后传来一声轻响。")

    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert client.calls[0]["_allow_truncation_recovery"] is False


def test_narration_plan_budget_is_structured_and_grows_for_long_chapters() -> None:
    paragraphs = [f"第 {index} 段故事内容。" for index in range(28)]

    class Client:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return '{"segments": []}'
            return json.dumps(
                {
                    "segments": [
                        {
                            "paragraph_index": index,
                            "emotion": "calm",
                            "speed": 1.0,
                            "pause_after_ms": 0,
                            "vocal_cue": "",
                        }
                        for index in range(len(paragraphs))
                    ]
                }
            )

    client = Client()
    NarrationPlanGenerator(client).generate("\n\n".join(paragraphs))

    assert client.calls[0]["max_tokens"] > 3360
    assert client.calls[1]["max_tokens"] > client.calls[0]["max_tokens"]


def test_ensure_narration_plan_prefers_valid_ai_plan_by_default(monkeypatch) -> None:
    class Client:
        api_key = "configured"

        def call(self, **kwargs):
            return (
                '{"segments":[{"paragraph_index":0,"emotion":"happy",'
                '"speed":1,"pause_after_ms":0,"vocal_cue":""}]}'
            )

    monkeypatch.delenv("ENABLE_AI_NARRATION_PLAN", raising=False)
    monkeypatch.delenv("STORY_TTS_DISABLE_NARRATION_PLAN_AI", raising=False)
    monkeypatch.setattr("src.ai.client.AIClient", lambda: Client())

    plan = StoryVoiceReadingService._ensure_narration_plan({}, ["门后传来一声轻响。"])

    assert plan["source"] == "story-model"
    assert plan["segments"][0]["emotion"] == "happy"


def test_ensure_narration_plan_falls_back_when_ai_plan_is_invalid(monkeypatch) -> None:
    class Client:
        api_key = "configured"

    class BrokenGenerator:
        def __init__(self, client) -> None:
            pass

        def generate(self, *args, **kwargs):
            raise NarrationPlanValidationError(["invalid model plan"])

    monkeypatch.setattr("src.ai.client.AIClient", lambda: Client())
    monkeypatch.setattr("src.services.story_voice_reading.NarrationPlanGenerator", BrokenGenerator)

    plan = StoryVoiceReadingService._ensure_narration_plan({}, ["黑暗中传来危险的脚步声。"])

    assert plan["source"] == "deterministic-fallback"
    assert plan["segments"][0]["emotion"] == "fearful"


def test_ensure_narration_plan_reports_fallback_reason_when_ai_fails(monkeypatch) -> None:
    class Client:
        api_key = "configured"

    class BrokenGenerator:
        def __init__(self, client) -> None:
            self.last_metrics = {
                "ai_attempts": 2,
                "output_token_budgets": [2048, 4096],
            }

        def generate(self, *args, **kwargs):
            raise TimeoutError("provider timeout")

    monkeypatch.setattr("src.ai.client.AIClient", lambda: Client())
    monkeypatch.setattr("src.services.story_voice_reading.NarrationPlanGenerator", BrokenGenerator)

    plan, metrics = StoryVoiceReadingService._ensure_narration_plan_with_metrics(
        {}, ["黑暗中传来危险的脚步声。"]
    )

    assert plan["source"] == "deterministic-fallback"
    assert metrics["source"] == "deterministic-fallback"
    assert metrics["fallback_reason"] == "timeout"
    assert metrics["ai_attempts"] == 2
    assert metrics["output_token_budgets"] == [2048, 4096]


def test_ensure_narration_plan_falls_back_when_ai_returns_truncated_json(
    monkeypatch,
) -> None:
    class Client:
        api_key = "configured"

        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            return '{"segments": ['

    client = Client()
    monkeypatch.setattr("src.ai.client.AIClient", lambda: client)

    plan = StoryVoiceReadingService._ensure_narration_plan({}, ["黑暗中传来脚步声。"])

    assert plan["source"] == "deterministic-fallback"
    assert client.calls
    assert all(call["_allow_truncation_recovery"] is False for call in client.calls)


def test_ensure_narration_plan_can_disable_ai_and_use_local_plan(monkeypatch) -> None:
    class Client:
        api_key = "configured"

        def call(self, **kwargs):
            raise AssertionError("AI narration plan must be disabled")

    monkeypatch.setenv("ENABLE_AI_NARRATION_PLAN", "false")
    monkeypatch.setattr("src.ai.client.AIClient", lambda: Client())

    plan = StoryVoiceReadingService._ensure_narration_plan({}, ["开心地笑了起来。"])

    assert plan["source"] == "deterministic-fallback"
    assert plan["segments"][0]["emotion"] == "happy"


@pytest.mark.parametrize(
    ("env_name", "reason"),
    [
        ("ENABLE_AI_NARRATION_PLAN", "feature_disabled"),
        ("STORY_TTS_DISABLE_NARRATION_PLAN_AI", "kill_switch"),
    ],
)
def test_ensure_narration_plan_reports_non_ai_fallback_reason(
    monkeypatch, env_name, reason
) -> None:
    class Client:
        api_key = "configured"

        def call(self, **kwargs):
            raise AssertionError("AI narration plan must not be called")

    monkeypatch.setattr("src.ai.client.AIClient", lambda: Client())
    monkeypatch.delenv("ENABLE_AI_NARRATION_PLAN", raising=False)
    monkeypatch.delenv("STORY_TTS_DISABLE_NARRATION_PLAN_AI", raising=False)
    if env_name == "ENABLE_AI_NARRATION_PLAN":
        monkeypatch.setenv(env_name, "false")
    else:
        monkeypatch.setenv(env_name, "1")

    plan, metrics = StoryVoiceReadingService._ensure_narration_plan_with_metrics(
        {}, ["开心地笑了起来。"]
    )

    assert plan["source"] == "deterministic-fallback"
    assert metrics["source"] == "deterministic-fallback"
    assert metrics["fallback_reason"] == reason
    assert metrics["ai_attempts"] == 0


def test_ensure_narration_plan_reports_missing_api_key(monkeypatch) -> None:
    class Client:
        api_key = ""

    monkeypatch.delenv("ENABLE_AI_NARRATION_PLAN", raising=False)
    monkeypatch.delenv("STORY_TTS_DISABLE_NARRATION_PLAN_AI", raising=False)
    monkeypatch.setattr("src.ai.client.AIClient", lambda: Client())

    plan, metrics = StoryVoiceReadingService._ensure_narration_plan_with_metrics(
        {}, ["没有配置密钥时也要保留本地旁白。"]
    )

    assert plan["source"] == "deterministic-fallback"
    assert metrics["fallback_reason"] == "missing_api_key"
    assert metrics["ai_attempts"] == 0
