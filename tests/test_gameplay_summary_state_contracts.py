"""Provider-free contracts for gameplay state and summary responses."""

from __future__ import annotations

import pytest

from src.ai.models import EventOption, GameEvent
from src.api.routers.gameplay.summary import generate_summary, get_game_state
from src.api.schemas import GenerateSummaryRequest
from src.api.services.session_service import session_service
from src.game.game_loop import GameLoop
from src.game.state import PlayerState

pytestmark = [pytest.mark.unit]



class _UnavailableCompletion:
    def generate_completion(self, **kwargs):
        _ = kwargs
        raise RuntimeError("local completion unavailable")


def _loop(*, week: int, current_round: int, round_history: list[dict] | None = None) -> GameLoop:
    game_loop = GameLoop(language="zh", ai_generator=_UnavailableCompletion(), quality_level="master")
    game_loop.player_state = PlayerState(
        player_name="林岚",
        age=28,
        week=week,
        current_round=current_round,
        round_history=round_history or [],
    )
    return game_loop


@pytest.mark.asyncio
async def test_game_state_preserves_active_event_progress_and_narrative_style() -> None:
    game_id = 781_001
    user_id = 761_001
    game_loop = _loop(week=7, current_round=2)
    game_loop.narrative_style_id = "chinese_classic_saga"
    game_loop.current_event = GameEvent(
        event_description="林岚在旧档案室发现导师留下的线索。",
        options=[
            EventOption(text="继续整理", effects={}),
            EventOption(text="先核对目录", effects={}),
        ],
    )
    session_service.put(game_id, game_loop, user_id=user_id, language="zh")

    try:
        response = await get_game_state(game_id, user_id=user_id)

        assert response.game_id == game_id
        assert response.progress == {"age": 28, "week": 7, "year": 0}
        assert response.round_info == {"current_round": 2, "game_over": False}
        assert response.current_event["event_description"] == game_loop.current_event.event_description
        assert response.constraint_level == "master"
        assert response.narrative_style_id == "chinese_classic_saga"
        assert response.narrative_style_name
    finally:
        session_service.remove(game_id, user_id=user_id)


@pytest.mark.asyncio
async def test_summary_bounds_recent_weeks_and_uses_grounded_fallback() -> None:
    game_id = 781_002
    user_id = 761_002
    history = [
        {
            "week": 0,
            "round": 1,
            "event_description": "林岚入职社区图书馆。",
            "story_continuation": "她熟悉了新的同事。",
            "choice": "先整理借阅记录",
        },
        {
            "week": 1,
            "round": 1,
            "event_description": "林岚调查缺失的馆藏。",
            "story_continuation": "她找到一份旧目录。",
            "choice": "联系导师核对",
        },
        {
            "week": 2,
            "round": 2,
            "event_description": "林岚研究社区档案。",
            "story_continuation": "她确认了关键时间线。",
            "choice": "记录新的发现",
        },
    ]
    game_loop = _loop(week=2, current_round=2, round_history=history)
    session_service.put(game_id, game_loop, user_id=user_id, language="zh")

    try:
        response = await generate_summary(
            game_id, GenerateSummaryRequest(weeks=2), user_id=user_id
        )

        assert response["start_week"] == 2
        assert response["end_week"] == 3
        assert response["story_count"] == 2
        assert "研究社区档案" in response["summary_text"]
        assert "入职社区图书馆" not in response["summary_text"]
    finally:
        session_service.remove(game_id, user_id=user_id)


@pytest.mark.asyncio
async def test_summary_empty_history_returns_just_started_response() -> None:
    game_id = 781_003
    user_id = 761_003
    game_loop = _loop(week=4, current_round=0)
    session_service.put(game_id, game_loop, user_id=user_id, language="zh")

    try:
        response = await generate_summary(game_id, GenerateSummaryRequest(), user_id=user_id)

        assert response == {
            "start_week": 1,
            "end_week": 5,
            "summary_text": "你的人生故事刚刚开始，还没有足够的经历可以总结。",
        }
    finally:
        session_service.remove(game_id, user_id=user_id)
