"""Latency contracts for the on-demand life-summary endpoint."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.api.routers.gameplay import summary
from src.api import deps as _deps
from src.api.schemas import GenerateSummaryRequest
from src.utils.financial_narrative import (
    contains_precise_financial_fact,
    contains_tracked_wealth_state,
)

pytestmark = [pytest.mark.unit]



class RecordingSummaryGenerator:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate_completion(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return "第1周，林晓完成了项目调研，并决定继续查证。"


class TimedOutSummaryGenerator:
    def generate_completion(self, **_kwargs: object) -> str:
        raise TimeoutError("provider deadline exceeded")


class UnsafeSummaryGenerator:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate_completion(self, **_kwargs: object) -> str:
        return self.response


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
        _deps.session_service,
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


@pytest.mark.parametrize(
    "provider_summary",
    (
        "第1周，林晓的账户余额达到USD 8,000，存款继续增长。",
        "第1周，林晓的账户余额有所改善，当前财富值也有所提升。",
        "第1周，林晓的存款快要见底。",
    ),
)
def test_rejected_provider_money_state_returns_safe_generated_summary(
    monkeypatch, provider_summary: str
) -> None:
    history = [
        {
            "week": 0,
            "round": 0,
            "event_description": (
                "林晓的账户余额达到USD 8,000，财富并非人生目标，她一直重视家人。"
            ),
            "story_continuation": "她的存款快要见底，但仍面临经济压力，消费也更加谨慎。",
            "choice": "月薪8000，同时陪伴家人",
        }
    ]
    player = SimpleNamespace(week=0, round_history=history, decision_history=[])
    game_loop = SimpleNamespace(
        player_state=player,
        ai_generator=UnsafeSummaryGenerator(provider_summary),
    )
    monkeypatch.setattr(
        summary.session_service,
        "get_or_restore",
        lambda _game_id, _user_id: SimpleNamespace(game_loop=game_loop),
    )

    result = asyncio.run(
        summary.generate_summary(1, GenerateSummaryRequest(weeks=52), user_id=None)
    )
    final_summary = result["summary_text"]

    assert not contains_precise_financial_fact(final_summary)
    assert not contains_tracked_wealth_state(final_summary)
    assert "8,000" not in final_summary
    assert "000" not in final_summary
    assert "账户余额" not in final_summary
    assert "存款" not in final_summary
    assert "月薪8000" not in final_summary
    assert "财富并非人生目标" in final_summary
    assert "经济压力" in final_summary
