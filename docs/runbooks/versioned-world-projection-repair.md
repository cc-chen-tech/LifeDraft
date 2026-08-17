# Versioned daily world-projection repair

Use this procedure only after the PR 1, PR 2, and PR 3 revisions are merged,
deployed, and their deployed revision has been independently verified. It is an
operator procedure for a production environment; it is not a deployment step
and it must not be run from a developer checkout or against a local database.

## Preconditions

Before the dry run, confirm all of the following in the same environment that
will run the apply command:

1. The deployed revision contains the approved PR 1, PR 2, and PR 3 changes.
2. The API health check is successful, and normal player traffic is understood.
3. `ENABLE_DAILY_WORLD_PROJECTION_V1` is enabled and the projection worker is
   running.
4. The backup filesystem has sufficient capacity for every selected complete
   state and the operator identity can create and read files there. The default
   root is `data/repair-backups/world-projection`, relative to the repository
   root. Set `WORLD_PROJECTION_REPAIR_BACKUP_DIR` in the service environment
   before the dry run to use an approved alternate root.
5. The repair is scheduled after merge and deployment. Do not run production
   apply as part of a code review, test run, or release build.

The repair command reads `WORLD_PROJECTION_REPAIR_BACKUP_DIR` only when it
creates the backup. Keep that setting unchanged from dry run through apply and
wait. Provision the directory before this procedure; do not create it during a
dry-run check.

## Safe repair sequence

From the repository root in the verified production environment, run this
block in one shell. The files retained by `tee` are the durable operator
evidence for this attempt; do not replace them with output from another run.

```bash
set -euo pipefail

WORLD_REPAIR_EVIDENCE_DIR="${WORLD_PROJECTION_REPAIR_BACKUP_DIR:-data/repair-backups/world-projection}"
: "${WORLD_REPAIR_EVIDENCE_DIR:?repair evidence directory missing}"
WORLD_REPAIR_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
: "${WORLD_REPAIR_RUN_ID:?repair run identifier missing}"
WORLD_REPAIR_DRY_RUN="$WORLD_REPAIR_EVIDENCE_DIR/$WORLD_REPAIR_RUN_ID-dry-run.json"
WORLD_REPAIR_APPLY_OUTPUT="$WORLD_REPAIR_EVIDENCE_DIR/$WORLD_REPAIR_RUN_ID-apply.json"

python scripts/world_projection_status.py --json | tee "$WORLD_REPAIR_EVIDENCE_DIR/$WORLD_REPAIR_RUN_ID-status-before.json"
python scripts/repair_daily_world_projections.py --dry-run | tee "$WORLD_REPAIR_DRY_RUN"
WORLD_REPAIR_REPORT_HASH="$(
  python - "$WORLD_REPAIR_DRY_RUN" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as report_file:
    report = json.load(report_file)
report_hash = report.get("report_hash")
if not isinstance(report_hash, str) or not report_hash:
    raise SystemExit("dry-run report hash missing")
print(report_hash)
PY
)"
: "${WORLD_REPAIR_REPORT_HASH:?dry-run report hash missing}"
python scripts/repair_daily_world_projections.py --apply --expected-report-hash "$WORLD_REPAIR_REPORT_HASH" --wait --timeout-seconds 1800 | tee "$WORLD_REPAIR_APPLY_OUTPUT"
WORLD_REPAIR_AUDIT_IDS="$(
  python - "$WORLD_REPAIR_APPLY_OUTPUT" "$WORLD_REPAIR_REPORT_HASH" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as apply_file:
    apply = json.load(apply_file)
report_hash = sys.argv[2]
audit_ids = apply.get("audit_ids")
if (
    apply.get("report_hash") != report_hash
    or apply.get("status") != "complete"
    or not isinstance(audit_ids, list)
    or not audit_ids
    or any(isinstance(audit_id, bool) or not isinstance(audit_id, int) or audit_id <= 0 for audit_id in audit_ids)
    or len(audit_ids) != len(set(audit_ids))
):
    raise SystemExit("apply output is not an exact completed repair scope")
print(",".join(str(audit_id) for audit_id in audit_ids))
PY
)"
: "${WORLD_REPAIR_AUDIT_IDS:?apply returned no audit IDs}"
python scripts/world_projection_status.py --json | tee "$WORLD_REPAIR_EVIDENCE_DIR/$WORLD_REPAIR_RUN_ID-status-after.json"
```

The first status command is a read-only snapshot. An unhealthy snapshot still
uses exit 0, so inspect its JSON fields rather than treating that exit code as
an approval to apply. A query failure is nonzero and stops the procedure.

Dry-run has no writes. Review `"$WORLD_REPAIR_DRY_RUN"` before continuing: it
is the complete selected scope and its `report_hash` is the approval value.
Apply rescans in the same environment and refuses to mutate if the supplied
hash differs. Do not add a one-off game filter to production apply; the scan
rules select the scope. `set -euo pipefail` ensures a failed status, dry run,
apply, JSON parse, or `tee` pipeline stops before a later command can run.

## Read-only inspection and backup verification

Use the final status JSON to inspect pending rows, suspicious-empty counts, and
repair-audit counts. For a read-only audit overview, use an approved read-only
database session with this query:

```sql
SELECT audit_id, status, report_hash, backup_path, backup_sha256,
       non_projection_digest_before, non_projection_digest_after,
       created_at, completed_at
FROM daily_world_projection_repair_audits
ORDER BY audit_id DESC
LIMIT 20;
```

In the same shell as the safe sequence, validate every audit emitted by this
specific apply output and verify every backup checksum. This fails closed if an
emitted audit was changed, is unfinished, has a different report scope, is
missing, or if a newer audit appeared after the apply scope.

```bash
set -euo pipefail

: "${WORLD_REPAIR_REPORT_HASH:?run the safe sequence first}"
: "${WORLD_REPAIR_AUDIT_IDS:?run the safe sequence first}"
python - "$WORLD_REPAIR_REPORT_HASH" "$WORLD_REPAIR_AUDIT_IDS" <<'PY'
import sys

from src.database.models import DailyWorldProjectionRepairAudit, SessionLocal
from src.services.daily_world_projection_backup import verify_state_backup

report_hash = sys.argv[1]
audit_ids = tuple(int(value) for value in sys.argv[2].split(",") if value)
if not audit_ids or len(audit_ids) != len(set(audit_ids)):
    raise SystemExit("exact audit IDs missing")

with SessionLocal() as db:
    audits = {
        int(audit.audit_id): audit
        for audit in db.query(DailyWorldProjectionRepairAudit)
        .filter(DailyWorldProjectionRepairAudit.audit_id.in_(audit_ids))
        .all()
    }
    if set(audits) != set(audit_ids):
        raise SystemExit("an exact audit is missing")
    for audit_id in audit_ids:
        audit = audits[audit_id]
        if audit.report_hash != report_hash:
            raise SystemExit("audit belongs to a different repair scope")
        if audit.status != "complete":
            raise SystemExit("audit is not complete")
        verify_state_backup(audit.backup_path, audit.backup_sha256)
    newer = (
        db.query(DailyWorldProjectionRepairAudit.audit_id)
        .filter(DailyWorldProjectionRepairAudit.audit_id > max(audit_ids))
        .first()
    )
    if newer is not None:
        raise SystemExit("newer repair audit detected")
print("exact repair scope and backup checksums verified")
PY
```

Apply writes a complete-state backup, then calls `verify_state_backup` before
it creates an audit or queues a rebuild. Do not expose connection material in
shell history, logs, tickets, or this runbook. Keep audit output limited to the
operator channel that is approved for state metadata.

## Wait outcomes and containment

With `--wait`, a fully completed repair exits 0. Stop and preserve the
dry-run report, persisted apply output, status JSON, and exact audit IDs for
any other result:

| Result | Meaning | Required action |
| --- | --- | --- |
| Exit 3 with `failed_invariant` | Visible non-projection state did not remain unchanged. | Do not retry or restore automatically; investigate current player activity. |
| Exit 4 with `failed_fenced` | A rebuild was fenced by changed source state. | Do not retry or restore automatically; inspect the latest state and audit. |
| Exit 4 with `timed_out` | Completion was not observed before the timeout. | Do not retry or restore automatically; inspect the worker and audit status. |

For any failed, fenced, or timeout outcome, disable further repair scheduling
while investigating. If containment is needed, set
`ENABLE_DAILY_WORLD_PROJECTION_V1=false` through the normal deployment
configuration and restart using the established service procedure. This rolls
the projection path back to the provisional path; it does not restore state.

## Restore preparation and guarded restore

Restore is a projection-only operation. Before restoring, inspect the audit,
verify its backup as above, and compare the current latest state with the
audit's non-projection digest. Stop if newer player activity changed the latest
state: the restore command must refuse that condition, and operators must not
overwrite it automatically.

An apply can return several audit IDs. Review them one at a time. Set
`WORLD_REPAIR_AUDIT_ID` explicitly to one ID from
`WORLD_REPAIR_AUDIT_IDS`; never select an audit by recency. Re-run this block
before each individual restore. It accepts previously restored sibling audits,
but requires the selected audit to remain complete and rejects a newer or
different-scope audit.

```bash
set -euo pipefail

: "${WORLD_REPAIR_REPORT_HASH:?run the safe sequence first}"
: "${WORLD_REPAIR_AUDIT_IDS:?run the safe sequence first}"
: "${WORLD_REPAIR_AUDIT_ID:?set one exact audit ID from WORLD_REPAIR_AUDIT_IDS}"
python - "$WORLD_REPAIR_REPORT_HASH" "$WORLD_REPAIR_AUDIT_IDS" "$WORLD_REPAIR_AUDIT_ID" <<'PY'
import sys

from src.database.models import DailyWorldProjectionRepairAudit, SessionLocal
from src.services.daily_world_projection_backup import verify_state_backup

report_hash = sys.argv[1]
audit_ids = tuple(int(value) for value in sys.argv[2].split(",") if value)
selected_audit_id = int(sys.argv[3])
if not audit_ids or selected_audit_id not in audit_ids:
    raise SystemExit("selected audit is outside the exact apply scope")

with SessionLocal() as db:
    audits = {
        int(audit.audit_id): audit
        for audit in db.query(DailyWorldProjectionRepairAudit)
        .filter(DailyWorldProjectionRepairAudit.audit_id.in_(audit_ids))
        .all()
    }
    if set(audits) != set(audit_ids):
        raise SystemExit("an exact audit is missing")
    for audit_id in audit_ids:
        audit = audits[audit_id]
        if audit.report_hash != report_hash:
            raise SystemExit("audit belongs to a different repair scope")
        if audit_id == selected_audit_id and audit.status != "complete":
            raise SystemExit("selected audit is not complete")
        if audit_id != selected_audit_id and audit.status not in {"complete", "restored"}:
            raise SystemExit("sibling audit is unfinished")
    newer = (
        db.query(DailyWorldProjectionRepairAudit.audit_id)
        .filter(DailyWorldProjectionRepairAudit.audit_id > max(audit_ids))
        .first()
    )
    if newer is not None:
        raise SystemExit("newer repair audit detected")
    selected_audit = audits[selected_audit_id]
    verify_state_backup(selected_audit.backup_path, selected_audit.backup_sha256)
print("selected exact repair audit and backup checksum verified")
PY
python scripts/repair_daily_world_projections.py --restore-audit-id "$WORLD_REPAIR_AUDIT_ID"
```

The restore command validates its stored backup checksum, locks the game, and
refuses a changed non-projection digest. It supersedes only the audited rebuild
identities. A refusal is a stop signal, not permission to force an overwrite.

## Post-apply player check

After a successful wait and checksum verification, use a controlled generation
request for each repaired player. When no current event remains,
`replace_current` must resolve to `generate_missing`; confirm that a new daily
event is produced, projection watermarks advance, and the audit's
non-projection digest remains unchanged. Record the report hash, exact audit
IDs, status snapshots, and outcome in the incident record without including
player prose or connection material.
