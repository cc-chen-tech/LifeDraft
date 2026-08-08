"""Semantic boundaries for qualitative economic narrative.

Economic circumstances may remain part of the story. Exact monetary amounts,
balances, and retired wealth-resource state must not become authoritative game
state or long-term grounding evidence.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

_ARABIC_NUMBER = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_ZH_NUMBER = r"[零〇一二两三四五六七八九十百千万亿]+"
_CURRENCY_CODE = r"(?<![A-Za-z])(?:USD|RMB|CNY|EUR|GBP|JPY|HKD)(?![A-Za-z])"
_CURRENCY_NAME = (
    r"(?:元(?!里|二次|组)|块钱|人民币|美元|美金|欧元|英镑|日元|港元|" r"yuan\b|dollars?\b)"
)
_CURRENCY_AMOUNT = re.compile(
    rf"(?:[¥￥$€£]\s*{_ARABIC_NUMBER}|{_CURRENCY_CODE}\s*{_ARABIC_NUMBER}|"
    rf"(?:{_ARABIC_NUMBER}|{_ZH_NUMBER})\s*(?:万|亿)?\s*"
    rf"(?:{_CURRENCY_NAME}|{_CURRENCY_CODE}))",
    re.IGNORECASE,
)
_RESOURCE_NUMBER = re.compile(rf"{_ARABIC_NUMBER}(?![\d年月周岁天日个%％])")
_FINANCIAL_RESOURCE_HEAD = re.compile(
    r"(?:财富值|财富资源|财富|账户余额|帐户余额|余额|存款|净资产|月薪|年薪|工资|薪资|"
    r"\baccount\s+balance\b|\bbank\s+balance\b|\bbalance\b|\bsavings\b|"
    r"\bnet\s+worth\b|\bwealth\b|\bsalar(?:y|ies)\b|\bwages?\b)",
    re.IGNORECASE,
)
_PLAIN_WEALTH_HEAD = re.compile(r"(?:财富(?!值|资源)|\bwealth\b)", re.IGNORECASE)
_NON_TRACKING_WEALTH_VALUE = re.compile(
    r"(?:财富\s*(?:并非|不是|并不是|不等于).{0,18}(?:人生|生活|幸福|成功|唯一)?"
    r".{0,8}(?:目标|标准|意义)|"
    r"\bwealth\s+(?:is\s+)?not\s+.{0,24}(?:goal|measure|meaning))",
    re.IGNORECASE,
)
_STRUCTURED_FINANCIAL_CATEGORIES = frozenset({"financial", "wealth"})

# A comma is punctuation only when it is not the separator between two digits.
# Keeping numeric commas intact prevents an unsafe ``USD 8,000`` clause from
# being reduced to an apparently harmless ``000`` fragment during sanitizing.
_CLAUSE_SEPARATOR = re.compile(r"[；;。！？!?\n]+|(?<!\d)[，,]|[，,](?!\d)")


def _text_values(values: Iterable[Any]) -> Iterable[str]:
    for value in values:
        if value is not None:
            text = str(value).strip()
            if text:
                yield text


def split_narrative_clauses(text: str) -> list[str]:
    """Split narrative prose without splitting thousands separators."""
    return [clause.strip() for clause in _CLAUSE_SEPARATOR.split(text) if clause.strip()]


def _clauses(*values: Any) -> Iterable[str]:
    for text in _text_values(values):
        yield from split_narrative_clauses(text)


def is_structured_financial_category(value: Any) -> bool:
    """Return whether a structured fact category represents retired money state."""
    return isinstance(value, str) and value.strip().lower() in _STRUCTURED_FINANCIAL_CATEGORIES


def contains_precise_financial_fact(*values: Any) -> bool:
    """Return whether text encodes an exact monetary fact."""
    for clause in _clauses(*values):
        if _CURRENCY_AMOUNT.search(clause):
            return True
        if _FINANCIAL_RESOURCE_HEAD.search(clause) and _RESOURCE_NUMBER.search(clause):
            return True
    return False


def _is_non_tracking_wealth_value(clause: str) -> bool:
    heads = list(_FINANCIAL_RESOURCE_HEAD.finditer(clause))
    return bool(
        heads
        and all(_PLAIN_WEALTH_HEAD.fullmatch(match.group(0)) for match in heads)
        and _NON_TRACKING_WEALTH_VALUE.search(clause)
        and not _CURRENCY_AMOUNT.search(clause)
    )


def contains_tracked_wealth_state(*values: Any) -> bool:
    """Return whether text treats a financial resource as tracked state.

    A resource head is authoritative by default. This boundary deliberately
    does not depend on an enumerable list of verbs such as "rose" or "fell".
    Explicit value statements about wealth are the narrow exception.
    """
    for clause in _clauses(*values):
        if _FINANCIAL_RESOURCE_HEAD.search(clause) and not _is_non_tracking_wealth_value(clause):
            return True
    return False


def contains_authoritative_financial_state(*values: Any) -> bool:
    """Return whether values encode exact money or cross-turn money state."""
    return contains_precise_financial_fact(*values) or contains_tracked_wealth_state(*values)


def sanitize_authoritative_financial_clauses(text: str) -> str:
    """Drop unsafe clauses and guarantee the returned text satisfies the boundary."""
    normalized = text.strip()
    if not normalized:
        return ""
    if not contains_authoritative_financial_state(normalized):
        return normalized

    safe = [
        clause
        for clause in split_narrative_clauses(normalized)
        if not contains_authoritative_financial_state(clause)
    ]
    result = "；".join(safe)
    return "" if contains_authoritative_financial_state(result) else result
