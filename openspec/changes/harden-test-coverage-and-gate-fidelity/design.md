## Context

Story2 currently uses `test.sh` as the local source of truth for Preflight + five test layers: static analysis, imports, contracts, real DB, and browser E2E. Recent OpenSpec changes correctly wired their new focused tests into those layers, but the broader repository has accumulated older contract tests that no longer represent current implementation decisions.

The current coverage picture is therefore split:

- Maintained backend CI coverage runs a small, reliable gate subset and passes, but reports low `src` coverage.
- Full backend pytest reports much higher coverage, but the full suite contains stale failures and cannot be treated as a merge gate.
- Frontend Jest coverage is healthy enough to enforce a global threshold, but several high-risk state stores and components remain thinly covered.

## Goals / Non-Goals

**Goals:**
- Make coverage reports state whether they are maintained-gate coverage or full-suite coverage.
- Keep fast, reliable maintained gates green while the full backend suite is triaged.
- Add contracts that detect drift between `test.sh`, coverage CI, and new OpenSpec test wiring.
- Add focused tests for high-risk state-machine paths before raising thresholds.
- Introduce coverage thresholds in stages so they become useful gates rather than noisy metrics.

**Non-Goals:**
- Do not rewrite the whole test suite in one PR.
- Do not weaken recent no-mock/no-skip gate tests.
- Do not run full E2E/browser suites in parallel worker branches.
- Do not treat raw coverage percentage as a substitute for user-flow coverage.
- Do not change product behavior unless a failing, current contract proves the behavior is required.

## Decisions

1. Maintain two explicit backend coverage modes.

   `maintained` coverage runs the currently trusted gate subset and may block CI with a modest threshold. `full` coverage runs the entire backend suite only after stale failures are resolved. This avoids pretending that full-suite coverage is reliable while retaining visibility into the full test debt.

   Alternative considered: immediately switch CI coverage to `pytest tests`. Rejected because the full suite currently has many unrelated failures; doing so would turn coverage hardening into a broad feature-and-legacy-repair PR.

2. Treat stale contract tests as triage items, not automatic implementation requirements.

   Each failing legacy contract must be classified as one of:
   - restore production behavior because the contract is still correct,
   - update the test because the implementation intentionally changed,
   - archive or quarantine the test with an explicit reason because it no longer represents a maintained contract.

   Alternative considered: fix production until every old contract passes. Rejected because several tests assert removed symbols such as old music cache internals and would reintroduce design that may no longer be desired.

3. Use risk-weighted coverage targets.

   First coverage additions target stateful, user-visible paths: story voice reading, scene image state, music queue/playback, SSE parsing/retry, and persistence recovery. Files with low coverage but little behavior are lower priority than state machines with recent regressions.

   Alternative considered: sort files by lowest percentage only. Rejected because it would prioritize easy but low-value files over gameplay-critical paths.

4. Keep coverage thresholds staged.

   Frontend keeps its existing global Jest threshold. Backend starts with a maintained-gate threshold and only adopts a full-suite threshold after full backend pytest is green or the stale suites are explicitly excluded from that target.

   Alternative considered: set a high backend threshold immediately. Rejected because the maintained subset measured about one quarter of `src`, which would produce false failures before the suite selection is corrected.

5. Reduce noisy test output separately from behavior assertions.

   Tests may assert expected error paths, but common console noise should be silenced or asserted intentionally in test helpers. This keeps CI logs actionable without hiding real failures.

## Risks / Trade-offs

- [Risk] Maintained coverage may be mistaken for full repository confidence. -> Mitigation: use explicit names in commands, workflow job names, artifacts, and summaries.
- [Risk] Quarantining stale tests can hide real regressions. -> Mitigation: require an explicit stale-test reason and preserve a follow-up task for every excluded suite.
- [Risk] Thresholds may encourage superficial tests. -> Mitigation: require high-risk state-machine scenarios before raising thresholds.
- [Risk] CI time can grow quickly. -> Mitigation: keep browser/E2E coverage in existing `test.sh e2e` and avoid adding it to unit coverage jobs.
