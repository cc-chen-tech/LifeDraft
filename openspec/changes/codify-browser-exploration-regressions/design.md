## Context

The project already has a deep Playwright exploration script and several no-mock browser fixtures, but not every finding is represented in the faster maintained preflight gate. Browser exploration uncovered regressions around creation loading, opening/restored story text, retry duplication, history image identity, collection refresh, ChatBar click interception, rewrite/regenerate/session recovery, and music degradation.

## Goals / Non-Goals

**Goals:**
- Convert stable browser-agent findings into deterministic Jest/Playwright tests that run in maintained gates.
- Keep full deep exploration available for broad sweeps without making every PR depend on a 30-minute exploratory run.
- Make gate wiring itself testable so newly added regression tests are not accidentally left out.

**Non-Goals:**
- Rebuild the full browser-agent exploration framework.
- Require live external AI, music, or image providers for maintained gates.
- Fix every legacy backend test failure identified by full-suite exploration.

## Decisions

- Use fast frontend preflight tests for stateful browser findings when the browser failure maps cleanly to a store, hook, or component contract. This catches regressions earlier than full Playwright runs and avoids live-service flake.
- Use the existing `frontend/e2e/no-mock-regression.spec.ts` fixture for layout, pointer, and browser-only behaviors. This keeps click interception and fixture-driven UI checks in a real DOM browser.
- Add gate fidelity checks for browser regression files to the existing backend gate test rather than relying on comments in `test.sh`.
- Keep the deep `story101-exploration.spec.ts` as an explicit browser sweep and require `test.sh e2e` to include it, but do not promote it into preflight.

## Risks / Trade-offs

- Some real browser regressions are approximated by deterministic fixtures rather than full production flows. Mitigation: require the original deep exploration script to remain wired into `test.sh e2e`.
- Adding many frontend preflight tests increases preflight runtime. Mitigation: target high-signal store/hook/component contracts and keep full Playwright sweeps in the e2e layer.
- Browser findings can become stale as UI changes. Mitigation: specs describe user-visible invariants, while tests use stable roles/test IDs where available.
