from __future__ import annotations

import pytest

from config.feature_flags import reset_features, set_feature
from src.ai.budgets import measure_narrative_length, resolve_information_budget
from src.ai.summary_generator import SummaryGenerator, compact_display_summary
from src.game.game_loop import GameLoop
from src.game.state import PlayerState


@pytest.mark.parametrize(
    ("kind", "language", "target_min", "target_max", "unit"),
    [
        ("week", "zh", 80, 160, "characters"),
        ("week", "en", 50, 100, "words"),
        ("month", "zh", 180, 320, "characters"),
        ("month", "en", 120, 220, "words"),
        ("year", "zh", 350, 600, "characters"),
        ("year", "en", 220, 400, "words"),
        ("life", "zh", 500, 900, "characters"),
        ("life", "en", 320, 600, "words"),
    ],
)
def test_display_summary_budgets_are_localized(
    kind: str,
    language: str,
    target_min: int,
    target_max: int,
    unit: str,
) -> None:
    budget = resolve_information_budget(kind, language)
    assert (budget.target_min, budget.target_max) == (target_min, target_max)
    assert budget.compression_threshold == target_max
    assert budget.unit == unit


def test_chinese_compaction_keeps_only_complete_sentences() -> None:
    text = "第一件事完整结束。" * 30 + "不应留下的半句"
    budget = resolve_information_budget("week", "zh")

    result = compact_display_summary(text, budget)

    assert result.endswith("。")
    assert "半句" not in result
    assert measure_narrative_length(result, "zh") <= budget.compression_threshold


def test_english_compaction_counts_words_and_ends_at_sentence_boundary() -> None:
    sentence = "The team completed a careful review of the archived evidence. "
    text = sentence * 30 + "unfinished fragment"
    budget = resolve_information_budget("week", "en")

    result = compact_display_summary(text, budget)

    assert result.endswith(".")
    assert "unfinished fragment" not in result
    assert measure_narrative_length(result, "en") <= budget.compression_threshold


@pytest.mark.parametrize(
    ("language", "text", "ending"),
    [
        ("zh", "这是一段尚未带句号的展示摘要", "。"),
        ("en", "This display summary has no terminal punctuation", "."),
    ],
)
def test_short_display_summary_is_normalized_to_a_complete_sentence(
    language: str,
    text: str,
    ending: str,
) -> None:
    result = compact_display_summary(text, resolve_information_budget("week", language))

    assert result.endswith(ending)


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("zh", "一个没有任何句末标点的超长摘要" * 100),
        ("en", "unfinished " * 200),
    ],
)
def test_single_oversized_fragment_cannot_bypass_display_threshold(
    language: str,
    text: str,
) -> None:
    budget = resolve_information_budget("week", language)

    result = compact_display_summary(text, budget)

    assert result.endswith(("。", "！", "？", ".", "!", "?"))
    assert measure_narrative_length(result, language) <= budget.compression_threshold


class _DisplayClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict[str, object]] = []

    def call_with_retry(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return self.response


def test_shared_display_generation_injects_budget_and_compacts_response() -> None:
    client = _DisplayClient("完整的一周结束了。" * 40 + "残句")
    generator = SummaryGenerator(client)  # type: ignore[arg-type]

    result = generator.generate_display_summary(
        summary_kind="week",
        prompt="请根据证据总结。",
        language="zh",
        fallback="本周记录仍在整理。",
    )

    assert "80-160字" in str(client.calls[0]["user_prompt"])
    assert result.endswith("。")
    assert "残句" not in result


def test_structured_memory_flag_stops_display_prose_from_becoming_model_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop = object.__new__(GameLoop)
    loop.player_state = PlayerState()
    loop.player_state.four_week_summaries = [{"summary": "legacy month prose"}]
    loop.player_state.yearly_summaries = [{"summary": "legacy year prose"}]
    monkeypatch.setattr("src.game.game_loop.random.random", lambda: 0.0)
    try:
        set_feature("structured_story_memory", False)
        assert loop._select_display_summary_context() == (
            "legacy month prose",
            "legacy year prose",
        )

        set_feature("structured_story_memory", True)
        assert loop._select_display_summary_context() == (None, None)
    finally:
        reset_features()
