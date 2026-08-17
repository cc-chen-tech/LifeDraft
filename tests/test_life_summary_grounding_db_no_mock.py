"""Real database history round-trip for grounded life summaries."""

from __future__ import annotations

from uuid import uuid4

from src.database.models import Game, GameState, SessionLocal, User, init_db
from src.services.life_summary_grounding import build_grounded_fallback
import pytest

pytestmark = [pytest.mark.integration]



def test_saved_four_week_history_builds_grounded_summary_after_real_read() -> None:
    init_db()
    session = SessionLocal()
    user_id: int | None = None
    game_id: int | None = None
    try:
        suffix = uuid4().hex[:10]
        user = User(
            public_id=f"LS{suffix[:6].upper()}",
            private_id=f"life-summary-{suffix}",
            display_name="人生总结测试",
        )
        session.add(user)
        session.flush()
        user_id = int(user.user_id)
        game = Game(user_id=user_id, language="zh", initial_state={"player_name": "林晓"})
        session.add(game)
        session.flush()
        game_id = int(game.game_id)
        history = [
            {
                "week": week,
                "round": 0,
                "story_text": f"第{week + 1}周原文事件",
                "choice_text": "继续查证",
            }
            for week in range(4)
        ]
        session.add(
            GameState(
                game_id=game_id,
                week=3,
                age=28,
                state_json={"player_name": "林晓", "round_history": history},
            )
        )
        session.commit()

        loaded = session.query(GameState).filter(GameState.game_id == game_id).one().state_json
        result = build_grounded_fallback(loaded["round_history"], start_week=1, end_week=4)

        assert result.startswith("第1-4周：")
        assert "第1周原文事件" in result
        assert "第4周原文事件" in result
    finally:
        if game_id is not None:
            session.query(GameState).filter(GameState.game_id == game_id).delete()
            session.query(Game).filter(Game.game_id == game_id).delete()
        if user_id is not None:
            session.query(User).filter(User.user_id == user_id).delete()
        session.commit()
        session.close()

