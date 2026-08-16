"""Typed contracts for versioned daily world projection extraction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from src.game.world_projection_coverage import detect_world_change_signals

WORLD_PROJECTION_SCHEMA_VERSION = 1
WORLD_PROJECTION_PROMPT_VERSION = "daily-world-projection-v1"


class WorldPatch(BaseModel):
    """Narrative-derived changes in one accepted story branch."""

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


def validate_projection_payload(
    value: Any,
    story: str,
    options: Sequence[Any],
    tracked_state: Any = None,
) -> WorldProjectionPayload:
    """Validate one extracted payload and reject suspicious all-empty output."""
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
