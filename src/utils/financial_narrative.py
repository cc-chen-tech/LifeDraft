"""Semantic boundaries for qualitative economic narrative.

Economic circumstances may remain part of the story. Exact monetary amounts,
balances, and retired wealth-resource state must not become authoritative game
state or long-term grounding evidence.
"""

from __future__ import annotations

import re
from typing import Any

_ARABIC_NUMBER = r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
_ZH_NUMBER = r"[零〇一二两三四五六七八九十百千万亿]+"
_CURRENCY_CODE = r"(?:USD|RMB|CNY|EUR|GBP|JPY|HKD)"
_CURRENCY_NAME = r"(?:元|块钱|人民币|美元|美金|欧元|英镑|日元|港元|yuan|dollars?)"
_CURRENCY_AMOUNT = re.compile(
    rf"(?:[¥￥$€£]\s*{_ARABIC_NUMBER}|{_CURRENCY_CODE}\s*{_ARABIC_NUMBER}|"
    rf"(?:{_ARABIC_NUMBER}|{_ZH_NUMBER})\s*(?:万|亿)?\s*"
    rf"(?:{_CURRENCY_NAME}|{_CURRENCY_CODE}))",
    re.IGNORECASE,
)
_BALANCE_WITH_NUMBER = re.compile(
    rf"(?:账户余额|帐户余额|余额|存款|净资产|财富值?|"
    rf"account balance|bank balance|savings|net worth|wealth)\s*"
    rf"(?:(?:为|是|达到|达|有|剩余|超过|低于|增加到|升至|降至|reached|is|was|at)\s*)?"
    rf"[:：]?\s*(?:[¥￥$€£]|{_CURRENCY_CODE})?\s*"
    rf"(?:{_ARABIC_NUMBER}|{_ZH_NUMBER})(?![年月周岁天日个%％])",
    re.IGNORECASE,
)
_TRACKED_WEALTH_RESOURCE = re.compile(
    r"(?:当前(?:财富值?|存款|净资产)|财富值|财富资源|账户余额|帐户余额|"
    r"(?:财富|存款|净资产)(?:仍在|继续|有所|正在|已经|将会|会)?"
    r"(?:增长|增加|提升|减少|下降|改善|恶化|保持|剩余|达到|超过|低于)|"
    r"account balance|bank balance|current (?:wealth|savings|net worth)|"
    r"wealth (?:stat|score|resource|state)|"
    r"(?:wealth|savings|net worth) (?:grew|increased|improved|decreased|fell|remained|reached))",
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


def contains_authoritative_financial_state(*values: Any) -> bool:
    """Return whether values encode exact money or cross-turn money state."""
    return contains_precise_financial_fact(*values) or contains_tracked_wealth_state(
        *values
    )
