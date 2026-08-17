"""Main-path contracts preventing money facts from becoming continuity authority."""

from config.prompts._helpers import _build_established_facts_context
from config.prompts.world_prompts import get_world_extraction_prompt
from src.game.continuity_ledger import ContinuityLedger
from src.game.state import PlayerState
from src.game.world_model import WorldModel
from src.game.world_model_updater import WorldModelUpdater
import pytest

pytestmark = [pytest.mark.unit]



def _legacy_authority_state() -> PlayerState:
    return PlayerState.from_dict(
        {
            "player_name": "林岚",
            "age": 28,
            "week": 3,
            "current_round": 0,
            "character_settings": {"era": {"year": 2026}},
            "established_facts": [
                {
                    "subject": "林岚",
                    "category": "career",
                    "fact": "月薪8000元",
                    "established_week": 1,
                },
                {
                    "subject": "林岚",
                    "category": "economic_context",
                    "fact": "家庭经济压力加剧，消费更加谨慎",
                    "established_week": 1,
                },
            ],
            "continuity_ledger": {
                "version": 1,
                "timeline": [
                    {
                        "event_id": "w1-r0",
                        "week": 1,
                        "round": 0,
                        "date_info": {},
                        "summary": "账户余额达到50000元，但家庭仍面临经济压力",
                        "choice": "接受月薪8000元的职位",
                        "status": "committed",
                    }
                ],
                "mutable_states": {
                    "health": {},
                    "relationships": {},
                    "facts": {
                        "career:林岚": {
                            "subject": "林岚",
                            "category": "career",
                            "fact": "月薪8000元",
                            "source_event_id": "w1-r0",
                        },
                        "economic_context:林岚": {
                            "subject": "林岚",
                            "category": "economic_context",
                            "fact": "家庭经济压力加剧，消费更加谨慎",
                            "source_event_id": "w1-r0",
                        },
                    },
                },
            },
        }
    )


def test_legacy_authority_is_sanitized_before_serialization_and_world_prompt() -> None:
    state = _legacy_authority_state()
    serialized_before_world_model = state.to_dict()
    world_model = WorldModel.from_player_state(state)
    constraints = world_model.build_constraints_text("zh")
    serialized = state.to_dict()

    assert [fact["fact"] for fact in state.established_facts] == [
        "家庭经济压力加剧，消费更加谨慎"
    ]
    assert "50000" not in constraints
    assert "月薪8000" not in constraints
    assert "家庭仍面临经济压力" in constraints
    assert "家庭经济压力加剧" in constraints
    assert "career:林岚" not in serialized_before_world_model["continuity_ledger"][
        "mutable_states"
    ]["facts"]
    assert "career:林岚" not in serialized["continuity_ledger"]["mutable_states"]["facts"]


def test_player_state_serialization_reapplies_financial_authority_boundary() -> None:
    state = PlayerState(player_name="林岚")
    state.established_facts = [
        {"subject": "林岚", "category": "career", "fact": "月薪8000元"},
        {
            "subject": "林岚",
            "category": "economic_context",
            "fact": "家庭经济压力加剧",
        },
    ]
    state.continuity_ledger = {
        "timeline": [
            {
                "event_id": "w0-r0",
                "week": 0,
                "round": 0,
                "summary": "账户余额达到50000元，但家庭仍面临经济压力",
                "choice": "接受月薪8000元的职位",
            }
        ],
        "mutable_states": {
            "facts": {
                "career:林岚": {
                    "subject": "林岚",
                    "category": "career",
                    "fact": "月薪8000元",
                }
            }
        },
    }

    serialized = state.to_dict()

    assert [fact["fact"] for fact in serialized["established_facts"]] == [
        "家庭经济压力加剧"
    ]
    assert serialized["continuity_ledger"]["timeline"][0]["summary"] == (
        "但家庭仍面临经济压力"
    )
    assert serialized["continuity_ledger"]["timeline"][0]["choice"] == ""
    assert serialized["continuity_ledger"]["mutable_states"]["facts"] == {}


def test_committed_event_sanitizes_timeline_and_fact_authority() -> None:
    ledger = ContinuityLedger()

    ledger.record_committed_event(
        event_id="w0-r0",
        week=0,
        round_number=0,
        date_info={},
        summary="账户余额达到50000元，但家庭仍面临经济压力",
        choice="接受月薪8000元的职位",
        story_text="她接受了新工作，但家庭仍面临经济压力。",
        fact_updates=[
            {
                "action": "new",
                "subject": "林岚",
                "category": "financial",
                "fact": "家庭经济压力加剧",
            },
            {
                "action": "new",
                "subject": "林岚",
                "category": "career",
                "fact": "月薪8000元",
            },
            {
                "action": "new",
                "subject": "林岚",
                "category": "economic_context",
                "fact": "家庭经济压力加剧，消费更加谨慎",
            },
        ],
    )

    assert ledger.timeline[0]["summary"] == "但家庭仍面临经济压力"
    assert ledger.timeline[0]["choice"] == ""
    assert [record["fact"] for record in ledger.mutable_states["facts"].values()] == [
        "家庭经济压力加剧，消费更加谨慎"
    ]
    constraints = ledger.build_constraints_text("zh")
    assert "50000" not in constraints
    assert "月薪8000" not in constraints
    assert "家庭经济压力加剧" in constraints


def test_established_fact_prompt_boundaries_drop_money_authority() -> None:
    facts = [
        {
            "subject": "结构化财务",
            "category": "financial",
            "fact": "经济压力属于财务类别",
        },
        {"subject": "林岚", "category": "career", "fact": "月薪8000元"},
        {
            "subject": "林岚",
            "category": "economic_context",
            "fact": "家庭经济压力加剧，消费更加谨慎",
        },
    ]

    established_context = _build_established_facts_context(facts, "zh")
    extraction_prompt = get_world_extraction_prompt(
        "她换了工作，但仍面临经济压力。",
        "谨慎消费",
        "zh",
        established_facts=facts,
    )

    for prompt in (established_context, extraction_prompt):
        assert "月薪8000" not in prompt
        assert "结构化财务" not in prompt
        assert "家庭经济压力加剧，消费更加谨慎" in prompt


def test_structured_world_updates_reject_money_authority_and_keep_qualitative_context() -> None:
    state = PlayerState(player_name="林岚", week=2)

    WorldModelUpdater.process_career_updates(
        state,
        [
            {"action": "change", "character": "林岚", "new_role": "月薪8000元的产品经理"},
            {"action": "change", "character": "周宁", "new_role": "经济援助项目协调员"},
        ],
    )
    WorldModelUpdater.process_commitment_updates(
        state,
        [
            {"action": "new", "description": "承诺偿还5000元债务", "parties": ["林岚"]},
            {"action": "new", "description": "在经济压力下互相支持", "parties": ["周宁"]},
        ],
    )
    WorldModelUpdater.process_causal_updates(
        state,
        [
            {
                "action": "new",
                "cause": "账户余额不足5000元",
                "expected_consequence": "需要偿还2000元",
            },
            {
                "action": "new",
                "cause": "家庭消费压力加剧",
                "expected_consequence": "生活选择更加谨慎",
            },
        ],
    )

    data = state.world_model_data
    assert set(data["career_records"]) == {"周宁"}
    assert [item["description"] for item in data["active_commitments"]] == [
        "在经济压力下互相支持"
    ]
    assert [item["cause"] for item in data["causal_chains"]] == ["家庭消费压力加剧"]


def test_legacy_structured_world_authority_is_filtered_on_load_prompt_and_serialize() -> None:
    state = PlayerState(
        player_name="林岚",
        week=3,
        world_model_data={
            "career_records": {
                "林岚": {"current_job": "月薪8000元的产品经理", "employer": "星河科技"},
                "周宁": {"current_job": "经济援助项目协调员", "employer": "社区中心"},
            },
            "active_commitments": [
                {"description": "承诺偿还5000元债务", "parties": ["林岚"]},
                {"description": "在经济压力下互相支持", "parties": ["周宁"]},
            ],
            "causal_chains": [
                {
                    "cause": "奖金到账5000元",
                    "expected_consequence": "账户余额提升",
                },
                {
                    "cause": "家庭消费压力加剧",
                    "expected_consequence": "生活选择更加谨慎",
                },
            ],
        },
    )

    world = WorldModel.from_player_state(state)
    constraints = world.build_constraints_text("zh")
    serialized = world.to_dict()
    serialized_text = str(serialized)

    assert set(world.career_records) == {"周宁"}
    assert [item.description for item in world.active_commitments] == [
        "在经济压力下互相支持"
    ]
    assert [item.cause for item in world.causal_chains] == ["家庭消费压力加剧"]
    for forbidden in ("8000", "5000", "账户余额"):
        assert forbidden not in constraints
        assert forbidden not in serialized_text
    for expected in ("经济援助项目协调员", "在经济压力下互相支持", "家庭消费压力加剧"):
        assert expected in constraints
        assert expected in serialized_text


def test_player_state_load_and_save_sanitize_structured_world_authority() -> None:
    state = PlayerState.from_dict(
        {
            "player_name": "林岚",
            "world_model_data": {
                "career_records": {
                    "林岚": {"current_job": "月薪8000元的产品经理"},
                    "周宁": {"current_job": "经济援助项目协调员"},
                },
                "active_commitments": [
                    {"description": "承诺偿还5000元债务"},
                    {"description": "在经济压力下互相支持"},
                ],
                "causal_chains": [
                    {"cause": "付款2000元", "expected_consequence": "余额改善"},
                    {"cause": "家庭消费压力加剧", "expected_consequence": "生活选择更加谨慎"},
                ],
            },
        }
    )

    assert set(state.world_model_data["career_records"]) == {"周宁"}
    assert len(state.world_model_data["active_commitments"]) == 1
    assert len(state.world_model_data["causal_chains"]) == 1
    serialized = str(state.to_dict()["world_model_data"])
    assert "经济援助项目协调员" in serialized
    assert "家庭消费压力加剧" in serialized
    for forbidden in ("8000", "5000", "2000", "余额改善"):
        assert forbidden not in serialized


def test_world_updater_cleans_existing_containers_before_merging() -> None:
    state = PlayerState(
        player_name="林岚",
        world_model_data={
            "career_records": {"林岚": {"current_job": "月薪8000元的产品经理"}},
            "active_commitments": [{"description": "偿还5000元债务", "status": "pending"}],
            "causal_chains": [{"cause": "付款2000元", "expected_consequence": "余额改善"}],
        },
    )

    WorldModelUpdater.process_career_updates(
        state, [{"action": "change", "character": "周宁", "new_role": "经济援助项目协调员"}]
    )
    WorldModelUpdater.process_commitment_updates(
        state, [{"action": "new", "description": "在经济压力下互相支持"}]
    )
    WorldModelUpdater.process_causal_updates(
        state,
        [{"action": "new", "cause": "家庭消费压力加剧", "expected_consequence": "生活选择更加谨慎"}],
    )

    serialized = str(state.world_model_data)
    assert "经济援助项目协调员" in serialized
    assert "在经济压力下互相支持" in serialized
    assert "家庭消费压力加剧" in serialized
    for forbidden in ("8000", "5000", "2000", "余额改善"):
        assert forbidden not in serialized


def test_causal_updater_alone_cleans_existing_financial_authority() -> None:
    state = PlayerState(
        world_model_data={
            "causal_chains": [
                {"cause": "付款2000元", "expected_consequence": "账户余额改善"}
            ]
        }
    )

    WorldModelUpdater.process_causal_updates(
        state,
        [
            {
                "action": "new",
                "cause": "家庭消费压力加剧",
                "expected_consequence": "生活选择更加谨慎",
            }
        ],
    )

    serialized = str(state.world_model_data["causal_chains"])
    assert "家庭消费压力加剧" in serialized
    assert "2000" not in serialized
    assert "账户余额" not in serialized
