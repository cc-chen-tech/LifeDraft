## 1. Coverage Mode Contracts

- [x] 1.1 Add a failing backend contract test that detects drift between `test.sh` maintained backend gate tests and `.github/workflows/coverage.yml`.
- [x] 1.2 Update coverage workflow naming and selection so maintained backend coverage is explicit and includes all current maintained backend gate tests.
- [x] 1.3 Add local `test.sh` commands for maintained backend coverage and full backend coverage, with clear labels.
- [x] 1.4 Add a modest maintained backend `--cov-fail-under` threshold after the maintained coverage command is stable.

## 2. Legacy Failure Triage

- [x] 2.1 Generate a machine-readable inventory of current full-backend failures grouped by file and domain.
- [x] 2.2 Classify music cache and health failures as restore, update, or stale-contract exclusions.
- [x] 2.3 Classify text normalization, era validator, scene image SSE, SSE retry, and security contract failures.
- [x] 2.4 Document any excluded stale suites with explicit reasons and follow-up owners before excluding them from maintained gates.

## 3. High-Risk Frontend Coverage

- [x] 3.1 Add focused Jest tests for `useStoryVoiceStore` success, failure, retry, text hash, and music ducking behavior.
- [x] 3.2 Add focused Jest tests for scene image store cache refresh and failure recovery paths.
- [x] 3.3 Add focused Jest tests for music store queue preservation and user intent paths.
- [x] 3.4 Keep frontend coverage thresholds passing and avoid noisy, unasserted console output in the new tests.

## 4. Verification

- [x] 4.1 Run `openspec validate harden-test-coverage-and-gate-fidelity --strict`.
- [x] 4.2 Run the new gate fidelity contract test.
- [x] 4.3 Run maintained backend coverage.
- [x] 4.4 Run targeted frontend coverage for newly covered stores.
- [x] 4.5 Re-run the relevant `test.sh` layers and summarize remaining full-suite debt.

## 5. First Maintained Backend Ratchet

- [x] 5.1 Promote stable gameplay, scene-image, collection cache, session cache, and SSE contract groups into maintained backend coverage.
- [x] 5.2 Keep unstable legacy router/mock suites out of maintained coverage and record them for follow-up repair.
- [x] 5.3 Raise maintained backend `--cov-fail-under` from 25 to 30 in local and CI coverage gates.
- [x] 5.4 Add gate fidelity checks for the promoted high-risk groups and first threshold ratchet.
- [x] 5.5 Run maintained backend coverage, preflight, OpenSpec validation, and full backend suite after the ratchet.

## 6. Second Maintained Backend Ratchet

- [x] 6.1 Stabilize legacy API games and collection tests against module reload and dependency override ordering.
- [x] 6.2 Promote stable legacy API, gameplay, image, session repository, and world-model suites into maintained backend gates.
- [x] 6.3 Raise maintained backend `--cov-fail-under` from 30 to 40 in local and CI coverage gates.
- [x] 6.4 Add gate fidelity checks for the promoted legacy groups and second threshold ratchet.
- [x] 6.5 Run the expanded maintained backend coverage candidate and confirm it passes the 40% gate.
