## Why

Full backend exploration still has legacy contract failures that are not yet reliable enough for maintained gates. Restoring the highest-signal contracts incrementally will raise backend confidence without promoting stale assertions wholesale.

## What Changes

- Reconcile legacy backend contract tests with current production behavior.
- Restore narrow production contracts when the test exposes a real missing compatibility surface.
- Update stale expectations only when current behavior is intentional and already covered by maintained gates.
- Promote repaired groups into maintained coverage after they pass reliably.

## Capabilities

### New Capabilities
- `backend-legacy-contract-restoration`: Legacy backend tests are repaired or reclassified in focused groups and only promoted when they match current product behavior.

### Modified Capabilities

None.

## Impact

- Backend AI/text quality helpers.
- Legacy contract tests under `tests/`.
- Maintained coverage and preflight gate wiring as repaired groups become stable.
- OpenSpec triage artifacts tracking which failure groups remain unresolved.
