"""Display title helpers for generated story music tracks."""

from __future__ import annotations

from typing import Protocol


class MusicTitleBrief(Protocol):
    @property
    def mood(self) -> str:
        """Music mood from story analysis."""
        raise NotImplementedError

    @property
    def scene_type(self) -> str:
        """Scene type from story analysis."""
        raise NotImplementedError

    @property
    def era_or_environment(self) -> str:
        """Era or environment context from story analysis."""
        raise NotImplementedError


GENERIC_SCENE_TITLE_CUES = {
    "",
    "未知",
    "通用",
    "叙事",
    "场景",
    "日常过渡",
    "通用叙事",
    "通用叙事场景",
}

GENERIC_CONTEXT_TITLE_CUES = {
    "",
    "未知",
    "通用",
    "通用叙事",
    "通用叙事场景",
}


def generated_music_title(brief: MusicTitleBrief) -> str:
    """Build a user-facing title that avoids generic internal scene labels."""
    scene_type = _clean_title_part(brief.scene_type)
    if scene_type not in GENERIC_SCENE_TITLE_CUES:
        return f"AI MiniMax {scene_type}"

    parts: list[str] = []
    environment = _clean_title_part(brief.era_or_environment)
    mood = _clean_title_part(brief.mood)
    if environment not in GENERIC_CONTEXT_TITLE_CUES:
        parts.append(environment)
    if mood not in GENERIC_CONTEXT_TITLE_CUES and mood not in parts:
        parts.append(mood)

    return f"AI MiniMax {' '.join(parts) if parts else '故事配乐'}"


def _clean_title_part(value: object) -> str:
    return " ".join(str(value or "").strip().split())
