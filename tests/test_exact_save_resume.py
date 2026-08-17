"""Exact saved-phase recovery contracts for P1-4."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.routers.gameplay.events import (
    _require_resume_view_acknowledged,
    acknowledge_resume_view,
)
from src.api.routers.gameplay.sse_helpers import _set_generation_resume_view
from src.api.routers.games import _mark_orphaned_generation_interrupted
from src.game.state import PlayerState

pytestmark = [pytest.mark.unit]



def test_player_state_serializes_exact_resume_view() -> None:
    state = PlayerState(
        week=3,
        current_round=1,
        resume_view={
            "phase": "result",
            "story_text": "第4周周一完整结果",
            "completed_week": 3,
            "completed_round": 0,
        },
    )

    restored = PlayerState.from_dict(state.to_dict())

    assert restored.resume_view == state.resume_view


def test_event_generation_is_blocked_while_saved_result_awaits_user() -> None:
    game_loop = SimpleNamespace(
        player_state=PlayerState(resume_view={"phase": "result"})
    )

    with pytest.raises(HTTPException) as exc_info:
        _require_resume_view_acknowledged(game_loop)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "saved_view_pending"


@pytest.mark.asyncio
async def test_acknowledge_clears_and_persists_saved_result() -> None:
    player_state = PlayerState(resume_view={"phase": "result", "story_text": "结果"})
    session = SimpleNamespace(game_loop=SimpleNamespace(player_state=player_state))
    db = MagicMock()

    with (
        patch(
            "src.api.deps.session_service.get_or_restore",
            return_value=session,
        ),
        patch("src.api.routers.gameplay.events.get_db", return_value=db),
    ):
        response = await acknowledge_resume_view(7, user_id=9)

    assert response == {"acknowledged": True}
    assert player_state.resume_view is None
    db.save_game_progress.assert_called_once_with(7, player_state)


def test_generation_and_failure_markers_are_persisted() -> None:
    player_state = PlayerState(week=2, current_round=1)
    game_loop = SimpleNamespace(
        player_state=player_state,
        get_state=lambda: player_state,
    )

    with patch(
        "src.api.routers.gameplay.sse_helpers._persist_generated_event_state"
    ) as persist:
        _set_generation_resume_view(game_loop, 11, "generating")
        assert player_state.resume_view["phase"] == "generating"
        _set_generation_resume_view(game_loop, 11, "failed", "provider timeout")

    assert player_state.resume_view["phase"] == "failed"
    assert player_state.resume_view["error"] == "provider timeout"
    assert persist.call_count == 2


def test_orphaned_generating_marker_becomes_retryable_failure() -> None:
    player_state = PlayerState(
        resume_view={"phase": "generating", "story_text": "已保存的部分正文"}
    )
    game_loop = SimpleNamespace(get_state=lambda: player_state)

    _mark_orphaned_generation_interrupted(game_loop)

    assert player_state.resume_view["phase"] == "failed"
    assert "恢复当前进度" in player_state.resume_view["error"]
    assert player_state.resume_view["story_text"] == "已保存的部分正文"
