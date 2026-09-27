# Generation diagnostics and regression reliability implementation plan

> Execution: implement the user-approved audit remediation in parallel bounded modules, with one integration owner. Use test-driven development and verify the combined tree before updating the PR.

**Goal:** Every story, image and voice failure can be traced to its user, game, task and attempt without logging private content; durable failure recovery and regression gates cover the audited incidents.

**Architecture:** Extend existing request context and metadata-only telemetry. Write structured lifecycle events through the existing rotating application log and retain model events in a separate mounted rotating log. Rebuild task context from durable identities on worker execution/recovery. Keep runtime behavior fixes at the affected transaction boundaries.

**Scope:** The September 27 audit approved by the user's request to fix all identified problems. Includes diagnostic completeness, persistence failures, validator exceptions, frontend reporting, audio resource ownership, historical regression gates and actual first-day delivery smoke.

**Constraints:** No prompt/story/audio content or credentials in logs. No production mutation or deployment during implementation. Reuse the clean existing isolated worktree and PR #386; preserve the prior fallback fix. Test real business functions and file-backed database boundaries, using deterministic providers for injected failures. Do not claim provider acceptance from fake providers.

## Shared interfaces

- `src.observability.diagnostics.diagnostic_context(**fields)` is a context manager merging request/task identity. Fields: request_id, operation_id, feature, operation, user_id, game_id, job_id, job_type, segment_index, attempt_id.
- `emit_diagnostic(event, *, phase, outcome, error=None, **fields)` writes a metadata-only structured event and returns its payload. Approved fields include identity above, attempt/max_attempts, event_id/revision, batch_id/slot_index/asset_id, error_code/provider_code/provider_trace_id/retryable, finding_codes/severity/disposition, duration_ms/size_bytes/count/persisted/used_fallback/reason/recovery_count/selected_image_id. Unknown or content fields are dropped.
- Model telemetry inherits the active identity and preserves typed provider codes/traces, including through exception causes. Background contexts must use stable task-derived operation IDs and per-attempt identity.

## Review focus

- Two users fail concurrently, then one retries after restart: formatted records remain attributable and no identity leaks across tasks.
- Failure reporting itself encounters a database error: independent log still contains a terminal failure and the Future exception is observed.
- Provider succeeds but validation, disk write, database commit or audio assembly fails: application outcome does not claim successful delivery.
- Errors contain private prompts or credentials: structured diagnostics and retained logs exclude them while preserving safe codes and source locations.
- Existing regression files are added but CI registration drifts: the maintained regression manifest is checked, and the full backend CI discovers every test automatically.

## Tasks

- [x] Core: add failing tests for formatter identity, safe exception frames, provider codes, context isolation and rotating model sink; implement diagnostics/context/formatter changes.
- [x] Stories: per-candidate gate findings and terminal outcomes; fail closed on validator implementation errors; rollback/report failed persistence; prove save/reload through a real SQLite/API boundary.
- [x] Images: instrument job/slot/provider/storage/reference fallback boundaries; observe scheduler Future failures and double database failures; preserve provider codes; test ownership and restart attribution.
- [x] Voice: reconstruct worker context; preserve business codes; distinguish plan/synthesis/assembly/persistence failure; retain error history in logs; test concurrent users, shutdown and assembly. Enforce owned audio access with compatible browser cookie delivery.
- [x] Frontend: bounded metadata-only remote reporting, authenticated server identity, request/task correlation, media/polling recovery events; tests verify network delivery and privacy.
- [x] Gates: register historical regression suites and new tests in a manifest consumed by maintained CI; test registration, document `all` vs full-backend; extend real-provider smoke to production daily opening/save/reload and surfaced options.
- [x] Retention: rotate mounted model/application logs and container stdout, document retention/retrieval and verify configured handlers.
- [x] Integration: run relevant red/green tests, maintained and full backend, frontend unit/integration/types/build and appropriate browser acceptance; inspect failures, review combined diff, update PR with exact evidence.

## Acceptance evidence

Record each task's tests and red/green evidence in the final PR. A successful run must demonstrate a reconstructable operation timeline (including failed attempts), stable user/task association, real persistence/reload and no private content in formatted output. Remote provider smoke, CI, merge and deployment are separate facts.

## Local combined verification (2026-09-27)

- Full backend discovery: 5,271 passed, 1 skipped, 4 expected failures (isolated SQLite).
- Maintained regression and coverage gate: 772 passed; total backend line coverage 50.02% (gate 34%).
- Complete frontend Jest: 126 suites / 2,234 tests passed.
- Production frontend build and core browser acceptance: 331 passed, 1 skipped; no provider secrets used.
- Strict Python gate, TypeScript check, generated OpenAPI synchronization and diff whitespace checks passed.
- Independent reviews found and resolved context loss, recovery outcome misclassification, frontend/server schema mismatch, wrapped exception classification, browser expansion race and credential-bearing smoke traces.
- Remote CI and protected provider smoke are tracked on PR #386 separately; local deterministic tests do not establish provider acceptance.
