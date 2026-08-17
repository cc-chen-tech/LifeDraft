"""Regression contracts for the versioned world-projection repair procedure."""

from __future__ import annotations

import json
import re
import subprocess
import sys
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
import pytest

pytestmark = [pytest.mark.unit]



REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "daily_world_projection"
    / "game156_sanitized.json"
)
RUNBOOK_PATH = (
    REPOSITORY_ROOT / "docs" / "runbooks" / "versioned-world-projection-repair.md"
)


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _phase_two_python_block(marker: str) -> str:
    """Extract one executable guard from the runbook's approved-apply phase."""

    _, phase_two = RUNBOOK_PATH.read_text(encoding="utf-8").split(
        "## Phase 2: approved apply", maxsplit=1
    )
    return next(
        block
        for block in re.findall(r"python - .*? <<'PY'\n(.*?)\nPY", phase_two, re.DOTALL)
        if marker in block
    )


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
        day["choice"] == day["options"][day["choice_option_index"]]["text"]
        for day in history
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
    phase_one, phase_two = runbook.split("## Phase 2: approved apply", maxsplit=1)

    assert runbook.index(dry_run) < runbook.index(apply)
    assert "## Phase 1: preflight and dry run" in phase_one
    assert apply not in phase_one
    assert "mktemp -d" in phase_one
    assert "WORLD_REPAIR_RUN_DIR" in phase_one
    assert "manifest.json" in phase_one
    assert "WORLD_REPAIR_APPROVED_REPORT_HASH:?" in phase_two
    assert "approved report hash does not match manifest" in phase_two
    assert "apply.stdout.json" in phase_two
    assert "apply.stderr.log" in phase_two
    assert "apply_exit_code" in phase_two
    assert "manifest apply evidence already exists" in phase_two
    assert "interrupted Phase 2 evidence requires a new repair run" in phase_two
    for evidence_name in (
        "apply.stdout.json.tmp",
        "apply.stdout.json",
        "apply.stderr.log.tmp",
        "apply.stderr.log",
        "status-after.json",
        "status-after.stderr.log",
    ):
        assert evidence_name in phase_two
    assert phase_two.index('if manifest.get("apply") is not None') < phase_two.index(
        apply
    )
    assert phase_two.index("if any((run_dir / name).exists()") < phase_two.index(apply)
    assert '--expected-report-hash "$WORLD_REPAIR_REPORT_HASH"' in runbook
    assert "verify_state_backup" in runbook
    assert "WORLD_PROJECTION_REPAIR_BACKUP_DIR" in runbook
    assert "set -euo pipefail" in runbook
    assert "WORLD_REPAIR_EVIDENCE_DIR" in runbook
    assert "WORLD_REPAIR_RUN_DIR" in runbook
    assert "apply.stdout.json" in runbook
    assert "apply.stderr.log" in runbook
    assert "WORLD_REPAIR_AUDIT_IDS" in runbook
    assert "WORLD_REPAIR_AUDIT_ID:?" in runbook
    assert (
        '--restore-audit-id "$WORLD_REPAIR_AUDIT_ID" --expected-report-hash' in runbook
    )
    assert "audit.report_hash != report_hash" in runbook
    assert '"failed_invariant", "failed_fenced", "timed_out"' in runbook
    assert "newer repair audit exists for this game" in runbook
    assert "approved_report_hash" in runbook
    assert "observed_report_hash" in runbook
    assert "dry-run candidates do not match report hash" in runbook
    assert 'exit "$apply_exit_code"' in phase_two
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


def test_phase_two_rejects_tampered_dry_run_candidates_despite_embedded_hash(
    tmp_path: Path,
) -> None:
    """The actual Phase 2 guard must hash candidates, not trust their field."""

    dry_run = {
        "report_hash": "0" * 64,
        "candidates": [{"game_id": 1, "rebuild_day_indexes": [0]}],
    }
    run_dir = tmp_path / "repair-run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"report_hash": dry_run["report_hash"], "apply": None}),
        encoding="utf-8",
    )
    (run_dir / "dry-run.json").write_text(json.dumps(dry_run), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _phase_two_python_block("dry_run_hash = dry_run.get"),
            str(run_dir),
            dry_run["report_hash"],
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "candidates do not match report hash" in result.stderr


def test_phase_two_records_report_changed_without_replacing_cli_exit_code(
    tmp_path: Path,
) -> None:
    """A stale approved hash must persist observed evidence then retain exit 2."""

    approved_hash = "a" * 64
    observed_hash = "b" * 64
    run_dir = tmp_path / "repair-run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps({"report_hash": approved_hash, "apply": None}), encoding="utf-8"
    )
    (run_dir / "apply.stdout.json").write_text(
        json.dumps(
            {
                "report_hash": observed_hash,
                "audit_ids": [],
                "status": "report_changed",
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _phase_two_python_block("apply_exit_code = int"),
            str(run_dir),
            approved_hash,
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["apply"] == {
        "approved_report_hash": approved_hash,
        "audit_ids": [],
        "exit_code": 2,
        "observed_report_hash": observed_hash,
        "status": "report_changed",
    }
