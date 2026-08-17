"""Contracts for typed daily world projection extraction payloads."""

from __future__ import annotations

import pytest

from src.game.world_projection_schema import (
    WorldProjectionExtractionError,
    compute_projection_source_hash,
    validate_projection_payload,
)


def _tracked_state() -> dict[str, object]:
    return {"character_locations": {"黑袍人": {"location": "花果山"}}}


def test_missing_option_patch_is_materialized_as_empty_typed_patch() -> None:
    payload = validate_projection_payload(
        {"schema_version": 1, "story_patch": {}, "option_patches": {"0": {}}},
        "黑袍人在花果山停留。",
        [{"text": "继续交谈"}, {"text": "静候消息"}],
        _tracked_state(),
    )

    assert payload.option_patches[0].model_dump() == {
        "fact_updates": [],
        "foreshadowing_seeds": [],
        "habit_updates": [],
        "location_updates": [],
        "career_updates": [],
        "commitment_updates": [],
        "causal_updates": [],
    }
    assert (
        payload.option_patches[1].model_dump() == payload.option_patches[0].model_dump()
    )
    assert payload.no_change is True


def test_extra_option_patch_is_rejected_instead_of_being_silently_stored() -> None:
    with pytest.raises(WorldProjectionExtractionError) as caught:
        validate_projection_payload(
            {
                "schema_version": 1,
                "story_patch": {},
                "option_patches": {"0": {}, "3": {}},
            },
            "两人在院中闲谈天气。",
            [{"text": "继续交谈"}],
            _tracked_state(),
        )

    assert caught.value.code == "invalid_schema"


def test_valid_no_change_is_marked_ready_no_change() -> None:
    payload = validate_projection_payload(
        {"schema_version": 1, "story_patch": {}, "option_patches": {}},
        "两人在院中闲谈天气。",
        [],
        _tracked_state(),
    )

    assert payload.no_change is True


def test_suspicious_empty_projection_is_retryable_error() -> None:
    with pytest.raises(WorldProjectionExtractionError) as caught:
        validate_projection_payload(
            {"schema_version": 1, "story_patch": {}, "option_patches": {}},
            "黑袍人抵达东海，完成了与孙悟空同行的约定。",
            [],
            _tracked_state(),
        )

    assert caught.value.code == "suspicious_empty"


def test_source_hash_is_stable_for_equivalent_option_mappings() -> None:
    first = compute_projection_source_hash(
        "黑袍人抵达东海。", [{"text": "继续", "effects": {"mood": 1}}]
    )
    second = compute_projection_source_hash(
        "黑袍人抵达东海。", [{"effects": {"mood": 1}, "text": "继续"}]
    )

    assert first == second


@pytest.mark.parametrize(
    "raw_payload",
    [
        {
            "schema_version": 1,
            "story_patch": {"unknown_change": []},
            "option_patches": {},
        },
        {
            "schema_version": 1,
            "story_patch": {},
            "option_patches": {"0": {"unknown_change": []}},
        },
        {
            "schema_version": 1,
            "story_patch": {},
            "option_patches": {},
            "unknown_top_level": True,
        },
    ],
)
def test_unknown_projection_fields_are_invalid_schema_not_no_change(
    raw_payload: dict[str, object],
) -> None:
    with pytest.raises(WorldProjectionExtractionError) as caught:
        validate_projection_payload(
            raw_payload,
            "两人在院中闲谈天气。",
            [{"text": "继续交谈"}],
            _tracked_state(),
        )

    assert caught.value.code == "invalid_schema"


@pytest.mark.parametrize(
    "raw_option_patches",
    [
        {"0": {}, "00": {}},
        {"-1": {}},
        {"1.0": {}},
        {" 0": {}},
    ],
)
def test_noncanonical_raw_option_patch_indexes_are_rejected_before_coercion(
    raw_option_patches: dict[str, object],
) -> None:
    with pytest.raises(WorldProjectionExtractionError) as caught:
        validate_projection_payload(
            {
                "schema_version": 1,
                "story_patch": {},
                "option_patches": raw_option_patches,
            },
            "两人在院中闲谈天气。",
            [{"text": "继续交谈"}],
            _tracked_state(),
        )

    assert caught.value.code == "invalid_schema"
