"""P2-性能优化：PlayerState.to_prompt_context 字段投影契约。"""

from typing import Any

from src.game.round.event_generator import RoundEventGenerator
from src.game.state import PlayerState


def _make_state() -> PlayerState:
    state = PlayerState(
        player_name="林岚",
        week=10,
        current_round=1,
        story_history=[{"week": w, "story": f"第{w}周故事"} for w in range(10)],
        four_week_summaries=[{"start_week": 0, "summary": "摘要"}],
        yearly_summaries=[],
        weekly_summaries=[{"week": 9, "summary": "周摘要"}],
        round_history=[
            {"week": 10, "round": r, "event_description": f"回合{r}"} for r in range(6)
        ],
        decision_history=[
            {"week": w, "choice_text": f"选择{w}"} for w in range(40)
        ],
        emotional_arc_history=[{"week": 9, "valence": 0.5}],
        novelty_scores=[{"week": 9, "score": 0.8}],
        world_breathing_events=[{"event": "背景事件", "week": 9}],
    )
    return state


def test_to_prompt_context_trims_histories_and_drops_irrelevant_keys() -> None:
    state = _make_state()
    ctx = state.to_prompt_context(recent_rounds=3, recent_decisions=30)

    assert len(ctx["round_history"]) == 3
    assert ctx["round_history"][-1]["event_description"] == "回合5"
    assert len(ctx["decision_history"]) == 30
    assert ctx["decision_history"][-1]["choice_text"] == "选择39"

    for key in (
        "story_history",
        "four_week_summaries",
        "yearly_summaries",
        "weekly_summaries",
        "emotional_arc_history",
        "novelty_scores",
        "world_breathing_events",
    ):
        assert key not in ctx

    # 生成仍需要的字段保留
    assert ctx["player_name"] == "林岚"
    assert ctx["week"] == 10
    assert ctx["current_round"] == 1
    assert ctx["character_settings"] == {}


def test_to_dict_remains_complete() -> None:
    """持久化/响应继续使用完整 to_dict()，不受投影影响。"""
    state = _make_state()
    full = state.to_dict()

    assert len(full["round_history"]) == 6
    assert len(full["decision_history"]) == 40
    assert len(full["story_history"]) == 10
    assert "four_week_summaries" in full


def test_round_event_prompt_context_falls_back_for_legacy_state_adapter() -> None:
    """Old state adapters without the optimization API remain usable."""

    class LegacyState:
        def to_dict(self) -> dict[str, Any]:
            return {"player_name": "林岚", "round_history": [{"round": 1}]}

    assert RoundEventGenerator._prompt_context(LegacyState()) == {
        "player_name": "林岚",
        "round_history": [{"round": 1}],
    }
