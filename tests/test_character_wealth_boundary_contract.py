"""Regression contract for late character wealth after gameplay has started."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_late_character_wealth_does_not_reset_a_played_game_balance() -> None:
    db = MagicMock()
    db.load_saved_game.return_value = {
        "player_name": "沈若澜",
        "life_vision": "经营一家 AI 教育工作室",
        "age": 32,
        "week": 2,
        "current_round": 1,
        "round_history": [{"week": 0, "round": 0, "choice": "接受首份合同"}],
        "wealth": 78_000,
        "wealth_ledger": {
            "opening_balance": 50_000,
            "balance_snapshot": 78_000,
            "transactions": [
                {
                    "transaction_id": "contract-1",
                    "opening_balance": 50_000,
                    "requested_delta": 28_000,
                    "applied_delta": 28_000,
                    "reason": "首份合同",
                    "source_event_id": "round-0",
                    "week": 0,
                    "round": 0,
                    "closing_balance": 78_000,
                }
            ],
        },
        "character_settings": {"wealth": {"initial_wealth": 50_000}},
    }
    db.save_game_progress.return_value = True

    with patch("src.api.deps.decode_token", return_value=1), patch(
        "src.api.routers.games.get_db", return_value=db
    ), patch("src.api.routers.games.session_store") as session_store:
        session_store.get.return_value = None
        response = client.patch(
            "/api/games/109/character-settings",
            json={
                "character_settings": {
                    "wealth": {"initial_wealth": 120_000, "currency_name": "元"}
                }
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    saved_game_id, saved_player_state = db.save_game_progress.call_args.args
    saved_state = saved_player_state.to_dict()
    assert saved_game_id == 109
    assert saved_state["character_settings"]["wealth"]["initial_wealth"] == 120_000
    assert saved_state["wealth"] == 78_000
    assert saved_state["wealth_ledger"]["opening_balance"] == 50_000
    assert saved_state["wealth_ledger"]["balance_snapshot"] == 78_000
    assert saved_state["wealth_ledger"]["transactions"][0]["closing_balance"] == 78_000
