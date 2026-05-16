"""Text quality helpers for generated narrative."""

from __future__ import annotations

import re


def normalize_chinese_punctuation(text: str) -> str:
    """Normalize obvious English punctuation artifacts in Chinese prose."""
    replacements = {
        '："': "：“",
        ': "': "：“",
        ':"': "：“",
        '",': "”，",
        '."': "。”",
        '?"': "？”",
        '!"': "！”",
        '"': "”",
        ",": "，",
        "?": "？",
        "!": "！",
    }

    normalized = text
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)

    normalized = re.sub(r"([\u4e00-\u9fff])[:：]", r"\1：", normalized)
    normalized = re.sub(r"([，。！？；：])\s+([\u4e00-\u9fff“])", r"\1\2", normalized)
    return normalized


INTERNAL_STATE_PATTERNS = [
    re.compile(r"【[^】]*(状态|系统|数值|判定)[^】]*】"),
    re.compile(r"\b(energy|mood|knowledge|wealth)\s*[+-]?\s*\d+", re.IGNORECASE),
    re.compile(r"(系统|AI|模型|规则|状态栏|数值|判定)[:：][^\n。！？]*"),
]


def validate_narrative_quality(
    text: str, language: str = "zh", perspective: str = "second"
) -> list[str]:
    """Return deterministic quality issues that should never leak into narrative."""
    issues: list[str] = []
    if any(pattern.search(text) for pattern in INTERNAL_STATE_PATTERNS):
        issues.append("internal_state_leak")

    if language == "zh" and perspective == "second":
        has_second_person = bool(re.search(r"(^|[。！？\n])\s*你", text))
        has_first_person = bool(re.search(r"(^|[。！？\n])\s*我", text))
        if has_second_person and has_first_person:
            issues.append("mixed_perspective")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    short_paragraphs = [p for p in paragraphs if len(p) <= 12]
    if len(paragraphs) >= 5 and len(short_paragraphs) / len(paragraphs) > 0.6:
        issues.append("over_fragmented_paragraphs")

    return issues


def _remove_internal_state_leaks(text: str) -> str:
    cleaned = text
    for pattern in INTERNAL_STATE_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _merge_over_fragmented_lines(text: str) -> str:
    blocks = re.split(r"\n\s*\n", text)
    merged_blocks: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        current = ""
        paragraphs: list[str] = []
        for line in lines:
            if not current:
                current = line
            elif len(current) < 80 and len(line) <= 40:
                current += line if current.endswith(("“", "‘")) else line
            else:
                paragraphs.append(current)
                current = line
        if current:
            paragraphs.append(current)
        merged_blocks.append("\n\n".join(paragraphs))
    return "\n\n".join(merged_blocks)


def normalize_generated_story(
    text: str,
    language: str = "zh",
    perspective: str = "second",
) -> str:
    """Normalize generated prose before it is shown or persisted."""
    normalized = text.strip()
    if language == "zh":
        normalized = normalize_chinese_punctuation(normalized)
    normalized = _remove_internal_state_leaks(normalized)

    issues = validate_narrative_quality(normalized, language=language, perspective=perspective)
    if "over_fragmented_paragraphs" in issues:
        normalized = _merge_over_fragmented_lines(normalized)

    normalized = re.sub(r"[ \t]+\n", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
