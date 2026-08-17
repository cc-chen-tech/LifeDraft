"""Deterministic public contracts for narrative consistency validators."""

from types import SimpleNamespace

from src.ai.harness.cause_effect_validator import CauseEffectConsistencyValidator
from src.ai.harness.info_barrier_validator import InformationBarrierValidator
import pytest

pytestmark = [pytest.mark.unit]



class TestCauseEffectConsistencyContracts:
    def test_overdue_pending_chain_requires_a_consequence(self):
        context = {
            "player_state": {},
            "world_model": SimpleNamespace(
                current_week=7,
                causal_chains=[
                    {
                        "trigger_event": "帮助王二",
                        "trigger_week": 3,
                        "expected_consequences": ["王二感恩"],
                        "actual_consequences": [],
                        "status": "pending",
                    }
                ],
            ),
        }

        passed, evidence, details = CauseEffectConsistencyValidator().validate(
            "洛阳城一切如常，王二独自离开了。", context
        )

        assert passed is False
        assert "因果后果违规" in evidence
        assert details["causal_chain_issues"][0]["trigger_event"] == "帮助王二"

    def test_opposite_consequence_is_reported_even_before_deadline(self):
        context = {
            "player_state": {},
            "world_model": SimpleNamespace(
                current_week=7,
                causal_chains=[
                    {
                        "trigger_event": "帮助王二",
                        "trigger_week": 6,
                        "expected_consequences": ["王二感恩"],
                        "actual_consequences": [],
                        "status": "pending",
                    }
                ],
            ),
        }

        passed, _, details = CauseEffectConsistencyValidator().validate(
            "王二决定报复李逍遥，派人堵住了城门。", context
        )

        assert passed is False
        assert details["causal_chain_issues"][0]["contradiction"] == "预期'感恩'但出现'报复'"

    def test_explicit_expected_consequence_resolves_an_overdue_chain(self):
        context = {
            "player_state": {},
            "world_model": SimpleNamespace(
                current_week=7,
                causal_chains=[
                    {
                        "trigger_event": "帮助王二",
                        "trigger_week": 3,
                        "expected_consequences": ["王二感恩"],
                        "actual_consequences": [],
                        "status": "pending",
                    }
                ],
            ),
        }

        passed, evidence, details = CauseEffectConsistencyValidator().validate(
            "王二感恩地送来了一封谢信。", context
        )

        assert passed is True
        assert evidence == ""
        assert details["causal_chain_issues"] == []


class TestInformationBarrierContracts:
    def test_unknown_secret_in_speech_is_rejected(self):
        context = {
            "character_knowledge_sets": {
                "王二": {"knows": ["洛阳城有药铺"], "secrets_unknown": ["藏宝图线索"]}
            }
        }

        passed, evidence, details = InformationBarrierValidator().validate(
            "王二说：我知道藏宝图线索藏在城西。", context
        )

        assert passed is False
        assert "信息屏障违规" in evidence
        assert details["barrier_violations"][0]["secret"] == "藏宝图线索"

    def test_configured_knowledge_is_allowed(self):
        context = {
            "character_knowledge_sets": {
                "王二": {"knows": ["洛阳城有药铺"], "secrets_unknown": []}
            }
        }

        passed, evidence, details = InformationBarrierValidator().validate(
            "王二说：我知道洛阳城有药铺。", context
        )

        assert passed is True
        assert evidence == ""
        assert details["barrier_violations"] == []

    def test_world_model_knowledge_source_is_honored(self):
        context = {
            "world_model": SimpleNamespace(
                character_knowledge_sets={
                    "赵灵儿": {"knows": [], "secrets_unknown": ["藏宝图"]}
                }
            )
        }

        passed, _, details = InformationBarrierValidator().validate(
            "赵灵儿说：藏宝图就在城西。", context
        )

        assert passed is False
        assert details["barrier_violations"][0]["character"] == "赵灵儿"
