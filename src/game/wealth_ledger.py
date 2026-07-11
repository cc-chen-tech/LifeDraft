"""Authoritative, idempotent transaction audit for player wealth.

``PlayerState.wealth`` remains the single spendable balance. This ledger records
how gameplay changed that value and validates exact money claims in generated
text; prose can never update the balance.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

WEALTH_LEDGER_VERSION = 1
MAX_TRANSACTIONS = 2_000
MAX_CONFLICTS = 100

_NUMBER_PATTERN = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_DEFAULT_MONEY_UNITS = ("万元", "人民币", "美元", "元", "万", "块")
_BALANCE_WORDS = (
    "余额",
    "存款",
    "账户",
    "帐户",
    "财富",
    "资产",
    "身家",
    "手头",
    "钱包",
    "还剩",
    "剩下",
    "balance",
    "savings",
    "account",
    "net worth",
)
_CHANGE_WORDS = (
    "到账",
    "收入",
    "赚",
    "获得",
    "奖金",
    "报酬",
    "花费",
    "花了",
    "支付",
    "付了",
    "扣除",
    "损失",
    "支出",
    "增加",
    "减少",
    "earned",
    "received",
    "spent",
    "paid",
    "lost",
    "deducted",
)
_CLAUSE_BOUNDARIES = "。！？!?；;，,\n"


def _value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _set_value(target: Any, key: str, value: Any) -> None:
    if isinstance(target, dict):
        target[key] = value
    else:
        setattr(target, key, value)


def _int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


@dataclass(frozen=True)
class WealthTransaction:
    transaction_id: str
    opening_balance: int
    requested_delta: int
    applied_delta: int
    reason: str
    source_event_id: str
    week: int
    round_number: int
    closing_balance: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WealthTransaction":
        return cls(
            transaction_id=_text(data.get("transaction_id")),
            opening_balance=_int(data.get("opening_balance")),
            requested_delta=_int(data.get("requested_delta")),
            applied_delta=_int(data.get("applied_delta")),
            reason=_text(data.get("reason")),
            source_event_id=_text(data.get("source_event_id")),
            week=_int(data.get("week")),
            round_number=_int(data.get("round")),
            closing_balance=_int(data.get("closing_balance")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "opening_balance": self.opening_balance,
            "requested_delta": self.requested_delta,
            "applied_delta": self.applied_delta,
            "reason": self.reason,
            "source_event_id": self.source_event_id,
            "week": self.week,
            "round": self.round_number,
            "closing_balance": self.closing_balance,
        }


@dataclass(frozen=True)
class WealthClaimIssue:
    code: str
    observed_amount: int
    expected_amount: Optional[int]
    start: int
    end: int
    message: str


@dataclass
class WealthValidationResult:
    passed: bool
    issues: List[WealthClaimIssue] = field(default_factory=list)

    @property
    def fix_instructions(self) -> str:
        if not self.issues:
            return ""
        lines = ["\n\n【权威财富账本冲突，必须修正】"]
        lines.extend(f"- {issue.message}" for issue in self.issues)
        lines.append("只可使用账本支持的期初、变动和期末金额；否则删除精确数字。")
        return "\n".join(lines)


class WealthLedger:
    """Versioned transaction audit synchronized to ``PlayerState.wealth``."""

    def __init__(self, data: Optional[Mapping[str, Any]] = None):
        raw = copy.deepcopy(dict(data or {}))
        self.version = _int(raw.get("version"), WEALTH_LEDGER_VERSION)
        self.opening_balance = _int(raw.get("opening_balance"))
        self.balance_snapshot = _int(raw.get("balance_snapshot"), self.opening_balance)
        self.currency_name = _text(raw.get("currency_name")) or "元"
        self.transactions: List[WealthTransaction] = []
        for item in raw.get("transactions") or []:
            if isinstance(item, Mapping) and item.get("transaction_id"):
                self.transactions.append(WealthTransaction.from_dict(item))
        self.transactions = self.transactions[-MAX_TRANSACTIONS:]
        self.conflicts: List[Dict[str, Any]] = list(raw.get("conflicts") or [])[
            -MAX_CONFLICTS:
        ]

    @classmethod
    def from_player_state(cls, player_state: Any) -> "WealthLedger":
        stored = _value(player_state, "wealth_ledger", {})
        current_balance = max(0, _int(_value(player_state, "wealth", 0)))
        settings = _value(player_state, "character_settings", {})
        wealth_settings = (
            settings.get("wealth", {}) if isinstance(settings, Mapping) else {}
        )
        configured_currency = ""
        if isinstance(wealth_settings, Mapping):
            configured_currency = _text(
                wealth_settings.get("currency_name") or wealth_settings.get("currency")
            )
        if not isinstance(stored, Mapping) or not stored:
            ledger = cls(
                {
                    "version": WEALTH_LEDGER_VERSION,
                    "opening_balance": current_balance,
                    "balance_snapshot": current_balance,
                    "currency_name": configured_currency or "元",
                }
            )
            return ledger

        ledger = cls(stored)
        if configured_currency:
            ledger.currency_name = configured_currency
        uninitialized_default = (
            not ledger.transactions
            and not ledger.conflicts
            and ledger.opening_balance == 0
            and ledger.balance_snapshot == 0
        )
        if uninitialized_default:
            ledger.opening_balance = current_balance
            ledger.balance_snapshot = current_balance
            return ledger
        if "opening_balance" not in stored:
            ledger.opening_balance = current_balance
        if ledger.balance_snapshot != current_balance:
            ledger._append_conflict(
                code="balance_snapshot_mismatch",
                transaction_id="reconciliation",
                expected=current_balance,
                observed=ledger.balance_snapshot,
                source_event_id="player_state.wealth",
            )
            ledger.balance_snapshot = current_balance
        return ledger

    def to_dict(self, current_balance: Optional[int] = None) -> Dict[str, Any]:
        snapshot = (
            self.balance_snapshot
            if current_balance is None
            else max(0, current_balance)
        )
        return {
            "version": WEALTH_LEDGER_VERSION,
            "opening_balance": self.opening_balance,
            "balance_snapshot": snapshot,
            "currency_name": self.currency_name,
            "transactions": [
                transaction.to_dict() for transaction in self.transactions
            ],
            "conflicts": copy.deepcopy(self.conflicts[-MAX_CONFLICTS:]),
        }

    def persist(self, player_state: Any) -> None:
        current_balance = max(0, _int(_value(player_state, "wealth", 0)))
        self.balance_snapshot = current_balance
        _set_value(player_state, "wealth_ledger", self.to_dict(current_balance))

    def reset_opening_balance(self, player_state: Any, balance: int) -> None:
        """Rebase a not-yet-played character setup without fabricating a transaction."""
        target = max(0, _int(balance))
        if self.transactions:
            raise ValueError("Cannot reset opening wealth after transactions exist")
        self.opening_balance = target
        self.balance_snapshot = target
        _set_value(player_state, "wealth", target)
        self.persist(player_state)

    def find_transaction(self, transaction_id: str) -> Optional[WealthTransaction]:
        return next(
            (
                transaction
                for transaction in self.transactions
                if transaction.transaction_id == transaction_id
            ),
            None,
        )

    def apply_transaction(
        self,
        player_state: Any,
        *,
        transaction_id: str,
        requested_delta: int,
        reason: str,
        source_event_id: str,
        week: int,
        round_number: int,
    ) -> WealthTransaction:
        clean_id = _text(transaction_id)
        clean_source = _text(source_event_id)
        if not clean_id or not clean_source:
            raise ValueError(
                "Wealth transactions require stable transaction and source IDs"
            )
        requested = _int(requested_delta)
        existing = self.find_transaction(clean_id)
        if existing is not None:
            if (
                existing.requested_delta != requested
                or existing.reason != _text(reason)
                or existing.source_event_id != clean_source
            ):
                self._append_conflict(
                    code="transaction_id_conflict",
                    transaction_id=clean_id,
                    expected=existing.requested_delta,
                    observed=requested,
                    source_event_id=clean_source,
                )
                self.persist(player_state)
            return existing

        opening = max(0, _int(_value(player_state, "wealth", 0)))
        closing = max(0, opening + requested)
        transaction = WealthTransaction(
            transaction_id=clean_id,
            opening_balance=opening,
            requested_delta=requested,
            applied_delta=closing - opening,
            reason=_text(reason) or "gameplay wealth change",
            source_event_id=clean_source,
            week=max(0, _int(week)),
            round_number=max(0, _int(round_number)),
            closing_balance=closing,
        )
        self.transactions.append(transaction)
        self.transactions = self.transactions[-MAX_TRANSACTIONS:]
        _set_value(player_state, "wealth", closing)
        self.persist(player_state)
        return transaction

    def _append_conflict(
        self,
        *,
        code: str,
        transaction_id: str,
        expected: int,
        observed: int,
        source_event_id: str,
    ) -> None:
        self.conflicts.append(
            {
                "code": code,
                "transaction_id": transaction_id,
                "expected": expected,
                "observed": observed,
                "source_event_id": source_event_id,
            }
        )
        self.conflicts = self.conflicts[-MAX_CONFLICTS:]

    def build_constraints_text(self, current_balance: int, language: str = "zh") -> str:
        balance = max(0, _int(current_balance))
        recent = self.transactions[-8:]
        if language == "zh":
            lines = [
                "\n【权威财富账本 — 玩家数值财富是唯一余额来源】",
                f"当前权威余额：{self.format_amount(balance)}。",
                "没有交易支持时，禁止声称余额变化、收入到账或完成支付。",
            ]
            if recent:
                lines.append("最近交易：")
                for transaction in recent:
                    lines.append(
                        f"- [{transaction.transaction_id}] 期初{self.format_amount(transaction.opening_balance)}；"
                        f"变动{self.format_amount(transaction.applied_delta, signed=True)}；"
                        f"期末{self.format_amount(transaction.closing_balance)}；"
                        f"原因{transaction.reason}；来源{transaction.source_event_id}"
                    )
            return "\n".join(lines)

        lines = [
            "\n[Authoritative Wealth Ledger - PlayerState.wealth is the only balance authority]",
            f"Current authoritative balance: {balance:,}.",
            "Do not claim a balance change, received income, or completed payment without a transaction.",
        ]
        for transaction in recent:
            lines.append(
                f"- [{transaction.transaction_id}] opening {transaction.opening_balance:,}; "
                f"delta {transaction.applied_delta:+,}; closing {transaction.closing_balance:,}; "
                f"reason {transaction.reason}; source {transaction.source_event_id}"
            )
        return "\n".join(lines)

    def format_amount(self, amount: int, *, signed: bool = False) -> str:
        rendered = f"{amount:+,}" if signed else f"{amount:,}"
        return f"{rendered}{self.currency_name}"

    def _money_pattern(self) -> re.Pattern[str]:
        units = sorted(
            {*_DEFAULT_MONEY_UNITS, self.currency_name}, key=len, reverse=True
        )
        unit_pattern = "|".join(re.escape(unit) for unit in units if unit)
        return re.compile(rf"(?:[¥￥$]\s*)?{_NUMBER_PATTERN}\s*(?:{unit_pattern})")

    def validate_narrative(
        self,
        text: str,
        *,
        current_balance: int,
        active_transaction_id: Optional[str] = None,
        allowed_transaction_ids: Optional[Iterable[str]] = None,
    ) -> WealthValidationResult:
        if not text:
            return WealthValidationResult(passed=True)
        allowed_transactions: List[WealthTransaction] = []
        if active_transaction_id:
            active = self.find_transaction(active_transaction_id)
            if active is not None:
                allowed_transactions.append(active)
        for transaction_id in allowed_transaction_ids or []:
            transaction = self.find_transaction(transaction_id)
            if transaction is not None and transaction not in allowed_transactions:
                allowed_transactions.append(transaction)
        allowed_change_amounts = {
            abs(transaction.applied_delta)
            for transaction in allowed_transactions
            if transaction.applied_delta
        }
        aggregate_delta = sum(
            transaction.applied_delta for transaction in allowed_transactions
        )
        if aggregate_delta:
            allowed_change_amounts.add(abs(aggregate_delta))
        issues: List[WealthClaimIssue] = []
        for match in self._money_pattern().finditer(text):
            amount = _parse_amount(match.group(0))
            category = _claim_category(text, match.start(), match.end())
            if category == "balance" and amount != current_balance:
                issues.append(
                    WealthClaimIssue(
                        code="balance_claim_mismatch",
                        observed_amount=amount,
                        expected_amount=current_balance,
                        start=match.start(),
                        end=match.end(),
                        message=(
                            f"权威余额为{current_balance:,}，正文却声称余额{amount:,}"
                        ),
                    )
                )
            elif category == "change":
                if not allowed_change_amounts:
                    issues.append(
                        WealthClaimIssue(
                            code="unsupported_money_change",
                            observed_amount=amount,
                            expected_amount=None,
                            start=match.start(),
                            end=match.end(),
                            message=f"没有交易支持正文中的{amount:,}金额变化",
                        )
                    )
                elif amount not in allowed_change_amounts:
                    expected_amount = min(
                        allowed_change_amounts,
                        key=lambda candidate: abs(candidate - amount),
                    )
                    issues.append(
                        WealthClaimIssue(
                            code="transaction_amount_mismatch",
                            observed_amount=amount,
                            expected_amount=expected_amount,
                            start=match.start(),
                            end=match.end(),
                            message=(
                                f"账本支持的金额变动为{sorted(allowed_change_amounts)}，"
                                f"正文却写{amount:,}"
                            ),
                        )
                    )
        return WealthValidationResult(passed=not issues, issues=issues)

    def sanitize_narrative(
        self,
        text: str,
        validation: WealthValidationResult,
        *,
        current_balance: int,
    ) -> str:
        sanitized = text
        replacements: Dict[tuple[int, int], str] = {}
        for issue in validation.issues:
            if issue.code == "balance_claim_mismatch":
                replacement = self.format_amount(max(0, current_balance))
            elif issue.expected_amount is not None:
                replacement = self.format_amount(issue.expected_amount)
            else:
                replacement = "一笔款项"
            replacements[(issue.start, issue.end)] = replacement
        for (start, end), replacement in sorted(replacements.items(), reverse=True):
            sanitized = sanitized[:start] + replacement + sanitized[end:]
        return sanitized

    def record_validation_conflicts(
        self,
        issues: Iterable[WealthClaimIssue],
        *,
        source_event_id: str,
    ) -> None:
        for issue in issues:
            self.conflicts.append(
                {
                    "code": issue.code,
                    "transaction_id": "narrative-claim",
                    "expected": issue.expected_amount,
                    "observed": issue.observed_amount,
                    "source_event_id": source_event_id,
                }
            )
        self.conflicts = self.conflicts[-MAX_CONFLICTS:]


def _parse_amount(raw: str) -> int:
    number_match = re.search(r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?", raw)
    if not number_match:
        return 0
    value = float(number_match.group(0).replace(",", ""))
    if "万" in raw:
        value *= 10_000
    return int(round(value))


def _claim_category(text: str, start: int, end: int) -> str:
    clause_start = max(
        (text.rfind(boundary, 0, start) for boundary in _CLAUSE_BOUNDARIES), default=-1
    )
    following_boundaries = [
        position
        for boundary in _CLAUSE_BOUNDARIES
        if (position := text.find(boundary, end)) >= 0
    ]
    clause_end = min(following_boundaries) if following_boundaries else len(text)
    before = text[clause_start + 1 : start].lower()
    after = text[end:clause_end].lower()
    segment = before + after
    balance_distance = _nearest_keyword_distance(segment, before, _BALANCE_WORDS)
    change_distance = _nearest_keyword_distance(segment, before, _CHANGE_WORDS)
    if balance_distance is not None and (
        change_distance is None or balance_distance <= change_distance
    ):
        return "balance"
    if change_distance is not None:
        return "change"
    return "other"


def _nearest_keyword_distance(
    segment: str, before: str, keywords: Iterable[str]
) -> Optional[int]:
    distances: List[int] = []
    pivot = len(before)
    for keyword in keywords:
        search_from = 0
        while True:
            position = segment.find(keyword, search_from)
            if position < 0:
                break
            distances.append(abs(pivot - (position + len(keyword))))
            search_from = position + 1
    return min(distances) if distances else None
