# PR 3: World Projection Repair and Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect only affected daily saves, back them up, rebuild versioned hidden world projections from accepted story/choice history, prove visible state is unchanged, and expose production health for projection lag and suspicious empty extraction.

**Architecture:** A pure scanner produces a deterministic report and report hash. An apply command requires that hash, writes a full backup and audit row, enqueues oldest-first projection jobs, and optionally waits for contiguous hidden-state materialization. Health aggregation reads the projection/audit tables and emits structured logs plus thresholded Sentry warnings; it does not add a player-facing diagnostics surface.

**Tech Stack:** Python 3, SQLAlchemy, argparse, JSON/SHA-256, pytest, existing Story2 database/session services, Sentry SDK already configured by the API.

**Spec:** `docs/superpowers/specs/2026-08-16-versioned-async-world-projection-design.md`

## Global Constraints

- PR 1 and PR 2 must be deployed and verified before any production repair apply.
- Dry-run is the default and performs no database or filesystem write.
- Apply repairs only games included in the exact dry-run report hash supplied by the operator.
- A complete latest game-state backup is written and fsynced before projection state or repair audit mutation.
- Repair may modify only `world_projection_state` and projection/audit tables; all other saved player-state fields remain byte-equivalent after normalized JSON serialization.
- Game ID 156 is expected to match but is never hard-coded.
- Repair and observability do not expose internal projection failures to players.

---

### Task 1: Build a pure affected-save scanner and invariant digest

**Files:**
- Create: `src/services/daily_world_projection_repair.py`
- Test: `tests/test_daily_world_projection_repair_scan.py`

**Interfaces:**
- Produces: `RepairReason`, `GameRepairCandidate`, `RepairScanReport`, `scan_game_state(game_id, state)`, `build_scan_report(rows)`, `report_hash(report)`, and `non_projection_state_digest(state)`.

- [ ] **Step 1: Write failing scanner tests from the production incident shape**

```python
def test_sun_wukong_shape_is_detected_without_hardcoded_game_id() -> None:
    candidate = scan_game_state(156, sun_wukong_failed_fixture())
    assert {reason.code for reason in candidate.reasons} == {
        "suspicious_empty_world_projection",
        "world_watermark_behind_history",
        "missing_current_event_after_retryable_failure",
    }
    assert candidate.rebuild_day_indexes == [0, 1, 2, 3, 4]


def test_legitimate_no_change_save_is_not_detected() -> None:
    assert scan_game_state(200, legitimate_no_change_fixture()) is None


def test_digest_ignores_only_projection_state() -> None:
    before = player_state_fixture()
    after = deepcopy(before)
    after["world_projection_state"] = projected_state_fixture()
    assert non_projection_state_digest(before) == non_projection_state_digest(after)
    after["relationships"]["李长庚"] += 1
    assert non_projection_state_digest(before) != non_projection_state_digest(after)
```

- [ ] **Step 2: Run scanner tests and verify the missing module failure**

Run: `python -m pytest tests/test_daily_world_projection_repair_scan.py -q`

Expected: missing repair module.

- [ ] **Step 3: Implement deterministic detection**

Use these reason codes:

```python
SUSPICIOUS_EMPTY = "suspicious_empty_world_projection"
POSTPROCESSING_STUCK = "postprocessing_pending_or_failed"
WATERMARK_BEHIND = "world_watermark_behind_history"
MISSING_EVENT_RETRYABLE_FAILURE = "missing_current_event_after_retryable_failure"
```

For every day-history row, validate its existing projection output with PR 2's coverage detector. Treat `ready_no_change` or an all-empty result with no detected change signal as legitimate. Build the report in ascending game ID and day index order so identical input always produces the same SHA-256 report hash.

- [ ] **Step 4: Implement the non-projection invariant digest**

Normalize `state` by deep-copying it and removing only `world_projection_state`. Serialize with sorted keys, stable UTF-8, and compact separators, then hash with SHA-256. Do not exclude `resume_view`, dates, resources, relationships, stories, options, choices, or legacy world fields.

- [ ] **Step 5: Run scanner tests**

Run: `python -m pytest tests/test_daily_world_projection_repair_scan.py tests/test_world_projection_coverage.py -q`

Expected: all pass.

- [ ] **Step 6: Commit the scanner**

```bash
git add src/services/daily_world_projection_repair.py tests/test_daily_world_projection_repair_scan.py
git commit -m "feat: detect saves needing world projection repair"
```

### Task 2: Persist repair audit and write recoverable backups

**Files:**
- Modify: `src/database/models.py`
- Create: `src/services/daily_world_projection_backup.py`
- Test: `tests/test_daily_world_projection_backup.py`
- Test: `tests/test_daily_world_projection_repair_audit.py`

**Interfaces:**
- Produces: `DailyWorldProjectionRepairAudit`, `write_state_backup(...)`, `verify_state_backup(...)`, and `restore_state_backup(...)`.

- [ ] **Step 1: Write failing backup/audit tests**

```python
def test_backup_is_fsynced_and_checksum_verified(tmp_path) -> None:
    backup = write_state_backup(tmp_path, game_id=156, state_id=9001, state_json=fixture())
    assert backup.path.exists()
    assert verify_state_backup(backup.path, backup.sha256) is True


def test_corrupt_backup_is_rejected(tmp_path) -> None:
    backup = write_state_backup(tmp_path, game_id=156, state_id=9001, state_json=fixture())
    backup.path.write_text("corrupt", encoding="utf-8")
    with pytest.raises(BackupChecksumMismatch):
        restore_state_backup(backup.path, backup.sha256)


def test_audit_records_report_and_visible_digest(db_session) -> None:
    audit = create_audit(db_session, report_hash="abc", visible_digest="def")
    assert audit.status == "backed_up"
```

- [ ] **Step 2: Run tests and verify missing model/service failures**

Run: `python -m pytest tests/test_daily_world_projection_backup.py tests/test_daily_world_projection_repair_audit.py -q`

Expected: missing audit table and backup APIs.

- [ ] **Step 3: Add the repair audit model**

```python
class DailyWorldProjectionRepairAudit(Base):
    __tablename__ = "daily_world_projection_repair_audits"
    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    state_id = Column(Integer, nullable=False)
    report_hash = Column(String(64), nullable=False, index=True)
    backup_path = Column(String(700), nullable=False)
    backup_sha256 = Column(String(64), nullable=False)
    non_projection_digest_before = Column(String(64), nullable=False)
    non_projection_digest_after = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, index=True)
    detail_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
```

- [ ] **Step 4: Implement atomic backup writes**

Default root is `data/repair-backups/world-projection`, overridable by `WORLD_PROJECTION_REPAIR_BACKUP_DIR`. Write JSON to a same-directory temporary file, flush and `os.fsync`, `os.replace` it to `{timestamp}-game-{game_id}-state-{state_id}.json`, then fsync the directory. The file contains metadata, complete `state_json`, and its SHA-256.

Restore verifies checksum before returning state and never writes to the database itself.

- [ ] **Step 5: Run backup/audit tests**

Run: `python -m pytest tests/test_daily_world_projection_backup.py tests/test_daily_world_projection_repair_audit.py tests/test_database.py -q`

Expected: all pass.

- [ ] **Step 6: Commit backup and audit support**

```bash
git add src/database/models.py src/services/daily_world_projection_backup.py tests/test_daily_world_projection_backup.py tests/test_daily_world_projection_repair_audit.py
git commit -m "feat: back up and audit projection repairs"
```

### Task 3: Add dry-run/apply CLI and oldest-first rebuild orchestration

**Files:**
- Modify: `src/services/daily_world_projection_repair.py`
- Create: `scripts/repair_daily_world_projections.py`
- Test: `tests/test_repair_daily_world_projections_cli.py`
- Test: `tests/test_daily_world_projection_rebuild.py`

**Interfaces:**
- Produces CLI modes `--dry-run`, `--apply --expected-report-hash HASH`, `--restore-audit-id ID`, optional `--game-id`, optional `--backup-dir`, and optional `--wait --timeout-seconds`.
- Produces `enqueue_rebuild(candidate, repo, state)` and `verify_repair_invariants(...)`.

- [ ] **Step 1: Write failing CLI safety tests**

```python
def test_cli_defaults_to_read_only_dry_run(cli, db) -> None:
    before = db.snapshot()
    result = cli.run([])
    assert result.exit_code == 0
    assert "report_hash" in result.stdout
    assert db.snapshot() == before


def test_apply_requires_exact_report_hash(cli) -> None:
    result = cli.run(["--apply", "--expected-report-hash", "wrong"])
    assert result.exit_code == 2
    assert "dry-run report changed" in result.stderr


def test_apply_repairs_only_reported_games(cli, db, tmp_path) -> None:
    report = cli.scan()
    result = cli.run([
        "--apply", "--expected-report-hash", report.hash,
        "--backup-dir", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert db.projection_game_ids() == set(report.game_ids)


def test_restore_refuses_when_visible_state_changed(cli, completed_audit, db) -> None:
    db.mutate_relationship(completed_audit.game_id, "李长庚", delta=1)
    result = cli.run(["--restore-audit-id", str(completed_audit.audit_id)])
    assert result.exit_code == 3
    assert "non-projection state changed" in result.stderr
```

- [ ] **Step 2: Run CLI/rebuild tests and verify failures**

Run: `python -m pytest tests/test_repair_daily_world_projections_cli.py tests/test_daily_world_projection_rebuild.py -q`

Expected: CLI and rebuild APIs are missing.

- [ ] **Step 3: Implement dry-run and report-hash enforcement**

The CLI loads only latest game states, applies optional `--game-id`, prints stable JSON containing game IDs, reasons, rebuild days, state IDs, non-projection digests, and the report hash. `--apply` rescans inside the same process and requires an exact hash match before the first write.

- [ ] **Step 4: Implement backup-first repair enqueue**

For each candidate in ascending game ID order:

1. write and verify full backup;
2. create `backed_up` audit row;
3. retain valid existing v1 applied state, otherwise initialize `world_projection_state` defaults;
4. ensure one projection row for every accepted day-history `(event_id, revision)` in ascending day order;
5. record each repaired day identity only in projection rows and audit metadata; do not mutate legacy `day_history` records;
6. wake the PR 2 projection service;
7. set audit status to `queued`.

Do not clear `resume_view`, change `current_event_data`, or mutate legacy world fields.

- [ ] **Step 5: Implement wait and invariant verification**

With `--wait`, poll until contiguous projections are applied, a terminal timeout occurs, or any job is fenced/superseded. Re-read latest state and require:

```python
non_projection_state_digest(after) == audit.non_projection_digest_before
```

Set audit to `complete` only when watermarks cover all rebuild days and the digest matches. On mismatch set `failed_invariant`, stop that game, and print the verified restore command; do not auto-restore over potentially newer player activity.

`--restore-audit-id` verifies the backup checksum and requires the current non-projection digest to equal the audit's before digest. It restores only `world_projection_state` from the backup into a new state snapshot, marks the audit `restored`, and leaves every visible/current field from the current state untouched. If the digest differs, it exits 3 without writing.

- [ ] **Step 6: Run CLI/rebuild tests**

Run: `python -m pytest tests/test_repair_daily_world_projections_cli.py tests/test_daily_world_projection_rebuild.py tests/test_daily_world_projection_repair_scan.py -q`

Expected: dry-run is write-free, hash mismatch blocks apply, backups precede writes, and visible-state digest is unchanged.

- [ ] **Step 7: Commit the repair CLI**

```bash
git add src/services/daily_world_projection_repair.py scripts/repair_daily_world_projections.py tests/test_repair_daily_world_projections_cli.py tests/test_daily_world_projection_rebuild.py
git commit -m "feat: rebuild affected world projections safely"
```

### Task 4: Add projection health summaries and thresholded alerts

**Files:**
- Create: `src/services/daily_world_projection_observability.py`
- Modify: `src/services/daily_world_projection.py`
- Create: `scripts/world_projection_status.py`
- Test: `tests/test_daily_world_projection_observability.py`

**Interfaces:**
- Produces: `ProjectionHealthSnapshot`, `summarize_projection_health(db, now)`, `emit_projection_health(snapshot)`, and a read-only status CLI.

- [ ] **Step 1: Write failing health aggregation tests**

```python
def test_health_snapshot_reports_backlog_and_empty_rates(db, now) -> None:
    seed_health_rows(db, pending_age_minutes=12, attempts=40, suspicious_empty=2)
    health = summarize_projection_health(db, now)
    assert health.oldest_pending_seconds == 720
    assert health.suspicious_empty_rate == pytest.approx(0.05)


def test_alert_requires_minimum_sample_for_empty_rate(db, now, sentry) -> None:
    seed_health_rows(db, attempts=3, suspicious_empty=1)
    emit_projection_health(summarize_projection_health(db, now), sentry=sentry)
    sentry.capture_message.assert_not_called()
```

- [ ] **Step 2: Run health tests and verify missing module failure**

Run: `python -m pytest tests/test_daily_world_projection_observability.py -q`

Expected: missing observability module.

- [ ] **Step 3: Implement read-only aggregation and structured logs**

Snapshot fields include status counts, oldest pending age, attempts in the last hour, suspicious-empty count/rate, ready-no-change count, fenced late writes, superseded rows, incomplete repair audits, and `latest_completed_repair_audit_id`. Emit one structured log every 60 seconds from the existing projection service loop.

- [ ] **Step 4: Add thresholded Sentry warnings**

Capture a warning with game IDs redacted from the message and attached as structured context when:

- oldest pending exceeds 10 minutes;
- suspicious-empty rate exceeds 2% with at least 20 extraction attempts in one hour;
- a repair audit reaches `failed_invariant`;
- any superseded/expired worker late write is rejected more than five times in one hour.

Rate-limit each alert key to once per 15 minutes per process.

- [ ] **Step 5: Implement the read-only status CLI**

`python scripts/world_projection_status.py --json` prints the same snapshot and exits nonzero only for query/configuration failure, not for an unhealthy snapshot. It never claims jobs or updates audit rows.

- [ ] **Step 6: Run observability tests**

Run: `python -m pytest tests/test_daily_world_projection_observability.py -q`

Expected: aggregation, minimum sample, thresholds, and rate limiting pass.

- [ ] **Step 7: Commit observability**

```bash
git add src/services/daily_world_projection_observability.py src/services/daily_world_projection.py scripts/world_projection_status.py tests/test_daily_world_projection_observability.py
git commit -m "feat: observe world projection health"
```

### Task 5: Document and test the production repair runbook

**Files:**
- Create: `docs/runbooks/versioned-world-projection-repair.md`
- Create: `tests/fixtures/daily_world_projection/game156_sanitized.json`
- Test: `tests/test_world_projection_repair_runbook.py`

**Interfaces:**
- Produces: an operator procedure that never embeds credentials and a sanitized regression fixture matching the incident state shape.

- [ ] **Step 1: Add the sanitized fixture and failing fixture-contract test**

The fixture contains: daily timeline v2, five accepted days, no current event, retryable exhausted resume view, a latest accepted story resolving a journey/commitment, and suspicious all-empty world extraction. Replace user/account identifiers and prose not needed for the regression.

```python
def test_game156_fixture_matches_repair_and_generation_contracts() -> None:
    state = load_fixture("game156_sanitized.json")
    candidate = scan_game_state(156, state)
    assert candidate is not None
    resolved = resolve_daily_generation_intent("replace_current", None)
    assert resolved.resolved_mode == "generate_missing"
```

- [ ] **Step 2: Write the runbook with exact safe commands**

Document this sequence without passwords:

```bash
python scripts/world_projection_status.py --json
python scripts/repair_daily_world_projections.py --dry-run > /tmp/world-projection-dry-run.json
WORLD_REPAIR_REPORT_HASH=$(python -c 'import json; print(json.load(open("/tmp/world-projection-dry-run.json", encoding="utf-8"))["report_hash"])')
python scripts/repair_daily_world_projections.py --apply --expected-report-hash "$WORLD_REPAIR_REPORT_HASH" --wait --timeout-seconds 1800
python scripts/world_projection_status.py --json
```

Include backup location, audit query, checksum verification, restore preparation, feature-flag rollback, and the requirement to confirm deployed revision and health before apply. State explicitly that restore requires stopping if newer player activity changed the latest state; operators must not overwrite it automatically.

The restore command is:

```bash
WORLD_REPAIR_AUDIT_ID=$(python scripts/world_projection_status.py --json | python -c 'import json,sys; print(json.load(sys.stdin)["latest_completed_repair_audit_id"])')
python scripts/repair_daily_world_projections.py --restore-audit-id "$WORLD_REPAIR_AUDIT_ID"
```

- [ ] **Step 3: Add a documentation contract test**

Assert the runbook contains dry-run before apply, expected report hash, backup verification, no literal SSH password, and no hard-coded `--game-id 156` apply command.

- [ ] **Step 4: Run fixture/runbook tests**

Run: `python -m pytest tests/test_world_projection_repair_runbook.py tests/test_daily_world_projection_repair_scan.py -q`

Expected: fixture is detected by rules and runbook safety contract passes.

- [ ] **Step 5: Commit the runbook and fixture**

```bash
git add docs/runbooks/versioned-world-projection-repair.md tests/fixtures/daily_world_projection/game156_sanitized.json tests/test_world_projection_repair_runbook.py
git commit -m "docs: add world projection repair runbook"
```

### Task 6: Verify PR 3 and production readiness

**Files:**
- Modify only for defects found inside PR 3 scope.

**Interfaces:**
- Produces: release evidence and a dry-run report; production apply remains a separately logged operator action after deployment verification.

- [ ] **Step 1: Run the complete repair/observability regression set**

Run: `python -m pytest tests/test_daily_world_projection_repair_scan.py tests/test_daily_world_projection_backup.py tests/test_daily_world_projection_repair_audit.py tests/test_repair_daily_world_projections_cli.py tests/test_daily_world_projection_rebuild.py tests/test_daily_world_projection_observability.py tests/test_world_projection_repair_runbook.py -q`

Expected: exit 0.

- [ ] **Step 2: Run all projection and daily compatibility tests**

Run: `python -m pytest tests/test_daily_world_projection_repository.py tests/test_daily_world_projection_service.py tests/test_daily_projection_enqueue.py tests/test_daily_projection_serial_apply.py tests/test_world_projection_resolver.py tests/test_daily_generation_transaction.py tests/test_daily_choice_processor.py tests/test_daily_event_revision.py -q`

Expected: exit 0.

- [ ] **Step 3: Run repository gates**

Run: `./test.sh preflight && ./test.sh contract && ./test.sh db && ./test.sh frontend`

Expected: every command exits 0. Run `./test.sh all` once in the designated integration worktree with the E2E lock available.

- [ ] **Step 4: Rehearse dry-run and restore on a disposable database**

Copy a fixture database to a temporary path, run dry-run, apply with its exact hash, wait for completion using a fake extractor, verify non-projection digest equality, then restore from backup into the disposable database and verify its original full-state checksum.

Expected: apply and restore are both reproducible; no production path is touched.

- [ ] **Step 5: Verify current release evidence before production apply**

Check, separately and with timestamps: `origin/main`, local gates, CI, deployed revision, API health, projection feature flag, dry-run report hash, and backup directory capacity. Only then run the documented apply command. After completion, verify game 156 can generate through `generate_missing`, projection watermarks advance, and no visible state digest changed.

- [ ] **Step 6: Record a verification-only fix commit when needed**

```bash
git add src scripts tests docs/runbooks
git commit -m "test: close projection repair regressions"
```

Skip this commit only when `git status --short` is empty.
