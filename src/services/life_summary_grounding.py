"""Evidence and timeline boundaries for generated life summaries."""

from __future__ import annotations

import re
from typing import List, Mapping, Sequence

from src.ai.professional_risk import apply_professional_risk_guardrail


StoryItem = Mapping[str, object]
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_REMOVED_METRICS = ("精力", "情绪", "学识", "财富", "energy", "mood", "knowledge", "wealth")
_LEGAL_ENDORSEMENTS = ("合规路径", "合法合规", "完全合法", "符合法律规定", "compliant path")
_INFLATED_DURATION = ("半年", "一年", "数年", "half a year", "one year", "several years")
_LIFE_SUMMARY_EVIDENCE_MAX_CHARS = 24_000
_COMPACT_STORY_MAX_CHARS = 360
_COMPACT_CHOICE_MAX_CHARS = 120


def _as_text(item: StoryItem, key: str) -> str:
    value = item.get(key, "")
    return value if isinstance(value, str) else ""


def _source_text(story_history: Sequence[StoryItem]) -> str:
    parts: List[str] = []
    for item in story_history:
        story = _as_text(item, "story_text")
        choice = _as_text(item, "choice_text")
        if story:
            parts.append(story)
        if choice:
            parts.append(choice)
    source = "\n".join(parts)
    if len(source) <= _LIFE_SUMMARY_EVIDENCE_MAX_CHARS:
        return source

    entries = [
        item
        for item in story_history
        if _as_text(item, "story_text").strip() or _as_text(item, "choice_text").strip()
    ]
    if not entries:
        return source[:_LIFE_SUMMARY_EVIDENCE_MAX_CHARS]

    max_entries = max(1, _LIFE_SUMMARY_EVIDENCE_MAX_CHARS // 520)
    selected_count = min(len(entries), max_entries)
    if selected_count == 1:
        selected_entries = [entries[0]]
    else:
        selected_entries = [
            entries[round(index * (len(entries) - 1) / (selected_count - 1))]
            for index in range(selected_count)
        ]

    compact_entries: List[str] = []
    for item in selected_entries:
        week = item.get("week")
        week_label = f"第{int(week) + 1}周" if isinstance(week, int) else "未标注周次"
        story = _truncate_evidence(_as_text(item, "story_text"), _COMPACT_STORY_MAX_CHARS)
        choice = _truncate_evidence(_as_text(item, "choice_text"), _COMPACT_CHOICE_MAX_CHARS)
        entry_parts = [week_label]
        if story:
            entry_parts.append(f"事件：{story}")
        if choice:
            entry_parts.append(f"选择：{choice}")
        compact_entries.append("；".join(entry_parts))

    return "\n".join(compact_entries)[:_LIFE_SUMMARY_EVIDENCE_MAX_CHARS]


def _truncate_evidence(text: str, limit: int) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _range_label(start_week: int, end_week: int) -> str:
    return f"第{start_week}周" if start_week == end_week else f"第{start_week}-{end_week}周"


def build_life_summary_prompt(
    story_history: Sequence[StoryItem], start_week: int, end_week: int
) -> str:
    """Build an evidence-only provider prompt for an inclusive week range."""
    label = _range_label(start_week, end_week)
    return f"""请为{label}的人生故事生成一段总结（300-500字）。

【事实与时间硬约束】
- 只使用下方故事证据和选择，不得补写未出现的人物身份、事件、数字、法律结论或资源状态。
- 时间范围只能写成“{label}”或等价的{end_week - start_week + 1}周，不得夸大为半年、数月或更长时期。
- 如果不同回合对身份、病情、招标、注册或其他事实存在冲突，必须明确保留为冲突或未决，不得自行合并成确定事实。
- 对“规避竞业”、借用亲属名义或类似行为，不得称为合规路径、合法方案或已经解决的法律风险。
- 不要提及精力、情绪、学识、财富等游戏资源指标。

【故事证据】
{_source_text(story_history)}

请用第三人称叙述，只返回总结正文。"""


def build_grounded_fallback(
    story_history: Sequence[StoryItem], start_week: int, end_week: int
) -> str:
    """Create a deterministic summary from bounded source excerpts."""
    excerpts: List[str] = []
    for item in story_history:
        story = _as_text(item, "story_text").strip()
        if story and story not in excerpts:
            excerpts.append(story)

    body = " ".join(excerpts[:8]) or "这段时间的故事记录仍在整理。"
    source = _source_text(story_history)
    caution = ""
    if any(marker in source for marker in ("规避竞业", "亲属名义", "母亲名义")):
        caution = " 相关做法存在争议与风险，不能据此认定法律或合规问题已经解决。"
    return f"{_range_label(start_week, end_week)}：{body}{caution}"


def _has_unsupported_number(
    summary: str, story_history: Sequence[StoryItem], start_week: int, end_week: int
) -> bool:
    source_numbers = set(_NUMBER_PATTERN.findall(_source_text(story_history)))
    allowed = source_numbers | {str(start_week), str(end_week), str(end_week - start_week + 1)}
    return any(number not in allowed for number in _NUMBER_PATTERN.findall(summary))


def validate_or_fallback_life_summary(
    summary: str,
    story_history: Sequence[StoryItem],
    start_week: int,
    end_week: int,
) -> str:
    """Return provider text only when it respects deterministic safety gates."""
    lowered = summary.lower()
    span = end_week - start_week + 1
    unsafe = (
        not summary.strip()
        or any(metric.lower() in lowered for metric in _REMOVED_METRICS)
        or any(claim.lower() in lowered for claim in _LEGAL_ENDORSEMENTS)
        or (span <= 8 and any(duration.lower() in lowered for duration in _INFLATED_DURATION))
        or _has_unsupported_number(summary, story_history, start_week, end_week)
    )
    if unsafe:
        return build_grounded_fallback(story_history, start_week, end_week)
    return apply_professional_risk_guardrail(summary.strip(), language="zh")
