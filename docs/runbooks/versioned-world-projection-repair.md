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

From the repository root in the verified production environment, run these
commands in this exact order:

```bash
python scripts/world_projection_status.py --json
python scripts/repair_daily_world_projections.py --dry-run > /tmp/world-projection-dry-run.json
WORLD_REPAIR_REPORT_HASH=$(python -c 'import json; print(json.load(open("/tmp/world-projection-dry-run.json", encoding="utf-8"))["report_hash"])')
python scripts/repair_daily_world_projections.py --apply --expected-report-hash "$WORLD_REPAIR_REPORT_HASH" --wait --timeout-seconds 1800
python scripts/world_projection_status.py --json
```

The first status command is a read-only snapshot. An unhealthy snapshot still
uses exit 0, so inspect its JSON fields rather than treating that exit code as
an approval to apply. A query failure is nonzero and stops the procedure.

Dry-run has no writes. Review `/tmp/world-projection-dry-run.json` before
continuing: it is the complete selected scope and its `report_hash` is the
approval value. Apply rescans in the same environment and refuses to mutate if
the supplied hash differs. Do not add a one-off game filter to production
apply; the scan rules select the scope. Apply writes a complete-state backup,
then calls `verify_state_backup` before it creates an audit or queues a
rebuild.

## Read-only inspection and backup verification

Use the final status JSON to inspect pending rows, suspicious-empty counts,
repair-audit counts, and `latest_completed_repair_audit_id`. For a read-only
audit overview, use an approved read-only database session with this query:

```sql
SELECT audit_id, status, report_hash, backup_path, backup_sha256,
       non_projection_digest_before, non_projection_digest_after,
       created_at, completed_at
FROM daily_world_projection_repair_audits
ORDER BY audit_id DESC
LIMIT 20;
```

After the wait reports a completed audit, obtain its identifier and verify the
backup bytes and embedded complete-state checksum without changing data:

```bash
WORLD_REPAIR_AUDIT_ID=$(python scripts/world_projection_status.py --json | python -c 'import json,sys; print(json.load(sys.stdin)["latest_completed_repair_audit_id"])')
python - "$WORLD_REPAIR_AUDIT_ID" <<'PY'
import sys

from src.database.models import DailyWorldProjectionRepairAudit, SessionLocal
from src.services.daily_world_projection_backup import verify_state_backup

with SessionLocal() as db:
    audit = db.get(DailyWorldProjectionRepairAudit, int(sys.argv[1]))
    if audit is None:
        raise SystemExit("repair audit not found")
    verify_state_backup(audit.backup_path, audit.backup_sha256)
    print("backup checksum verified")
PY
```

Do not expose connection material in shell history, logs, tickets, or this
runbook. Keep audit output limited to the operator channel that is approved for
state metadata.

## Wait outcomes and containment

With `--wait`, a fully completed repair exits 0. Stop and preserve the
dry-run report, status JSON, and audit identifier for any other result:

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

After that review, use this exact audit-ID pipeline from the repository root:

```bash
WORLD_REPAIR_AUDIT_ID=$(python scripts/world_projection_status.py --json | python -c 'import json,sys; print(json.load(sys.stdin)["latest_completed_repair_audit_id"])')
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
non-projection digest remains unchanged. Record the report hash, audit ID,
status snapshots, and outcome in the incident record without including player
prose or connection material.
