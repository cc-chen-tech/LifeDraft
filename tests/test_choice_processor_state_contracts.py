"""Deterministic state contracts for round choice processing."""

from src.game.round.choice_processor import RoundChoiceProcessor
from src.game.state import PlayerState


def _processor(state: PlayerState) -> RoundChoiceProcessor:
    return RoundChoiceProcessor(
        player_state_getter=lambda: state,
        ai_generator=object(),
        language_getter=lambda: "zh",
        story_service=object(),
        current_event_getter=lambda: None,
        current_event_setter=lambda event: None,
    )


def _state(**overrides: object) -> PlayerState:
    values: dict[str, object] = {
        "player_name": "林岚",
        "week": 3,
        "current_round": 2,
        "energy": 2,
        "mood": 99,
        "knowledge": 100,
        "wealth": 50,
        "character_settings": {"wealth": {"currency_name": "元"}},
    }
    values.update(overrides)
    return PlayerState(**values)


def test_effect_normalization_clamps_resources_and_reports_applied_deltas() -> None:
    state = _state()
    processor = _processor(state)

    effects, warnings = processor._normalize_effects_for_current_state(
        {"energy": -9, "mood": 6, "knowledge": 3, "wealth": -100}
    )

    assert effects == {"energy": -2, "mood": 1, "knowledge": 0, "wealth": -50}
    by_resource = {warning["resource"]: warning for warning in warnings}
    assert by_resource["energy"]["reason"] == "insufficient_resource"
    assert by_resource["energy"]["requested_delta"] == -9
    assert by_resource["energy"]["applied_delta"] == -2
    assert by_resource["mood"]["reason"] == "resource_cap"
    assert by_resource["mood"]["applied_delta"] == 1
    assert by_resource["knowledge"]["applied_delta"] == 0
    assert by_resource["wealth"]["applied_delta"] == -50


def test_choice_wealth_transaction_is_idempotent_and_rejects_boolean_delta() -> None:
    state = _state(wealth=100)
    processor = _processor(state)

    transaction_id = processor._apply_wealth_transaction(
        state, requested_delta=-150, reason="支付报名费"
    )
    duplicate_id = processor._apply_wealth_transaction(
        state, requested_delta=-150, reason="支付报名费"
    )
    invalid_id = processor._apply_wealth_transaction(
        state, requested_delta=True, reason="非法输入"
    )

    assert transaction_id == "choice:w3-r2"
    assert duplicate_id == transaction_id
    assert invalid_id is None
    assert state.wealth == 0
    transactions = state.wealth_ledger["transactions"]
    assert transactions == [
        {
            "transaction_id": "choice:w3-r2",
            "opening_balance": 100,
            "requested_delta": -150,
            "applied_delta": -100,
            "reason": "支付报名费",
            "source_event_id": "w3-r2",
            "week": 3,
            "round": 2,
            "closing_balance": 0,
        }
    ]
