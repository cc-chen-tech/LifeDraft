"""Regression contracts for the versioned world-projection repair procedure."""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.game.daily_generation_intent import resolve_daily_generation_intent
from src.services.daily_world_projection_repair import scan_game_state


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
    assert all(day["accepted"] is True for day in history)
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
    assert candidate.rebuild_day_indexes == [0, 1, 2, 3, 4]
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
    assert "latest_completed_repair_audit_id" in runbook
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
