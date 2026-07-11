"""Deterministic guardrails for professional-risk guarantees in generated text.

The detector deliberately requires a professional domain marker and a strong
guarantee in the same sentence.  This keeps ordinary fictional danger and
uncertain discussions of law or medicine untouched.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

RiskDomain = Literal["legal", "medical"]

_LEGAL_DOMAIN = re.compile(
    r"竞业|法律|律师|合规|规避|监管|法规|审批|实际控制|代持|亲属名义|"
    r"母亲名义|父亲名义|父母名义|政策|备案|认证|税务|"
    r"\b(?:lawyer|legal|compliance|compliant|non[- ]?compete|regulat(?:ion|ory)|"
    r"actual control|beneficial owner|relative(?:'s)? name)\b",
    re.IGNORECASE,
)
_MEDICAL_DOMAIN = re.compile(
    r"治疗|病情|医疗|医生|用药|药物|手术|透析|诊断|疗效|"
    r"\b(?:medical|medicine|doctor|clinician|treatment|therapy|surgery|"
    r"diagnosis|drug|medication|dialysis)\b",
    re.IGNORECASE,
)
_GUARANTEE = re.compile(
    r"零风险|无风险|没有风险|几乎(?:没有|不存在).{0,4}风险|风险几乎为零|"
    r"风险可控|保证合法|完全合法|绝对合法|合法合规(?:的路径)?|确保合规|合规路径|"
    r"绝对安全|万无一失|肯定没问题|保证不会有任何风险|不会有任何风险|"
    r"\b(?:zero[- ]risk|no risk|risk[- ]free|guaranteed (?:legal|compliant|safe)|"
    r"completely legal|absolutely (?:legal|safe)|compliant path|foolproof)\b",
    re.IGNORECASE,
)

_ZH_LEGAL_CAUTION = (
    "现实中的法律与合规结论取决于具体事实；涉及亲属名义、实际控制、利益冲突或"
    "规避义务时尤其存在风险，应由有资质的法律专业人士复核。"
)
_ZH_MEDICAL_CAUTION = (
    "医疗结果因个体情况而异，安全性和疗效均不能预先保证，应由有资质的医疗专业人士评估。"
)
_EN_LEGAL_CAUTION = (
    " Real-world legal and compliance outcomes depend on the specific facts; arrangements involving "
    "a relative's name, actual control, conflicts of interest, or evasion of obligations carry risk "
    "and should be reviewed by a qualified legal professional."
)
_EN_MEDICAL_CAUTION = " Medical outcomes vary by individual and cannot be guaranteed; consult a qualified medical professional."

_ZH_REPLACEMENTS = (
    (re.compile(r"合法合规(?:的路径)?|合规路径|确保合规"), "尚需专业复核的方案"),
    (re.compile(r"保证合法|完全合法|绝对合法"), "法律结论仍需结合具体事实判断"),
    (
        re.compile(
            r"零风险|无风险|没有风险|几乎(?:没有|不存在).{0,4}风险|风险几乎为零|"
            r"保证不会有任何风险|不会有任何风险|万无一失|肯定没问题"
        ),
        "存在现实风险和不确定性",
    ),
    (re.compile(r"风险可控"), "风险需要结合具体事实审慎评估"),
    (re.compile(r"绝对安全"), "安全性仍需审慎评估"),
)
_EN_REPLACEMENTS = (
    (
        re.compile(r"\b(?:compliant path|guaranteed compliant)\b", re.I),
        "a proposal requiring professional review",
    ),
    (
        re.compile(r"\b(?:guaranteed legal|completely legal|absolutely legal)\b", re.I),
        "legally uncertain",
    ),
    (
        re.compile(r"\b(?:zero[- ]risk|no risk|risk[- ]free|foolproof)\b", re.I),
        "subject to real risks and uncertainty",
    ),
    (
        re.compile(r"\b(?:guaranteed safe|absolutely safe)\b", re.I),
        "requiring an individualized safety assessment",
    ),
)


def _domain_for_sentence(sentence: str) -> Optional[RiskDomain]:
    if _LEGAL_DOMAIN.search(sentence):
        return "legal"
    if _MEDICAL_DOMAIN.search(sentence):
        return "medical"
    return None


def find_unsafe_professional_claims(text: str, language: str = "auto") -> list[str]:
    """Return sentences that combine professional advice with a guarantee."""
    del language  # Patterns intentionally recognize both supported languages.
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?；;\n])|(?<=[.])\s+", text or "")
        if sentence.strip()
        and _domain_for_sentence(sentence)
        and _GUARANTEE.search(sentence)
    ]


def apply_professional_risk_guardrail(text: str, language: str = "auto") -> str:
    """Qualify unsafe professional guarantees while preserving the fictional event."""
    if not text:
        return text

    english = language == "en" or (
        language == "auto"
        and bool(re.search(r"[A-Za-z]{4}", text))
        and not re.search(r"[\u4e00-\u9fff]", text)
    )
    parts = re.split(r"(?<=[。！？!?；;\n])|(?<=[.])(?=\s)", text)
    guarded: list[str] = []
    for sentence in parts:
        domain = _domain_for_sentence(sentence)
        if not domain or not _GUARANTEE.search(sentence):
            guarded.append(sentence)
            continue

        replacements = _EN_REPLACEMENTS if english else _ZH_REPLACEMENTS
        rewritten = sentence
        for pattern, replacement in replacements:
            rewritten = pattern.sub(replacement, rewritten)

        caution = (
            _EN_LEGAL_CAUTION
            if english and domain == "legal"
            else (
                _EN_MEDICAL_CAUTION
                if english
                else _ZH_LEGAL_CAUTION if domain == "legal" else _ZH_MEDICAL_CAUTION
            )
        )
        caution_marker = "qualified" if english else "有资质的"
        if caution_marker not in rewritten:
            if not english and rewritten.endswith(("。", "！", "？", "；")):
                rewritten += caution
            else:
                rewritten = rewritten.rstrip() + caution
        guarded.append(rewritten)

    return "".join(guarded)
