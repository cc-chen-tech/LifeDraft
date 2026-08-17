"""Regression contracts for the versioned world-projection repair procedure."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.game.daily_generation_intent import resolve_daily_generation_intent
from src.game.world_projection_schema import compute_projection_source_hash
from src.services.daily_world_projection_repair import (
    MISSING_EVENT_RETRYABLE_FAILURE,
    SUSPICIOUS_EMPTY,
    WATERMARK_BEHIND,
    rebuild_identities,
    rebuild_identities_match_history,
    scan_game_state,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "daily_world_projection" / "game156_sanitized.json"
)
RUNBOOK_PATH = REPOSITORY_ROOT / "docs" / "runbooks" / "versioned-world-projection-repair.md"


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_game156_fixture_matches_repair_and_generation_contracts() -> None:
    """The sanitized incident shape stays selectable by general repair rules."""

    state = _load_fixture()
    history = state["day_history"]

    candidate = scan_game_state(156, state)
    resolved = resolve_daily_generation_intent("replace_current", None)

    assert state["timeline_version"] == 2
    assert state["current_event_data"] is None
    assert state["resume_view"] == {
        "phase": "failed",
        "failure": {"code": "RETRY_EXHAUSTED", "retryable": True},
    }
    assert isinstance(history, list) and len(history) == 5
    assert all("accepted" not in day for day in history)
    assert all(
        {
            "event_id",
            "revision",
            "day_index",
            "story_date",
            "event_description",
            "options",
            "choice_option_index",
            "choice",
        }.issubset(day)
        for day in history
    )
    assert all(2 <= len(day["options"]) <= 4 for day in history)
    assert all(
        isinstance(option["text"], str)
        and option["text"].strip()
        and isinstance(option["effects"], dict)
        for day in history
        for option in day["options"]
    )
    assert all(
        day["choice"] == day["options"][day["choice_option_index"]]["text"] for day in history
    )
    assert all(
        day["postprocessing"]["world"]
        == {
            "fact_updates": [],
            "habit_updates": [],
            "location_updates": [],
            "career_updates": [],
            "commitment_updates": [],
            "causal_updates": [],
            "foreshadowing_seeds": [],
        }
        for day in history
    )
    assert "抵达" in history[-1]["event_description"]
    assert "完成" in history[-1]["event_description"]
    assert "约定" in history[-1]["event_description"]
    assert candidate is not None
    assert candidate.game_id == 156
    assert {reason.code for reason in candidate.reasons} == {
        SUSPICIOUS_EMPTY,
        WATERMARK_BEHIND,
        MISSING_EVENT_RETRYABLE_FAILURE,
    }
    assert candidate.rebuild_day_indexes == [0, 1, 2, 3, 4]
    identities = rebuild_identities(candidate, state)
    assert len(identities) == 5
    assert len({identity.projection_key for identity in identities}) == 5
    assert len({identity.source_hash for identity in identities}) == 5
    assert rebuild_identities_match_history(identities, state) is True
    for identity, record in zip(identities, history):
        assert identity.event_id == record["event_id"]
        assert identity.revision == record["revision"]
        assert identity.day_index == record["day_index"]
        assert identity.selected_option_index == record["choice_option_index"]
        assert identity.source_hash == compute_projection_source_hash(
            record["event_description"], record["options"]
        )
    assert resolved.resolved_mode == "generate_missing"


def test_repair_runbook_requires_a_hashed_dry_run_and_safe_backup_handling() -> None:
    """The operator procedure must keep the read-only handshake and restore fence."""

    runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
    dry_run = "python scripts/repair_daily_world_projections.py --dry-run"
    apply = "python scripts/repair_daily_world_projections.py --apply"

    assert runbook.index(dry_run) < runbook.index(apply)
    assert '--expected-report-hash "$WORLD_REPAIR_REPORT_HASH"' in runbook
    assert "verify_state_backup" in runbook
    assert "WORLD_PROJECTION_REPAIR_BACKUP_DIR" in runbook
    assert "set -euo pipefail" in runbook
    assert "WORLD_REPAIR_EVIDENCE_DIR" in runbook
    assert 'tee "$WORLD_REPAIR_APPLY_OUTPUT"' in runbook
    assert "WORLD_REPAIR_AUDIT_IDS" in runbook
    assert "WORLD_REPAIR_AUDIT_ID:?" in runbook
    assert "audit.report_hash != report_hash" in runbook
    assert 'audit.status != "complete"' in runbook
    assert "audit_id > max(audit_ids)" in runbook
    assert "latest_completed_repair_audit_id" not in runbook
    assert "newer player activity" in runbook
    assert re.search(r"must not\s+overwrite it automatically", runbook)
    assert "failed_invariant" in runbook
    assert "failed_fenced" in runbook
    assert "timed_out" in runbook
    assert "exit 0" in runbook
    assert "generate_missing" in runbook
    assert "SELECT" in runbook
    assert "SSH" not in runbook
    assert "password" not in runbook.lower()
    assert "credential" not in runbook.lower()
    assert "sshpass" not in runbook.lower()
    assert not re.search(r"--apply[^\n]*--game-id\s+156\b", runbook)
    assert not re.search(r"--game-id\s+156\b[^\n]*--apply", runbook)
