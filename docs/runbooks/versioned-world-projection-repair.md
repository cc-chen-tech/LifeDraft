# Versioned daily world-projection repair

Use this procedure only after the PR 1, PR 2, and PR 3 revisions are merged,
deployed, and their deployed revision has been independently verified. It is an
operator procedure for a production environment; it is not a deployment step
and it must not be run from a developer checkout or against a local database.

## Preconditions

Before Phase 1, confirm all of the following in the same environment that will
later run Phase 2:

1. The deployed revision contains the approved PR 1, PR 2, and PR 3 changes.
2. The API health check is successful, and normal player traffic is understood.
3. `ENABLE_DAILY_WORLD_PROJECTION_V1` is enabled and the projection worker is
   running.
4. The backup filesystem has sufficient capacity for every selected complete
   state and the operator identity can create and read files there. The default
   root is `data/repair-backups/world-projection`, relative to the repository
   root. Set `WORLD_PROJECTION_REPAIR_BACKUP_DIR` in the service environment
   before Phase 1 to use an approved alternate root.
5. The repair is scheduled after merge and deployment. Do not run production
   apply as part of a code review, test run, or release build.

The command reads `WORLD_PROJECTION_REPAIR_BACKUP_DIR` when it creates a
backup. Keep that setting unchanged across both phases. Provision the evidence
root before this procedure; do not create it during a dry-run check.

## Phase 1: preflight and dry run

From the repository root, run this block and then stop. `mktemp -d` creates a
unique no-clobber directory beneath the preprovisioned evidence root. It keeps
stdout JSON and stderr logs separately, and atomically writes the initial
manifest only after the dry-run hash has been parsed.

```bash
set -euo pipefail

WORLD_REPAIR_EVIDENCE_DIR="${WORLD_PROJECTION_REPAIR_BACKUP_DIR:-data/repair-backups/world-projection}"
test -d "$WORLD_REPAIR_EVIDENCE_DIR"
test -w "$WORLD_REPAIR_EVIDENCE_DIR"
WORLD_REPAIR_RUN_DIR="$(mktemp -d "$WORLD_REPAIR_EVIDENCE_DIR/world-projection-repair.XXXXXX")"
: "${WORLD_REPAIR_RUN_DIR:?repair run directory missing}"

python scripts/world_projection_status.py --json >"$WORLD_REPAIR_RUN_DIR/status-before.json" 2>"$WORLD_REPAIR_RUN_DIR/status-before.stderr.log"
python scripts/repair_daily_world_projections.py --dry-run >"$WORLD_REPAIR_RUN_DIR/dry-run.json" 2>"$WORLD_REPAIR_RUN_DIR/dry-run.stderr.log"
WORLD_REPAIR_REPORT_HASH="$(
  python - "$WORLD_REPAIR_RUN_DIR/dry-run.json" <<'PY'
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
python - "$WORLD_REPAIR_RUN_DIR" "$WORLD_REPAIR_REPORT_HASH" <<'PY'
import json
import os
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
report_hash = sys.argv[2]
manifest = {
    "report_hash": report_hash,
    "dry_run_path": "dry-run.json",
    "apply": None,
}
temporary = run_dir / "manifest.json.tmp"
temporary.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
with temporary.open("rb") as manifest_file:
    os.fsync(manifest_file.fileno())
os.replace(temporary, run_dir / "manifest.json")
print(run_dir)
PY
```

An unhealthy status snapshot still uses exit 0. Inspect the status JSON and
dry-run selection manually, obtain explicit operator authorization, and record
the approved hash out of band. Phase 1 does not apply anything; do not continue
to Phase 2 from this shell automatically.

## Phase 2: approved apply

Open a new shell in the same verified environment. Set
`WORLD_REPAIR_RUN_DIR` to the directory printed by Phase 1 and explicitly set
`WORLD_REPAIR_APPROVED_REPORT_HASH` to the separately authorized value. This
block reconstructs the dry-run scope from disk and refuses to apply when either
hash differs.

```bash
set -euo pipefail

: "${WORLD_REPAIR_RUN_DIR:?set the Phase 1 run directory}"
: "${WORLD_REPAIR_APPROVED_REPORT_HASH:?set the explicitly approved report hash}"
WORLD_REPAIR_REPORT_HASH="$(
  python - "$WORLD_REPAIR_RUN_DIR" "$WORLD_REPAIR_APPROVED_REPORT_HASH" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
approved_hash = sys.argv[2]
with (run_dir / "manifest.json").open(encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)
with (run_dir / "dry-run.json").open(encoding="utf-8") as dry_run_file:
    dry_run = json.load(dry_run_file)
manifest_hash = manifest.get("report_hash")
dry_run_hash = dry_run.get("report_hash")
if not isinstance(manifest_hash, str) or not manifest_hash:
    raise SystemExit("manifest report hash missing")
if not isinstance(dry_run_hash, str) or not dry_run_hash:
    raise SystemExit("dry-run report hash missing")
candidates = dry_run.get("candidates")
if not isinstance(candidates, list):
    raise SystemExit("dry-run candidates missing")
canonical_candidates = json.dumps(
    {"candidates": candidates},
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
if hashlib.sha256(canonical_candidates).hexdigest() != dry_run_hash:
    raise SystemExit("dry-run candidates do not match report hash")
if manifest_hash != dry_run_hash:
    raise SystemExit("manifest report hash does not match dry run")
if approved_hash != manifest_hash:
    raise SystemExit("approved report hash does not match manifest")
print(manifest_hash)
PY
)"
: "${WORLD_REPAIR_REPORT_HASH:?approved report hash missing}"

python - "$WORLD_REPAIR_RUN_DIR" <<'PY'
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
with (run_dir / "manifest.json").open(encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)
if manifest.get("apply") is not None:
    raise SystemExit("manifest apply evidence already exists; start a new repair run")
evidence_names = (
    "apply.stdout.json.tmp",
    "apply.stdout.json",
    "apply.stderr.log.tmp",
    "apply.stderr.log",
    "status-after.json",
    "status-after.stderr.log",
)
if any((run_dir / name).exists() for name in evidence_names):
    raise SystemExit("interrupted Phase 2 evidence requires a new repair run")
PY

if python scripts/repair_daily_world_projections.py --apply --expected-report-hash "$WORLD_REPAIR_REPORT_HASH" --wait --timeout-seconds 1800 >"$WORLD_REPAIR_RUN_DIR/apply.stdout.json.tmp" 2>"$WORLD_REPAIR_RUN_DIR/apply.stderr.log.tmp"; then
  apply_exit_code=0
else
  apply_exit_code=$?
fi
mv "$WORLD_REPAIR_RUN_DIR/apply.stdout.json.tmp" "$WORLD_REPAIR_RUN_DIR/apply.stdout.json"
mv "$WORLD_REPAIR_RUN_DIR/apply.stderr.log.tmp" "$WORLD_REPAIR_RUN_DIR/apply.stderr.log"
python - "$WORLD_REPAIR_RUN_DIR" "$WORLD_REPAIR_REPORT_HASH" "$apply_exit_code" <<'PY'
import json
import os
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
approved_report_hash = sys.argv[2]
apply_exit_code = int(sys.argv[3])
with (run_dir / "manifest.json").open(encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)
with (run_dir / "apply.stdout.json").open(encoding="utf-8") as apply_file:
    apply = json.load(apply_file)
audit_ids = apply.get("audit_ids")
observed_report_hash = apply.get("report_hash")
status = apply.get("status")
if (
    not isinstance(observed_report_hash, str)
    or not observed_report_hash
    or not isinstance(status, str)
    or not status
    or not isinstance(audit_ids, list)
    or any(isinstance(audit_id, bool) or not isinstance(audit_id, int) or audit_id <= 0 for audit_id in audit_ids)
    or len(audit_ids) != len(set(audit_ids))
):
    raise SystemExit("apply stdout is not a machine-readable exact scope")
if apply_exit_code == 0 and observed_report_hash != approved_report_hash:
    raise SystemExit("successful apply observed report hash does not match approved hash")
manifest["apply"] = {
    "approved_report_hash": approved_report_hash,
    "audit_ids": audit_ids,
    "exit_code": apply_exit_code,
    "observed_report_hash": observed_report_hash,
    "status": status,
}
temporary = run_dir / "manifest.json.tmp"
temporary.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
with temporary.open("rb") as manifest_file:
    os.fsync(manifest_file.fileno())
os.replace(temporary, run_dir / "manifest.json")
PY

if [ "$apply_exit_code" -ne 0 ]; then
  sed -n '1,200p' "$WORLD_REPAIR_RUN_DIR/apply.stderr.log" >&2
  exit "$apply_exit_code"
fi
WORLD_REPAIR_AUDIT_IDS="$(
  python - "$WORLD_REPAIR_RUN_DIR/manifest.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)
audit_ids = manifest.get("apply", {}).get("audit_ids")
if not isinstance(audit_ids, list) or not audit_ids:
    raise SystemExit("successful apply returned no audit IDs")
print(",".join(str(audit_id) for audit_id in audit_ids))
PY
)"
: "${WORLD_REPAIR_AUDIT_IDS:?successful apply returned no audit IDs}"
python scripts/world_projection_status.py --json >"$WORLD_REPAIR_RUN_DIR/status-after.json" 2>"$WORLD_REPAIR_RUN_DIR/status-after.stderr.log"
```

The CLI writes one machine-readable JSON payload to stdout even when the report
changed, wait ends in `failed_invariant`, `failed_fenced`, `timed_out`, or a
partial apply failure. Phase 2 stores the approved and observed report hashes,
status, audit IDs, and stderr before checking the exit code, then atomically
updates `manifest.json` before returning the original nonzero code. In
particular, an observed stale report hash is evidence for the CLI's exit 2, not
a parser failure that may replace that exit code.

## Read-only inspection and backup verification

Use `status-after.json` to inspect pending rows, suspicious-empty counts, and
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

Every following block can start in a new shell with only
`WORLD_REPAIR_RUN_DIR`. Reconstruct the exact report hash and audit IDs from
the manifest instead of using a latest-audit query or old shell variables.

```bash
set -euo pipefail

: "${WORLD_REPAIR_RUN_DIR:?set the Phase 1 run directory}"
WORLD_REPAIR_SCOPE_JSON="$(
  python - "$WORLD_REPAIR_RUN_DIR/manifest.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)
apply = manifest.get("apply")
report_hash = manifest.get("report_hash")
if not isinstance(apply, dict) or apply.get("exit_code") not in (0, 3, 4):
    raise SystemExit("manifest does not contain a restorable apply")
audit_ids = apply.get("audit_ids")
if (
    apply.get("approved_report_hash") != report_hash
    or apply.get("observed_report_hash") != report_hash
    or not isinstance(report_hash, str)
    or not isinstance(audit_ids, list)
    or not audit_ids
    or len(audit_ids) != len(set(audit_ids))
):
    raise SystemExit("manifest repair scope is invalid")
print(json.dumps({"audit_ids": audit_ids, "report_hash": report_hash}))
PY
)"
WORLD_REPAIR_REPORT_HASH="$(python -c 'import json,sys; print(json.loads(sys.argv[1])["report_hash"])' "$WORLD_REPAIR_SCOPE_JSON")"
WORLD_REPAIR_AUDIT_IDS="$(python -c 'import json,sys; print(",".join(str(value) for value in json.loads(sys.argv[1])["audit_ids"]))' "$WORLD_REPAIR_SCOPE_JSON")"
: "${WORLD_REPAIR_REPORT_HASH:?manifest report hash missing}"
: "${WORLD_REPAIR_AUDIT_IDS:?manifest audit IDs missing}"
python - "$WORLD_REPAIR_REPORT_HASH" "$WORLD_REPAIR_AUDIT_IDS" <<'PY'
import sys

from src.database.models import DailyWorldProjectionRepairAudit, SessionLocal
from src.services.daily_world_projection_backup import verify_state_backup

report_hash = sys.argv[1]
audit_ids = tuple(int(value) for value in sys.argv[2].split(",") if value)
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
        if audit.report_hash != report_hash or audit.status not in {
            "complete", "failed_invariant", "failed_fenced", "timed_out"
        }:
            raise SystemExit("audit is no longer the approved terminal scope")
        verify_state_backup(audit.backup_path, audit.backup_sha256)
print("exact repair scope and backup checksums verified")
PY
```

Apply writes a complete-state backup, then calls `verify_state_backup` before
it creates an audit or queues a rebuild. Do not expose connection material in
shell history, logs, tickets, or this runbook. Keep audit output limited to the
operator channel that is approved for state metadata.

## Wait outcomes and containment

With `--wait`, a fully completed repair exits 0. Stop and preserve the
dry-run report, run directory, manifest, status JSON, stdout JSON, stderr log,
and exact audit IDs for any other result:

| Result | Meaning | Required action |
| --- | --- | --- |
| Exit 3 with `failed_invariant` | Visible non-projection state did not remain unchanged. | Do not retry or restore automatically; investigate current player activity. |
| Exit 4 with `failed_fenced` | A rebuild was fenced by changed source state. | Do not retry or restore automatically; inspect the worker and audit. |
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
`WORLD_REPAIR_AUDIT_ID` explicitly to one ID from the manifest's
`WORLD_REPAIR_AUDIT_IDS`; never select an audit by recency. Re-run this block
before each individual restore. The CLI acquires that game's lock, rereads the
selected audit with `FOR UPDATE`, requires the exact report hash and one safe
terminal status (`complete`, `failed_invariant`, `failed_fenced`, or
`timed_out`), and rejects the restore if a newer repair audit exists for that
game with `newer repair audit exists for this game`. A printed terminal restore
command is only an explicit, guarded intent after human audit review; it never
restores automatically.

```bash
set -euo pipefail

: "${WORLD_REPAIR_RUN_DIR:?set the Phase 1 run directory}"
: "${WORLD_REPAIR_AUDIT_ID:?set one exact audit ID from the manifest scope}"
WORLD_REPAIR_SCOPE_JSON="$(
  python - "$WORLD_REPAIR_RUN_DIR/manifest.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as manifest_file:
    manifest = json.load(manifest_file)
apply = manifest.get("apply")
report_hash = manifest.get("report_hash")
audit_ids = apply.get("audit_ids") if isinstance(apply, dict) else None
if (
    not isinstance(report_hash, str)
    or not isinstance(audit_ids, list)
    or not audit_ids
    or apply.get("approved_report_hash") != report_hash
    or apply.get("observed_report_hash") != report_hash
    or apply.get("exit_code") not in (0, 3, 4)
):
    raise SystemExit("manifest repair scope is invalid")
print(json.dumps({"audit_ids": audit_ids, "report_hash": report_hash}))
PY
)"
WORLD_REPAIR_REPORT_HASH="$(python -c 'import json,sys; print(json.loads(sys.argv[1])["report_hash"])' "$WORLD_REPAIR_SCOPE_JSON")"
WORLD_REPAIR_AUDIT_IDS="$(python -c 'import json,sys; print(",".join(str(value) for value in json.loads(sys.argv[1])["audit_ids"]))' "$WORLD_REPAIR_SCOPE_JSON")"
case ",$WORLD_REPAIR_AUDIT_IDS," in
  *",$WORLD_REPAIR_AUDIT_ID,"*) ;;
  *) echo "selected audit is outside the manifest scope" >&2; exit 2 ;;
esac
python scripts/repair_daily_world_projections.py --restore-audit-id "$WORLD_REPAIR_AUDIT_ID" --expected-report-hash "$WORLD_REPAIR_REPORT_HASH"
```

The restore command validates its stored backup checksum and rechecks the
current non-projection digest under the game lock. It supersedes only the
audited rebuild identities. A refusal is a stop signal, not permission to force
an overwrite.

## Post-apply player check

After a successful wait and checksum verification, use a controlled generation
request for each repaired player. When no current event remains,
`replace_current` must resolve to `generate_missing`; confirm that a new daily
event is produced, projection watermarks advance, and the audit's
non-projection digest remains unchanged. Record the report hash, exact audit
IDs, status snapshots, and outcome in the incident record without including
player prose or connection material.
