"""Local structural checks for the personalized first daily opening."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from config.prompts.story_prompts import resolve_protagonist_name


_ZH_CLICHES = ("命运的齿轮", "人生十字路口", "全新旅程")
_EN_CLICHES = ("wheels of fate", "crossroads of life", "a brand-new journey")


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
    if re.match(
        r"^(?:#{1,6}\s*)?(?:第[^\n]{0,12}(?:周|轮|回)|公元\s*\d{1,4}\s*年)",
        first,
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

    if len(paragraphs) < 2:
        issues.append("daily_opening_missing_second_paragraph")
    return issues
