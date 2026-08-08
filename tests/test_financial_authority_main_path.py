"""Main-path contracts preventing money facts from becoming continuity authority."""

from config.prompts._helpers import _build_established_facts_context
from config.prompts.world_prompts import get_world_extraction_prompt
from src.game.continuity_ledger import ContinuityLedger
from src.game.state import PlayerState
from src.game.world_model import WorldModel


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
