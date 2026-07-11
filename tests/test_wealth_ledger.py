"""P1-8 regressions for the authoritative, source-linked wealth ledger."""

from __future__ import annotations

from src.game.state import PlayerState
from src.game.wealth_ledger import WealthLedger
from src.ai.text_quality import normalize_generated_story


def _state(wealth: int = 10_000) -> PlayerState:
    return PlayerState(
        player_name="林岚",
        wealth=wealth,
        week=0,
        current_round=0,
        character_settings={
            "wealth": {"currency": "¥", "currency_name": "元"},
        },
    )


def test_legacy_state_seeds_opening_balance_without_inventing_transactions() -> None:
    state = _state(50_000)

    ledger = WealthLedger.from_player_state(state)
    ledger.persist(state)

    assert ledger.opening_balance == 50_000
    assert ledger.transactions == []
    assert state.wealth == 50_000
    assert state.wealth_ledger["balance_snapshot"] == 50_000


def test_transaction_records_opening_delta_reason_source_and_closing_balance() -> None:
    state = _state(10_000)
    ledger = WealthLedger.from_player_state(state)

    transaction = ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=2_500,
        reason="接受设计委托",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    assert transaction.opening_balance == 10_000
    assert transaction.requested_delta == 2_500
    assert transaction.applied_delta == 2_500
    assert transaction.closing_balance == 12_500
    assert transaction.reason == "接受设计委托"
    assert transaction.source_event_id == "w0-r0"
    assert state.wealth == 12_500
    assert (
        transaction.closing_balance
        == transaction.opening_balance + transaction.applied_delta
    )


def test_insufficient_funds_clamp_is_recorded_as_applied_delta() -> None:
    state = _state(1_000)
    ledger = WealthLedger.from_player_state(state)

    transaction = ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=-1_500,
        reason="购买设备",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    assert transaction.requested_delta == -1_500
    assert transaction.applied_delta == -1_000
    assert transaction.closing_balance == 0
    assert state.wealth == 0


def test_duplicate_transaction_is_idempotent_even_after_later_transactions() -> None:
    state = _state(10_000)
    ledger = WealthLedger.from_player_state(state)
    first = ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=-500,
        reason="支付报名费",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )
    ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r1",
        requested_delta=1_000,
        reason="获得奖金",
        source_event_id="w0-r1",
        week=0,
        round_number=1,
    )

    duplicate = ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=-500,
        reason="支付报名费",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    assert duplicate == first
    assert state.wealth == 10_500
    assert len(ledger.transactions) == 2


def test_conflicting_duplicate_does_not_change_balance_and_is_diagnostic() -> None:
    state = _state(10_000)
    ledger = WealthLedger.from_player_state(state)
    ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=-500,
        reason="支付报名费",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=5_000,
        reason="矛盾的重复请求",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    assert state.wealth == 9_500
    assert len(ledger.transactions) == 1
    assert ledger.conflicts[-1]["code"] == "transaction_id_conflict"


def test_twelve_rounds_remain_arithmetically_monotonic_and_source_linked() -> None:
    state = _state(10_000)
    ledger = WealthLedger.from_player_state(state)

    for sequence in range(12):
        week, round_number = divmod(sequence, 3)
        delta = 300 if sequence % 2 == 0 else -125
        ledger.apply_transaction(
            state,
            transaction_id=f"choice:w{week}-r{round_number}",
            requested_delta=delta,
            reason=f"第{sequence + 1}轮选择",
            source_event_id=f"w{week}-r{round_number}",
            week=week,
            round_number=round_number,
        )

    assert len(ledger.transactions) == 12
    assert state.wealth == 11_050
    for transaction in ledger.transactions:
        assert transaction.closing_balance == (
            transaction.opening_balance + transaction.applied_delta
        )
        assert transaction.source_event_id


def test_exact_current_balance_claim_is_supported() -> None:
    state = _state(10_500)
    ledger = WealthLedger.from_player_state(state)

    result = ledger.validate_narrative(
        "她查看账户，余额为10,500元。", current_balance=state.wealth
    )

    assert result.passed is True


def test_invented_balance_claim_is_rejected() -> None:
    state = _state(10_500)
    ledger = WealthLedger.from_player_state(state)

    result = ledger.validate_narrative(
        "她查看账户，余额为50,000元。", current_balance=state.wealth
    )

    assert result.passed is False
    assert result.issues[0].code == "balance_claim_mismatch"
    assert result.issues[0].expected_amount == 10_500


def test_money_change_without_transaction_cannot_be_declared_as_completed() -> None:
    state = _state(10_500)
    ledger = WealthLedger.from_player_state(state)

    result = ledger.validate_narrative(
        "项目奖金到账5,000元。", current_balance=state.wealth
    )

    assert result.passed is False
    assert result.issues[0].code == "unsupported_money_change"


def test_active_transaction_supports_matching_change_but_rejects_other_amount() -> None:
    state = _state(10_000)
    ledger = WealthLedger.from_player_state(state)
    ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=2_500,
        reason="项目奖金",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    supported = ledger.validate_narrative(
        "项目奖金到账2,500元，账户余额达到12,500元。",
        current_balance=state.wealth,
        active_transaction_id="choice:w0-r0",
    )
    rejected = ledger.validate_narrative(
        "项目奖金到账8,000元。",
        current_balance=state.wealth,
        active_transaction_id="choice:w0-r0",
    )

    assert supported.passed is True
    assert rejected.passed is False
    assert rejected.issues[0].code == "transaction_amount_mismatch"


def test_sanitizer_corrects_balance_and_removes_unsupported_precision() -> None:
    state = _state(10_500)
    ledger = WealthLedger.from_player_state(state)
    text = "她看到余额为50,000元。随后又收到奖金8,000元。"
    validation = ledger.validate_narrative(text, current_balance=state.wealth)

    sanitized = ledger.sanitize_narrative(
        text, validation, current_balance=state.wealth
    )

    assert "余额为10,500元" in sanitized
    assert "奖金一笔款项" in sanitized
    assert "50,000" not in sanitized
    assert "8,000" not in sanitized


def test_prompt_snapshot_names_balance_and_recent_transaction_source() -> None:
    state = _state(10_000)
    ledger = WealthLedger.from_player_state(state)
    ledger.apply_transaction(
        state,
        transaction_id="choice:w0-r0",
        requested_delta=-500,
        reason="支付报名费",
        source_event_id="w0-r0",
        week=0,
        round_number=0,
    )

    prompt = ledger.build_constraints_text(state.wealth, "zh")

    assert "当前权威余额：9,500元" in prompt
    assert "choice:w0-r0" in prompt
    assert "期初10,000" in prompt
    assert "变动-500" in prompt
    assert "期末9,500" in prompt


def test_chinese_punctuation_normalizer_preserves_money_grouping_commas() -> None:
    normalized = normalize_generated_story(
        "账户余额10,500元,可以支付费用.", language="zh"
    )

    assert normalized == "账户余额10,500元，可以支付费用。"


def test_ledger_uses_configured_currency_for_constraints_and_correction() -> None:
    state = _state(900)
    state.character_settings["wealth"] = {
        "currency": "贯",
        "currency_name": "贯",
    }
    ledger = WealthLedger.from_player_state(state)

    assert "900贯" in ledger.build_constraints_text(state.wealth)
    validation = ledger.validate_narrative("账户余额是1,200贯", current_balance=900)
    assert not validation.passed
    assert (
        ledger.sanitize_narrative("账户余额是1,200贯", validation, current_balance=900)
        == "账户余额是900贯"
    )
