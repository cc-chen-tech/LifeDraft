"""Latency contracts for the on-demand life-summary endpoint."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.api.routers.gameplay import summary
from src.api.schemas import GenerateSummaryRequest


class RecordingSummaryGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_completion(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return "第1周，林晓完成了项目调研，并决定继续查证。"


class TimedOutSummaryGenerator:
    def generate_completion(self, **_kwargs: object) -> str:
        raise TimeoutError("provider deadline exceeded")


def test_life_summary_uses_a_short_provider_deadline(monkeypatch) -> None:
    """A user-visible summary must not inherit the five-minute general AI timeout."""
    generator = RecordingSummaryGenerator()
    player = SimpleNamespace(
        week=0,
        round_history=[
            {
                "week": 0,
                "round": 0,
                "event_description": "林晓完成了项目调研。",
                "story_continuation": "她决定继续查证。",
                "choice": "继续查证",
            }
        ],
        decision_history=[],
    )
    game_loop = SimpleNamespace(player_state=player, ai_generator=generator)
    monkeypatch.setattr(
        summary.session_service,
        "get_or_restore",
        lambda _game_id, _user_id: SimpleNamespace(game_loop=game_loop),
    )

    result = asyncio.run(
        summary.generate_summary(1, GenerateSummaryRequest(weeks=52), user_id=None)
    )

    assert result["summary_text"]
    assert generator.calls[0]["request_timeout"] <= 30


def test_life_summary_timeout_returns_grounded_fallback_without_mutating_history(monkeypatch) -> None:
    history = [
        {
            "week": 0,
            "round": 0,
            "event_description": "林晓完成了项目调研。",
            "story_continuation": "她决定继续查证。",
            "choice": "继续查证",
        }
    ]
    player = SimpleNamespace(week=0, round_history=history, decision_history=[])
    game_loop = SimpleNamespace(player_state=player, ai_generator=TimedOutSummaryGenerator())
    monkeypatch.setattr(
        summary.session_service,
        "get_or_restore",
        lambda _game_id, _user_id: SimpleNamespace(game_loop=game_loop),
    )

    result = asyncio.run(
        summary.generate_summary(1, GenerateSummaryRequest(weeks=52), user_id=None)
    )

    assert result["summary_text"].startswith("第1周：林晓完成了项目调研。\n她决定继续查证。")
    assert player.round_history == history
