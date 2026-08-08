"""Semantic boundaries for qualitative economic narrative.

Economic circumstances may remain part of the story. Exact monetary amounts,
balances, and retired wealth-resource state must not become authoritative game
state or long-term grounding evidence.
"""

from __future__ import annotations

import re
from typing import Any

_NUMBER = r"(?:\d[\d,]*(?:\.\d+)?|[零〇一二两三四五六七八九十百千万亿]+)"
_CURRENCY_AMOUNT = re.compile(
    rf"(?:[¥￥$€£]\s*{_NUMBER}|{_NUMBER}\s*(?:万|亿)?\s*"
    r"(?:元|块钱|人民币|美元|美金|欧元|英镑|rmb|cny|usd|yuan|dollars?))",
    re.IGNORECASE,
)
_BALANCE_WITH_NUMBER = re.compile(
    rf"(?:账户余额|帐户余额|余额|存款|净资产|财富值?|"
    rf"account balance|bank balance|savings|net worth|wealth)\D{{0,12}}{_NUMBER}",
    re.IGNORECASE,
)
_TRACKED_WEALTH_RESOURCE = re.compile(
    r"(?:当前财富(?:值|资源|状态)?|财富值|财富资源|"
    r"current wealth|wealth (?:stat|score|resource|state))",
    re.IGNORECASE,
)


def _joined_text(*values: Any) -> str:
    return " ".join(str(value).strip() for value in values if value is not None)


def contains_precise_financial_fact(*values: Any) -> bool:
    """Return whether text encodes an exact monetary fact or balance."""
    text = _joined_text(*values)
    return bool(_CURRENCY_AMOUNT.search(text) or _BALANCE_WITH_NUMBER.search(text))


def contains_tracked_wealth_state(*values: Any) -> bool:
    """Return whether text treats retired wealth/balance as tracked state."""
    text = _joined_text(*values)
    if _TRACKED_WEALTH_RESOURCE.search(text):
        return True
    return bool(_BALANCE_WITH_NUMBER.search(text))
