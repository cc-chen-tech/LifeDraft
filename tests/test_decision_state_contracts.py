"""Provider-free contracts for deterministic choice application."""

from src.game.decisions import process_decision
from src.game.state import CharacterState, PlayerState
import pytest

pytestmark = [pytest.mark.unit]



class TestDecisionStateContracts:
    def test_choice_updates_resources_and_history_once_for_same_event(self):
        player = PlayerState(week=12, current_round=1, energy=95, mood=5, knowledge=98)
        option = {"text": "支付报名费", "effects": {"energy": 20, "mood": -20, "knowledge": 10}}

        first = process_decision(player, "资格考试报名", 0, [option], generate_result_text=False)
        second = process_decision(player, "资格考试报名", 0, [option], generate_result_text=False)

        assert first["success"] is True
        assert second["result_text"] == ""
        assert (player.energy, player.mood, player.knowledge) == (100, 0, 100)
        assert len(player.decision_history) == 2
        assert player.decision_history[0]["effects"] == option["effects"]

    def test_choice_syncs_known_character_affinity_and_records_effect_details(self):
        player = PlayerState(week=4)
        player.characters["林小鹿"] = CharacterState(name="林小鹿", affinity=50, trust=50).model_dump()
        player.relationships["林小鹿"] = 50
        option = {"text": "帮助林小鹿", "effects": {"relationships": {"林小鹿": 6}}}

        result = process_decision(player, "林小鹿需要协助", 0, [option], generate_result_text=False)

        assert result["success"] is True
        assert player.relationships["林小鹿"] == player.characters["林小鹿"]["affinity"]
        assert player.relationships["林小鹿"] > 50
        details = player.decision_history[-1]["character_effects"]["林小鹿"]
        assert details["affinity"] == 6
        assert details["trust"] == 2
