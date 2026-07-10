"""Factual-safety boundary for AI-generated world settings."""

from __future__ import annotations

import re
from typing import Dict, Mapping


_ZH_QUALIFIER = "故事设定假设，不代表现实法规或统计："
_EN_QUALIFIER = "Fictional story assumption, not real legal or statistical guidance: "
_AUTHORITY_MARKERS = (
    "法规",
    "法定",
    "认证",
    "备案",
    "审批",
    "监管要求",
    "官方要求",
    "强制要求",
    "GDP",
    "国内生产总值",
    "风险投资",
    "venture capital",
    "certification",
    "regulation",
    "regulatory requirement",
    "official requirement",
)
_PRECISION_PATTERN = re.compile(
    r"(?:"
    r"\d+(?:\.\d+)?\s*%"
    r"|\d+\s*[-—–~至到]\s*\d+\s*(?:个?月|天|年|周|months?|days?|years?|weeks?)"
    r"|[（(][A-Z][A-Z0-9-]{1,9}[）)]"
    r")",
    re.IGNORECASE,
)


def _needs_qualification(text: str) -> bool:
    lowered = text.lower()
    return bool(_PRECISION_PATTERN.search(text)) or any(
        marker.lower() in lowered for marker in _AUTHORITY_MARKERS
    )


def qualify_generated_world_facts(
    world_setting: Mapping[str, object], language: str = "zh"
) -> Dict[str, object]:
    """Label precise generated claims before persistence or prompt reuse."""
    qualifier = _ZH_QUALIFIER if language == "zh" else _EN_QUALIFIER
    qualified: Dict[str, object] = dict(world_setting)
    for field, value in world_setting.items():
        if not isinstance(value, str):
            continue
        if value.startswith((_ZH_QUALIFIER, _EN_QUALIFIER)):
            continue
        if _needs_qualification(value):
            qualified[field] = f"{qualifier}{value}"
    return qualified
