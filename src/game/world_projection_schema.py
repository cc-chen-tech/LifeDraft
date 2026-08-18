"""Typed contracts for versioned daily world projection extraction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.game.world_projection_coverage import detect_world_change_signals

WORLD_PROJECTION_SCHEMA_VERSION = 1
WORLD_PROJECTION_PROMPT_VERSION = "daily-world-projection-v1"


class WorldPatch(BaseModel):
    """Narrative-derived changes in one accepted story branch."""

    model_config = ConfigDict(extra="forbid")

    fact_updates: list[dict[str, Any]] = Field(default_factory=list)
    foreshadowing_seeds: list[dict[str, Any]] = Field(default_factory=list)
    habit_updates: list[dict[str, Any]] = Field(default_factory=list)
    location_updates: list[dict[str, Any]] = Field(default_factory=list)
    career_updates: list[dict[str, Any]] = Field(default_factory=list)
    commitment_updates: list[dict[str, Any]] = Field(default_factory=list)
    causal_updates: list[dict[str, Any]] = Field(default_factory=list)

    def is_empty(self) -> bool:
        """Return whether this patch contains no derived world changes."""
        return not any(self.model_dump().values())


class WorldProjectionPayload(BaseModel):
    """One daily story patch plus the conditional patch for every option."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = WORLD_PROJECTION_SCHEMA_VERSION
    story_patch: WorldPatch
    option_patches: dict[int, WorldPatch]
    no_change: bool = False

    def is_empty(self) -> bool:
        """Return whether neither the story nor any option changes the world."""
        return self.story_patch.is_empty() and all(
            patch.is_empty() for patch in self.option_patches.values()
        )


class WorldProjectionExtractionError(RuntimeError):
    """A retryable extraction failure with a stable machine-readable code."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


def _normalize_projection_input(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize_projection_input(value.model_dump(mode="json"))
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_projection_input(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_projection_input(item) for item in value]
    if isinstance(value, str):
        return value.strip()
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def compute_projection_source_hash(story: str, options: Sequence[Any]) -> str:
    """Hash the canonical source shared by enqueue, worker, and repair paths."""
    source = {
        "schema_version": WORLD_PROJECTION_SCHEMA_VERSION,
        "prompt_version": WORLD_PROJECTION_PROMPT_VERSION,
        "story": _normalize_projection_input(story),
        "options": _normalize_projection_input(list(options)),
    }
    serialized = json.dumps(
        source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _parse_payload(value: Any) -> WorldProjectionPayload:
    try:
        return WorldProjectionPayload.model_validate(value)
    except ValidationError as exc:
        raise WorldProjectionExtractionError(
            f"Daily world projection did not match the schema: {exc}",
            code="invalid_schema",
        ) from exc


def _validate_raw_option_patch_keys(value: Any) -> None:
    """Reject ambiguous JSON keys before Pydantic can coerce them to integers."""
    if not isinstance(value, Mapping):
        return
    raw_option_patches = value.get("option_patches")
    if not isinstance(raw_option_patches, Mapping):
        return

    for raw_index in raw_option_patches:
        if (
            not isinstance(raw_index, str)
            or not raw_index.isascii()
            or not raw_index.isdecimal()
            or raw_index != str(int(raw_index))
        ):
            raise WorldProjectionExtractionError(
                "Daily world projection option indexes must be canonical non-negative JSON integers",
                code="invalid_schema",
            )


def _coerce_string_patch_records(value: Any, protagonist: str) -> Any:
    """Coerce bare-string patch records into minimal structured dicts.

    ``deepseek-v4-flash`` occasionally emits world-projection patch entries
    (e.g. ``fact_updates``) as plain strings — the update text only — instead of
    the structured objects the schema requires. Coerce those strings back into
    minimal dicts so the payload validates and the text is preserved with a
    best-effort subject, instead of failing schema validation outright.
    """
    if not isinstance(value, Mapping):
        return value

    subject = protagonist or "主角"
    coercions: dict[str, Any] = {
        "fact_updates": lambda text: {
            "action": "new",
            "subject": subject,
            "category": "situation",
            "fact": text,
        },
        "foreshadowing_seeds": lambda text: {
            "description": text,
            "seed_type": "mystery",
            "related_characters": [],
            "related_storylines": [],
        },
        "habit_updates": lambda text: {
            "action": "new",
            "character": subject,
            "habit": text,
            "category": "behavioral",
            "strength": "moderate",
        },
        "location_updates": lambda text: {
            "character": subject,
            "location": text,
        },
        "career_updates": lambda text: {
            "character": subject,
            "current_job": text,
        },
        "commitment_updates": lambda text: {
            "description": text,
            "parties": [],
        },
        "causal_updates": lambda text: {
            "cause": text,
            "expected_consequence": "结果未明",
        },
    }

    def coerce_patch(patch: Any) -> Any:
        if not isinstance(patch, Mapping):
            return patch
        coerced = dict(patch)
        for field, coerce in coercions.items():
            records = coerced.get(field)
            if isinstance(records, list):
                coerced[field] = [
                    coerce(item) if isinstance(item, str) else item for item in records
                ]
        return coerced

    result = dict(value)
    if "story_patch" in result:
        result["story_patch"] = coerce_patch(result["story_patch"])
    if isinstance(result.get("option_patches"), Mapping):
        result["option_patches"] = {
            key: coerce_patch(patch) for key, patch in result["option_patches"].items()
        }
    return result


def validate_projection_payload(
    value: Any,
    story: str,
    options: Sequence[Any],
    tracked_state: Any = None,
) -> WorldProjectionPayload:
    """Validate one extracted payload and reject suspicious all-empty output."""
    protagonist = ""
    if isinstance(tracked_state, Mapping):
        protagonist = str(tracked_state.get("player_name") or "").strip()
    value = _coerce_string_patch_records(value, protagonist)
    _validate_raw_option_patch_keys(value)
    payload = _parse_payload(value)
    expected_indexes = set(range(len(options)))
    extra_indexes = set(payload.option_patches) - expected_indexes
    if extra_indexes:
        raise WorldProjectionExtractionError(
            f"Daily world projection included unknown option indexes: {sorted(extra_indexes)}",
            code="invalid_schema",
        )

    for index in expected_indexes:
        payload.option_patches.setdefault(index, WorldPatch())

    if not payload.is_empty():
        payload.no_change = False
        return payload

    coverage = detect_world_change_signals(story, options, tracked_state)
    if coverage.requires_nonempty_patch:
        raise WorldProjectionExtractionError(
            "Daily world projection was empty despite detected world-change evidence: "
            + ", ".join(coverage.categories),
            code="suspicious_empty",
        )
    payload.no_change = True
    return payload
