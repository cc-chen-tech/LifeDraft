"""Real-database contracts for SSE-visible rewrite and recovery state."""

from src.ai.models import EventOption, GameEvent, StoryDeliveryNotice
from src.api.routers.gameplay.sse_helpers import (
    _set_generation_resume_view,
    persist_rewritten_current_event,
)
from src.database.models import Game, SessionLocal
from src.database.singletons import get_game_db
from src.game.state import PlayerState


class _GameLoop:
    def __init__(self, player_state: PlayerState, current_event: GameEvent) -> None:
        self.player_state = player_state
        self.current_event = current_event

    def get_state(self) -> PlayerState:
        return self.player_state


def _create_game(player_state: PlayerState) -> int:
    session = SessionLocal()
    try:
        game = Game(language="zh", initial_state=player_state.to_dict())
        session.add(game)
        session.commit()
        return int(game.game_id)
    finally:
        session.close()


def _event(description: str) -> GameEvent:
    return GameEvent(
        event_description=description,
        options=[
            EventOption(text="继续调查", effects={"knowledge": 3}),
            EventOption(text="暂时离开", effects={"mood": 1}),
        ],
    )


def test_rewritten_current_event_survives_real_database_reload() -> None:
    state = PlayerState(
        player_name="林岚",
        age=27,
        week=3,
        current_round=1,
        current_event_data={
            "event_description": "旧版本故事",
            "story_text": "旧版本故事",
            "scene_id": "scene-rewrite-contract",
            "delivery_notice": {
                "code": "SOFT_VALIDATION_FALLBACK",
                "summary": "旧提示",
                "reason": "旧原因",
                "retryable": True,
                "attempts_used": 3,
            },
            "options": [{"text": "继续调查", "effects": {"knowledge": 3}}],
        },
    )
    game_id = _create_game(state)
    current_event = _event("旧版本故事")
    current_event.delivery_notice = StoryDeliveryNotice(
        summary="旧提示",
        reason="旧原因",
        attempts_used=3,
    )
    loop = _GameLoop(state, current_event)

    persist_rewritten_current_event(loop, game_id, "重写后的最终故事")

    loaded = get_game_db().load_game_state(game_id)
    assert loop.current_event.event_description == "重写后的最终故事"
    assert loop.current_event.delivery_notice is None
    assert loaded is not None
    assert loaded["current_event_data"] == {
        "event_description": "重写后的最终故事",
        "story_text": "重写后的最终故事",
        "scene_id": "scene-rewrite-contract",
        "options": [
            {"text": "继续调查", "effects": {"knowledge": 3}, "likely_choice": False},
            {"text": "暂时离开", "effects": {"mood": 1}, "likely_choice": False},
        ],
    }


def test_failed_generation_resume_view_survives_real_database_reload() -> None:
    state = PlayerState(player_name="周宁", age=31, week=6, current_round=2)
    game_id = _create_game(state)
    loop = _GameLoop(state, _event("等待生成的故事"))

    _set_generation_resume_view(loop, game_id, "failed", "provider timeout")

    loaded = get_game_db().load_game_state(game_id)
    assert loaded is not None
    assert loaded["resume_view"] == {
        "phase": "failed",
        "story_text": "",
        "round_summary": "",
        "summary_text": "",
        "error": "provider timeout",
        "completed_week": 6,
        "completed_round": 2,
    }
