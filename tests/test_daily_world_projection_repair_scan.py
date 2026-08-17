from copy import deepcopy

import pytest

from src.game.world_projection_schema import compute_projection_source_hash
from src.services.daily_world_projection_repair import (
    GameRepairCandidate,
    RepairReason,
    build_scan_report,
    initialized_projection_state,
    is_valid_projection_state,
    non_projection_state_digest,
    report_hash,
    scan_game_state,
)


def _empty_world_patch() -> dict[str, list[object]]:
    return {
        "fact_updates": [],
        "habit_updates": [],
        "location_updates": [],
        "career_updates": [],
        "commitment_updates": [],
        "causal_updates": [],
        "foreshadowing_seeds": [],
    }


def sun_wukong_failed_fixture() -> dict[str, object]:
    history = [
        {
            "day_index": day_index,
            "event_id": f"sanitized-day-{day_index}",
            "revision": 1,
            "event_description": (
                "孙悟空抵达东海，完成了与龙王同行的约定。"
                if day_index == 4
                else "孙悟空在东海继续调查。"
            ),
            "options": [{"text": "继续前进"}],
            "choice_option_index": 0,
            "postprocessing_status": "complete",
            "postprocessing": {"world": _empty_world_patch()},
        }
        for day_index in range(5)
    ]
    return {
        "timeline_version": 2,
        "timeline": {
            "version": 2,
            "day_index": 5,
            "current_date": "2026-08-17",
        },
        "day_history": history,
        "current_event_data": None,
        "resume_view": {
            "phase": "failed",
            "failure": {"code": "RETRY_EXHAUSTED", "retryable": True},
        },
        "world_model_data": {
            "character_locations": {"孙悟空": {"location": "花果山"}},
            "active_commitments": [
                {"description": "与龙王同行", "parties": ["孙悟空", "龙王"]}
            ],
        },
        "world_projection_state": {
            "version": 1,
            "applied_through_day_index": -1,
            "projected_through_day_index": -1,
            "pending_from_day_index": 0,
            "world": _empty_world_patch(),
        },
    }


def legitimate_no_change_fixture() -> dict[str, object]:
    return {
        "timeline_version": 2,
        "timeline": {
            "version": 2,
            "day_index": 1,
            "current_date": "2026-08-13",
        },
        "day_history": [
            {
                "day_index": 0,
                "event_id": "quiet-day",
                "revision": 1,
                "event_description": "孙悟空倚在石边看潮水起落，暂时没有作出决定。",
                "options": [{"text": "继续观察"}],
                "choice_option_index": 0,
                "postprocessing_status": "complete",
                "world_projection_status": "ready_no_change",
                "postprocessing": {"world": _empty_world_patch()},
            }
        ],
        "current_event_data": {"event_id": "next-day"},
        "world_model_data": {"character_locations": {"孙悟空": {"location": "花果山"}}},
        "world_projection_state": {
            "version": 1,
            "applied_through_day_index": 0,
            "projected_through_day_index": 0,
            "pending_from_day_index": None,
            "world": _empty_world_patch(),
        },
    }


def player_state_fixture() -> dict[str, object]:
    return {
        "timeline": {"day_index": 3, "current_date": "2026-08-15"},
        "relationships": {"李长庚": 42},
        "resources": {"energy": 80},
        "resume_view": {"phase": "failed", "error": "retry later"},
        "day_history": [{"day_index": 2, "event_description": "已接受故事"}],
        "world_model_data": {"character_locations": {"孙悟空": "花果山"}},
    }


def projected_state_fixture() -> dict[str, object]:
    return {
        "version": 1,
        "applied_through_day_index": 2,
        "projected_through_day_index": 2,
        "pending_from_day_index": None,
        "world": _empty_world_patch(),
    }


def test_sun_wukong_shape_is_detected_without_hardcoded_game_id() -> None:
    candidate = scan_game_state(156, sun_wukong_failed_fixture())

    assert candidate is not None
    assert {reason.code for reason in candidate.reasons} == {
        "suspicious_empty_world_projection",
        "world_watermark_behind_history",
        "missing_current_event_after_retryable_failure",
    }
    assert candidate.rebuild_day_indexes == [0, 1, 2, 3, 4]


def test_legitimate_no_change_save_is_not_detected() -> None:
    assert scan_game_state(200, legitimate_no_change_fixture()) is None


def test_retryable_generation_failure_does_not_select_a_healthy_projection() -> None:
    state = legitimate_no_change_fixture()
    state["current_event_data"] = None
    state["resume_view"] = {
        "phase": "failed",
        "failure": {"code": "RETRY_EXHAUSTED", "retryable": True},
    }

    assert scan_game_state(200, state) is None


def test_affected_legacy_save_without_projection_layer_rebuilds_full_history() -> None:
    """Initializing v1 at -1 requires every accepted source in oldest-first order."""

    state = sun_wukong_failed_fixture()
    state.pop("world_projection_state")
    state["day_history"][0]["postprocessing_status"] = "complete"
    state["day_history"][0]["postprocessing"] = {
        "world": {**_empty_world_patch(), "fact_updates": [{"fact": "已完成"}]}
    }

    candidate = scan_game_state(201, state)

    assert candidate is not None
    assert candidate.rebuild_day_indexes == [0, 1, 2, 3, 4]


def test_invalid_v1_layer_with_high_watermark_rebuilds_full_history() -> None:
    """A layer reset to -1 cannot trust a watermark from malformed v1 data."""

    state = sun_wukong_failed_fixture()
    state["world_projection_state"] = {
        "version": 1,
        "applied_through_day_index": 99,
        "projected_through_day_index": 99,
        "applied_sources": "malformed",
        "world": _empty_world_patch(),
    }

    candidate = scan_game_state(202, state)

    assert candidate is not None
    assert candidate.rebuild_day_indexes == [0, 1, 2, 3, 4]


def test_canonical_layer_validation_rejects_normalized_data_and_rebuilds_all() -> None:
    """A layer canonical loading would discard must reset and rebuild from day zero."""

    state = sun_wukong_failed_fixture()
    state["world_projection_state"] = {
        "version": 1,
        "applied_through_day_index": 0,
        "projected_through_day_index": 0,
        "pending_from_day_index": None,
        "oldest_pending_at": None,
        "applied_sources": [
            {
                "event_id": "broken-ledger",
                "revision": 1,
                "day_index": 0,
                "source_hash": "not-a-sha256",
                "option_index": 0,
            }
        ],
        "world": {},
    }

    candidate = scan_game_state(203, state)
    initialized, was_initialized = initialized_projection_state(state)

    assert is_valid_projection_state(state["world_projection_state"]) is False
    assert candidate is not None
    assert candidate.rebuild_day_indexes == [0, 1, 2, 3, 4]
    assert was_initialized is True
    assert initialized["applied_through_day_index"] == -1
    assert initialized["applied_sources"] == []


def test_canonical_layer_validation_preserves_legacy_baseline_without_sources() -> None:
    """A migrated baseline watermark does not require synthetic ledger entries."""

    layer = {
        "version": 1,
        "applied_through_day_index": 3,
        "projected_through_day_index": 3,
        "pending_from_day_index": None,
        "oldest_pending_at": None,
        "applied_sources": [],
        "world": _empty_world_patch(),
    }

    assert is_valid_projection_state(layer) is True


def test_repair_below_unproven_legacy_watermark_rebuilds_full_history() -> None:
    state = sun_wukong_failed_fixture()
    state["world_projection_state"] = {
        "version": 1,
        "applied_through_day_index": 4,
        "projected_through_day_index": 4,
        "pending_from_day_index": None,
        "oldest_pending_at": None,
        "applied_sources": [],
        "world": _empty_world_patch(),
    }

    candidate = scan_game_state(204, state)
    assert candidate is not None
    assert candidate.rebuild_day_indexes == [0, 1, 2, 3, 4]

    initialized, was_initialized = initialized_projection_state(state, candidate)
    assert was_initialized is True
    assert initialized["applied_through_day_index"] == -1
    assert initialized["applied_sources"] == []


def test_exact_source_ledger_preserves_valid_repair_baseline() -> None:
    state = sun_wukong_failed_fixture()
    state["world_projection_state"]["applied_through_day_index"] = 4
    state["world_projection_state"]["projected_through_day_index"] = 4
    state["world_projection_state"]["pending_from_day_index"] = None
    state["world_projection_state"]["oldest_pending_at"] = None
    state["world_projection_state"]["applied_sources"] = [
        {
            "event_id": record["event_id"],
            "revision": record["revision"],
            "day_index": record["day_index"],
            "source_hash": compute_projection_source_hash(
                record["event_description"], record["options"]
            ),
            "option_index": record["choice_option_index"],
        }
        for record in state["day_history"]
    ]

    candidate = scan_game_state(205, state)
    assert candidate is not None
    assert candidate.rebuild_day_indexes == [4]
    initialized, was_initialized = initialized_projection_state(state, candidate)
    assert was_initialized is False
    assert initialized == state["world_projection_state"]


def test_weekly_v1_state_is_never_selected_for_daily_repair() -> None:
    state = sun_wukong_failed_fixture()
    state.pop("timeline_version")
    state.pop("timeline")

    assert scan_game_state(156, state) is None


def test_canonical_layer_validation_rejects_non_sha256_applied_source() -> None:
    """A source entry canonical application cannot safely fence must be rejected."""

    layer = {
        "version": 1,
        "applied_through_day_index": 0,
        "projected_through_day_index": 0,
        "pending_from_day_index": None,
        "oldest_pending_at": None,
        "applied_sources": [
            {
                "event_id": "bad-hash-day-0",
                "revision": 1,
                "day_index": 0,
                "source_hash": "not-a-sha256",
                "option_index": 0,
            }
        ],
        "world": _empty_world_patch(),
    }

    assert is_valid_projection_state(layer) is False


def test_canonical_layer_validation_rejects_duplicate_ledger_day() -> None:
    """Two source identities cannot both own one applied day."""

    layer = {
        "version": 1,
        "applied_through_day_index": 0,
        "projected_through_day_index": 0,
        "pending_from_day_index": None,
        "oldest_pending_at": None,
        "applied_sources": [
            {
                "event_id": "first-day-zero",
                "revision": 1,
                "day_index": 0,
                "source_hash": "a" * 64,
                "option_index": 0,
            },
            {
                "event_id": "second-day-zero",
                "revision": 1,
                "day_index": 0,
                "source_hash": "b" * 64,
                "option_index": 0,
            },
        ],
        "world": _empty_world_patch(),
    }

    assert is_valid_projection_state(layer) is False


def test_digest_ignores_only_projection_state() -> None:
    before = player_state_fixture()
    after = deepcopy(before)
    after["world_projection_state"] = projected_state_fixture()

    assert non_projection_state_digest(before) == non_projection_state_digest(after)

    after["relationships"]["李长庚"] += 1  # type: ignore[index,operator]
    assert non_projection_state_digest(before) != non_projection_state_digest(after)


def test_report_is_sorted_and_hashed_deterministically() -> None:
    first = scan_game_state(156, sun_wukong_failed_fixture())
    second = scan_game_state(42, sun_wukong_failed_fixture())

    assert first is not None
    assert second is not None
    report = build_scan_report([second, first])

    assert [candidate.game_id for candidate in report.candidates] == [42, 156]
    assert report_hash(report) == report_hash(build_scan_report([first, second]))


def test_report_normalizes_candidate_day_indexes_before_hashing() -> None:
    report = build_scan_report(
        [
            GameRepairCandidate(
                game_id=9,
                reasons=(RepairReason("z_reason", (4, 1)),),
                rebuild_day_indexes=[4, 1, 1],
            )
        ]
    )

    assert report.candidates[0].reasons[0].day_indexes == (1, 4)
    assert report.candidates[0].rebuild_day_indexes == [1, 4]


def test_report_rejects_duplicate_game_ids_in_any_input_order() -> None:
    first = GameRepairCandidate(
        game_id=9,
        reasons=(RepairReason("first_reason", (1,)),),
        rebuild_day_indexes=[1],
    )
    second = GameRepairCandidate(
        game_id=9,
        reasons=(RepairReason("second_reason", (2,)),),
        rebuild_day_indexes=[2],
    )

    for candidates in ([first, second], [second, first]):
        with pytest.raises(ValueError, match="duplicate_game_id_in_scan_report"):
            build_scan_report(candidates)
