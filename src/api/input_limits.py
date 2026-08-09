"""Shared limits for new user-controlled API writes.

Text lengths are Unicode code-point counts. Structured character settings use
their compact UTF-8 JSON representation so nested data has one deterministic
technical boundary.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Dict

from pydantic import AfterValidator, Field
from pydantic_core import PydanticCustomError

NAME_MAX_CHARS = 50
LIFE_VISION_MAX_CHARS = 500
FEEDBACK_MAX_CHARS = 500
CUSTOM_ACTION_MAX_CHARS = 500
STORY_DIALOGUE_MAX_CHARS = 2_000
STORY_REWRITE_INSTRUCTION_MAX_CHARS = 2_000
REPLACEMENT_SEGMENT_MAX_CHARS = 12_000
FULL_STORY_MAX_CHARS = 32_000
VOICE_TEXT_MAX_CHARS = 32_000
CHARACTER_SETTINGS_MAX_BYTES = 256 * 1024

PUBLIC_INPUT_LIMITS = {
    "name": NAME_MAX_CHARS,
    "lifeVision": LIFE_VISION_MAX_CHARS,
    "feedback": FEEDBACK_MAX_CHARS,
    "customAction": CUSTOM_ACTION_MAX_CHARS,
    "storyDialogue": STORY_DIALOGUE_MAX_CHARS,
    "rewriteInstruction": STORY_REWRITE_INSTRUCTION_MAX_CHARS,
    "replacementSegment": REPLACEMENT_SEGMENT_MAX_CHARS,
    "fullStory": FULL_STORY_MAX_CHARS,
    "voiceText": VOICE_TEXT_MAX_CHARS,
    "characterSettingsBytes": CHARACTER_SETTINGS_MAX_BYTES,
}


def compact_json_size_bytes(value: Any) -> int:
    """Return the deterministic compact UTF-8 JSON size for a request value."""

    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def validate_character_settings_size(value: Dict[str, Any]) -> Dict[str, Any]:
    """Reject, without mutating, oversized structured character settings."""

    actual_length = compact_json_size_bytes(value)
    if actual_length > CHARACTER_SETTINGS_MAX_BYTES:
        raise PydanticCustomError(
            "json_too_large",
            "JSON input exceeds {limit} bytes",
            {
                "limit": CHARACTER_SETTINGS_MAX_BYTES,
                "actual_length": actual_length,
                "unit": "bytes",
            },
        )
    return value


CharacterSettingsPayload = Annotated[
    Dict[str, Any],
    AfterValidator(validate_character_settings_size),
    Field(json_schema_extra={"x-maxBytes": CHARACTER_SETTINGS_MAX_BYTES}),
]
