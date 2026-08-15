"""Local structural checks for the personalized first daily opening."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from config.prompts.story_prompts import resolve_protagonist_name


_ZH_CLICHES = ("命运的齿轮", "人生十字路口", "全新旅程")
_EN_CLICHES = ("wheels of fate", "crossroads of life", "a brand-new journey")
_ZH_CONFLICT_MARKERS = (
    "却",
    "但",
    "仍",
    "难",
    "未",
    "不",
    "眼前",
    "现实",
    "困",
    "压力",
    "矛盾",
)
_EN_CONFLICT_MARKERS = (
    "but",
    "yet",
    "still",
    "difficult",
    "cannot",
    "can't",
    "conflict",
    "pressure",
    "reality",
)
_ZH_SCENE_MARKERS = (
    "清晨",
    "夜",
    "门",
    "街",
    "屋",
    "室",
    "店",
    "站",
    "坐",
    "走",
    "来到",
    "推开",
    "拿起",
    "望向",
)
_EN_SCENE_MARKERS = (
    "morning",
    "night",
    "street",
    "room",
    "door",
    "shop",
    "stood",
    "sat",
    "walked",
    "entered",
    "opened",
    "looked",
)
_ZH_TITLE_ENDINGS = (
    "抉择",
    "选择",
    "开端",
    "序曲",
    "转折",
    "新页",
    "启程",
)
_ZH_NARRATIVE_PREDICATES = (
    "了",
    "着",
    "过",
    "却",
    "但",
    "仍",
    "正在",
    "面对",
    "坚持",
    "做出",
    "决定",
    "想要",
    "希望",
    "把",
    "将",
)
_EN_NARRATIVE_VERBS = {
    "began",
    "chose",
    "continued",
    "decided",
    "entered",
    "faced",
    "felt",
    "found",
    "heard",
    "looked",
    "made",
    "met",
    "opened",
    "said",
    "saw",
    "stood",
    "thought",
    "walked",
    "wanted",
    "was",
    "went",
}


def _life_vision(state: Dict[str, Any], settings: Optional[Dict[str, Any]]) -> str:
    from src.ai.prompt_sanitizer import sanitize_persisted_life_vision

    return sanitize_persisted_life_vision(
        str(state.get("life_vision") or (settings or {}).get("life_vision") or "")
    )


def _has_vision_anchor(first: str, vision: str, language: str) -> bool:
    if not vision.strip():
        return True
    if language == "zh":
        vision_han = "".join(re.findall(r"[\u3400-\u9fff]", vision))
        if len(vision_han) >= 2:
            anchors = {
                vision_han[index : index + 2] for index in range(len(vision_han) - 1)
            }
            return any(anchor in first for anchor in anchors)
        if vision_han:
            return vision_han in first
        ascii_anchors = {
            word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z0-9']*", vision)
        }
        if not ascii_anchors:
            return True
        lowered = first.casefold()
        return any(anchor in lowered for anchor in ascii_anchors)
    ignored = {"their", "with", "that", "from", "into", "life"}
    anchors = {
        word.casefold()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9']*", vision)
        if word.casefold() not in ignored
    }
    lowered = first.casefold()
    return any(anchor in lowered for anchor in anchors)


def validate_daily_first_opening(
    story_text: str,
    player_state: Dict[str, Any],
    character_settings: Optional[Dict[str, Any]],
    language: str,
) -> List[str]:
    """Return retry-worthy first-day opening violations for daily timeline v2."""
    timeline = player_state.get("timeline")
    if not isinstance(timeline, dict) or timeline.get("version") != 2:
        return []

    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", story_text) if part.strip()
    ]
    if not paragraphs:
        return ["daily_opening_missing_first_paragraph"]

    issues: List[str] = []
    first = paragraphs[0]
    numbered_or_markdown_heading = re.match(
        r"^(?:#{1,6}\s+|第[^\n]{0,12}(?:周|轮|回)|第[^\n]{0,12}(?:章|节|天|日|幕|篇)(?:[:：·\s])|公元\s*\d{1,4}\s*年)",
        first,
    )
    short_unpunctuated_heading = len(first) <= 24 and not re.search(
        r"[。！？.!?]", first
    )
    bracketed_heading = bool(
        re.match(
            r"^(?:【.+】|［.+］|\[.+\]|《.+》|（.+）|\(.+\)|「.+」|『.+』)[。！？.!?]?$",
            first,
        )
    )
    title_candidate = re.sub(r"[。！？.!?]+$", "", first).strip()
    short_title_phrase = (
        language == "zh"
        and len(title_candidate) <= 24
        and not re.search(r"[，、；：]", title_candidate)
        and not any(marker in title_candidate for marker in _ZH_NARRATIVE_PREDICATES)
        and title_candidate.endswith(_ZH_TITLE_ENDINGS)
    )
    english_words = re.findall(r"[A-Za-z][A-Za-z'-]*", title_candidate)
    english_title_phrase = (
        language == "en"
        and 2 <= len(english_words) <= 10
        and bool(re.fullmatch(r"[A-Za-z][A-Za-z' -]*", title_candidate))
        and all(word[0].isupper() for word in english_words)
        and not any(word.casefold() in _EN_NARRATIVE_VERBS for word in english_words)
        and not any(word.casefold().endswith(("ed", "ing")) for word in english_words)
    )
    if (
        numbered_or_markdown_heading
        or short_unpunctuated_heading
        or bracketed_heading
        or short_title_phrase
        or english_title_phrase
    ):
        issues.append("daily_story_heading_forbidden")

    if int(timeline.get("day_index") or 0) != 0:
        return issues

    protagonist = resolve_protagonist_name(player_state, character_settings, None)
    if protagonist and protagonist not in first:
        issues.append("daily_opening_missing_protagonist")

    terminators = re.findall(r"[。！？.!?]", first)
    if len(terminators) != 1 or not re.search(r"[。！？.!?][”’\"']?$", first):
        issues.append("daily_opening_not_single_sentence")

    clichés = _ZH_CLICHES if language == "zh" else _EN_CLICHES
    lowered = first.casefold()
    if any(cliché.casefold() in lowered for cliché in clichés):
        issues.append("daily_opening_cliche")

    vision = _life_vision(player_state, character_settings)
    if not _has_vision_anchor(first, vision, language):
        issues.append("daily_opening_missing_vision_anchor")

    conflict_markers = (
        _ZH_CONFLICT_MARKERS if language == "zh" else _EN_CONFLICT_MARKERS
    )
    if not any(marker.casefold() in lowered for marker in conflict_markers):
        issues.append("daily_opening_missing_core_conflict")

    if len(paragraphs) < 2:
        issues.append("daily_opening_missing_second_paragraph")
    else:
        second = paragraphs[1].casefold()
        scene_markers = _ZH_SCENE_MARKERS if language == "zh" else _EN_SCENE_MARKERS
        if not any(marker.casefold() in second for marker in scene_markers):
            issues.append("daily_opening_second_paragraph_not_scene")
    return issues
