# Scheduled E2E repair plan (consolidated)

Source: PR #392 / `73d458c`; integration and final verification: PR #393. Checked items below describe the completed original diagnosis; final full-matrix acceptance is separately recorded in PR #393.

> Implementation: execute inline with systematic debugging and test-first verification.

**Goal:** Explain and repair the seven repeat failures at e73fdc5dd8 without bypassing production validation or weakening observable behavior.

**Architecture:** Correct deterministic provider inputs and obsolete test setup first. Change product behavior only after a focused reproduction proves a defect. Keep actual media decoding, transport recovery, saved state, and narrative validation in coverage.

**Tech stack:** Python/FastAPI, React/Next.js, pytest/Jest/Playwright.

**Spec:** User request: investigate Actions runs 40779269260 and 40590899820, preserve features and test coverage, add regressions and verify.

## Tasks

- [x] Compare both jobs and retries; inspect Oct 28 trace network and console evidence.
- [x] Add provider regression using the real expert daily length validator; observe failure before correcting fixture prose.
- [x] Repair long-story setup and assert real rendered story against persisted API content.
- [x] Give the ancient test an explicit historical origin and era-compatible deterministic story; assert saved year and actual visible prose.
- [x] Exercise real SSE transport failure/reconnect/polling and visible restored options; preserve terminal business-error coverage.
- [x] Reproduce delayed audio readiness in WebKit; distinguish autoplay policy, event races, and player bugs. Preserve actual progress and add explicit Range-response checks independent of browser request strategy.
- [x] Run focused regressions, type checks, affected suites; document any environment limits and remaining failures.

## Review focus

Provider-disabled behavior must stay unchanged. Historical fixtures must not silently become modern. A homepage/header must not count as a playable game. Recovery assertions must distinguish terminal failure from recoverable transport failure. Audio assertions must prove advancing playback, including after the real polling deadline, without assuming all browser engines issue Range headers.

## Results

See `bug_fix_log/2026-10-29-scheduled-e2e-root-causes.md` for evidence, verification, and remaining full-matrix limits.

## Consolidation follow-through

Retain PR #393 exact known-story judge guard and narrative_budget API. Preserve unique explicit browser-fixture Range coverage from PR #392. Establish a fresh absent progress record explicitly, save and read a nonzero checkpoint through the real API, then require exact persistence across history/save/reload under unfiltered HTTP error monitoring. Negative regressions must reject missing or reset saved progress. Verify the integrated commit in full Actions, retaining unrelated flake evidence. Never merge or deploy as part of this plan.
