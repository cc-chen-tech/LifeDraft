"""Evidence and timeline boundaries for generated life summaries."""

from __future__ import annotations

from dataclasses import replace
import re
from typing import List, Mapping, Sequence

from src.ai.budgets import (
    format_information_budget_requirement,
    resolve_information_budget,
)
from src.ai.professional_risk import apply_professional_risk_guardrail
from src.ai.summary_generator import (
    compact_display_summary,
    display_summary_overflow_fallback,
)
from src.utils.financial_narrative import (
    contains_authoritative_financial_state,
    sanitize_authoritative_financial_clauses,
)

StoryItem = Mapping[str, object]
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_REMOVED_METRICS = ("精力", "情绪", "学识", "energy", "mood", "knowledge")
_LEGAL_ENDORSEMENTS = ("合规路径", "合法合规", "完全合法", "符合法律规定", "compliant path")
_INFLATED_DURATION = ("半年", "一年", "数年", "half a year", "one year", "several years")
_LIFE_SUMMARY_EVIDENCE_MAX_CHARS = 24_000
_LIFE_SUMMARY_OUTPUT_MAX_CHARS = resolve_information_budget("life", "zh").target_max


def _as_text(item: StoryItem, key: str) -> str:
    value = item.get(key, "")
    return value if isinstance(value, str) else ""


def _source_text(story_history: Sequence[StoryItem]) -> str:
    parts: List[str] = []
    for item in story_history:
        story = _as_text(item, "story_text")
        choice = _as_text(item, "choice_text")
        week = item.get("week")
        week_label = f"第{int(week) + 1}周" if isinstance(week, int) else "未标注周次"
        entry_parts = [week_label]
        if story:
            entry_parts.append(f"事件：{story}")
        if choice:
            entry_parts.append(f"选择：{choice}")
        if len(entry_parts) > 1:
            parts.append("；".join(entry_parts))
    source = "\n".join(parts)
    if len(source) <= _LIFE_SUMMARY_EVIDENCE_MAX_CHARS:
        return source

    entries = [
        item
        for item in story_history
        if _as_text(item, "story_text").strip() or _as_text(item, "choice_text").strip()
    ]
    if not entries:
        return ""

    max_entries = max(1, _LIFE_SUMMARY_EVIDENCE_MAX_CHARS // 520)
    selected_count = min(len(entries), max_entries)
    if selected_count == 1:
        selected_entries = [entries[0]]
    else:
        selected_entries = [
            entries[round(index * (len(entries) - 1) / (selected_count - 1))]
            for index in range(selected_count)
        ]

    per_entry_limit = max(
        1,
        (_LIFE_SUMMARY_EVIDENCE_MAX_CHARS - max(0, selected_count - 1))
        // selected_count,
    )
    compact_entries: List[str] = []
    for item in selected_entries:
        week = item.get("week")
        week_label = f"第{int(week) + 1}周" if isinstance(week, int) else "未标注周次"
        story = _as_text(item, "story_text").strip()
        choice = _as_text(item, "choice_text").strip()
        full_parts = [week_label]
        if story:
            full_parts.append(f"事件：{story}")
        if choice:
            full_parts.append(f"选择：{choice}")
        full_entry = "；".join(full_parts)
        if len(full_entry) <= per_entry_limit:
            compact_entries.append(full_entry)
            continue

        structured_parts = [week_label, f"事件：{week_label}完整事件正文保存在原始记录中。"]
        choice_part = f"选择：{choice}"
        if choice and len("；".join([*structured_parts, choice_part])) <= per_entry_limit:
            structured_parts.append(choice_part)
        elif choice:
            structured_parts.append(f"选择：{week_label}完整选择保存在原始记录中。")
        compact_entries.append("；".join(structured_parts))

    return "\n".join(compact_entries)


def _sanitize_fallback_evidence(text: str) -> str:
    """Remove exact or tracked money-state clauses before fallback quoting."""
    return sanitize_authoritative_financial_clauses(text) or "相关经济处境有所变化"


def _range_label(start_week: int, end_week: int) -> str:
    return f"第{start_week}周" if start_week == end_week else f"第{start_week}-{end_week}周"


def _summary_output_limit(story_history: Sequence[StoryItem]) -> int:
    """Keep a summary compact relative to the source while preserving short histories."""
    source_length = len(_source_text(story_history))
    return min(_LIFE_SUMMARY_OUTPUT_MAX_CHARS, max(500, source_length // 4))


def build_life_summary_prompt(
    story_history: Sequence[StoryItem], start_week: int, end_week: int
) -> str:
    """Build an evidence-only provider prompt for an inclusive week range."""
    label = _range_label(start_week, end_week)
    length_requirement = format_information_budget_requirement("life", "zh")
    return f"""请为{label}的人生故事生成一段总结。{length_requirement}

【事实与时间硬约束】
- 只使用下方故事证据和选择，不得补写未出现的人物身份、事件、数字、法律结论或资源状态。
- 时间范围只能写成“{label}”或等价的{end_week - start_week + 1}周，不得夸大为半年、数月或更长时期。
- 如果不同回合对身份、病情、招标、注册或其他事实存在冲突，必须明确保留为冲突或未决，不得自行合并成确定事实。
- 对“规避竞业”、借用亲属名义或类似行为，不得称为合规路径、合法方案或已经解决的法律风险。
- 不要提及精力、情绪、学识等游戏资源指标。
- 不要把财富、账户余额或存款写成可追踪资源，也不要给出精确余额或财富门槛；可以保留定性的收入、消费、贫富与经济压力叙事。

【故事证据】
{_source_text(story_history)}

请用第三人称叙述，只返回总结正文。"""


def build_grounded_fallback(
    story_history: Sequence[StoryItem], start_week: int, end_week: int
) -> str:
    """Create a deterministic summary from complete representative event sentences."""
    excerpts: List[tuple[str, str, str]] = []
    seen_stories: set[str] = set()
    for item in story_history:
        story = _sanitize_fallback_evidence(_as_text(item, "story_text"))
        if story and story not in seen_stories:
            seen_stories.add(story)
            choice = _sanitize_fallback_evidence(_as_text(item, "choice_text"))
            week = item.get("week")
            week_label = f"第{int(week) + 1}周" if isinstance(week, int) else "某一周"
            excerpt = story
            if choice:
                excerpt += f" 相应选择是“{choice}”。"
            excerpts.append((week_label, excerpt, choice))

    source = _source_text(story_history)
    caution = ""
    if any(marker in source for marker in ("规避竞业", "亲属名义", "母亲名义")):
        caution = " 相关做法存在争议与风险，不能据此认定法律或合规问题已经解决。"

    if len(excerpts) > 4:
        excerpts = [
            excerpts[round(index * (len(excerpts) - 1) / 3)]
            for index in range(4)
        ]

    prefix = f"{_range_label(start_week, end_week)}："
    body_limit = max(1, _summary_output_limit(story_history) - len(prefix) - len(caution))
    if excerpts:
        excerpt_limit = max(1, body_limit // len(excerpts))
        event_budget = replace(
            resolve_information_budget("life", "zh"),
            target_min=1,
            target_max=excerpt_limit,
            compression_threshold=excerpt_limit,
        )
        bounded_entries: List[str] = []
        for week_label, excerpt, choice in excerpts:
            bounded = compact_display_summary(excerpt, event_budget)
            if bounded == display_summary_overflow_fallback("zh"):
                choice_sentence = f"{week_label}的选择是“{choice}”。" if choice else ""
                bounded = (
                    choice_sentence
                    if choice_sentence and len(choice_sentence) <= excerpt_limit
                    else f"{week_label}的完整事件仍保存在记录中。"
                )
            bounded_entries.append(bounded)
        body = "".join(bounded_entries)
    else:
        body = "这段时间的故事记录仍在整理。"
    result = f"{prefix}{body}{caution}"
    if contains_authoritative_financial_state(result):
        return f"{prefix}相关经济处境有所变化。"
    return result


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
        or contains_authoritative_financial_state(summary)
        or any(claim.lower() in lowered for claim in _LEGAL_ENDORSEMENTS)
        or (span <= 8 and any(duration.lower() in lowered for duration in _INFLATED_DURATION))
        or _has_unsupported_number(summary, story_history, start_week, end_week)
    )
    if unsafe:
        return build_grounded_fallback(story_history, start_week, end_week)
    guarded = apply_professional_risk_guardrail(summary.strip(), language="zh")
    compacted = compact_display_summary(
        guarded, resolve_information_budget("life", "zh")
    )
    if compacted == display_summary_overflow_fallback("zh"):
        return build_grounded_fallback(story_history, start_week, end_week)
    if len(compacted) > _summary_output_limit(story_history):
        return build_grounded_fallback(story_history, start_week, end_week)
    return compacted
