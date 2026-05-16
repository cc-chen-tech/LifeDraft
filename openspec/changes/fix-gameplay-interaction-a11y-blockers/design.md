## Context

The exploration report describes a successful registration and character creation flow followed by a gameplay blocker: a bottom fixed mini control captured pointer events across the story choice area. The report also identifies several accessibility and UX inconsistencies: unlabeled character creation step dots, choice buttons whose names are hard for automation to detect, an unclear disabled portrait-step action, and registration focus.

The current frontend already uses browser E2E through Playwright and `test.sh` already models the requested five-layer pipeline. This change should stay small and avoid introducing mocks or skipped tests for the new coverage.

## Goals / Non-Goals

**Goals:**

- Guarantee that collapsed bottom controls cannot intercept clicks outside their visible control.
- Make key interactive controls discoverable by role/name in browser automation and assistive technology.
- Make the portrait step state clear while image generation is pending and consistent once ready.
- Add focused no-mock browser regression coverage and wire it into `test.sh`.
- Keep `test.sh all` green across static analysis, import validation, contract tests, real DB tests, and E2E.

**Non-Goals:**

- Redesign the music player UI or the full gameplay screen.
- Replace the existing frontend test stack.
- Fix unrelated full-repository strict mypy debt in backend modules not touched by this frontend interaction fix.
- Implement or rerun the one-hour exploratory journey itself.

## Decisions

1. Use browser-level E2E for the regression.
   - Rationale: the reported blocker is a real pointer-event/DOM accessibility issue, so role/name queries and browser-rendered class assertions catch it more reliably than unit tests.
   - Alternative considered: Jest component tests. Rejected for this change because the current Jest setup contains global mocks and the user explicitly required no mock tests.

2. Add explicit accessible names at the component source.
   - Rationale: `aria-label` on the actual buttons gives stable producer/consumer contracts for automation and assistive technology without depending on nested text layout.
   - Alternative considered: restructure button child text. Rejected because it is more invasive and does not guarantee stable names for icon-only controls.

3. Make the collapsed bottom launcher container pointer-transparent.
   - Rationale: `pointer-events-none` on the fixed container plus `pointer-events-auto` on the visible button prevents invisible overlay hitboxes while preserving the launcher.
   - Alternative considered: lower z-index. Rejected because z-index changes are fragile when other bottom surfaces are present.

4. Initialize real DB schema in the DB test layer.
   - Rationale: real DB tests should run against a database with production tables; a clean local SQLite file otherwise fails before exercising save/read behavior.
   - Alternative considered: modifying DB tests to create tables. Rejected because centralizing the setup in `test.sh` keeps the layer self-contained.

## Risks / Trade-offs

- [Risk] A test-only regression route could be reachable in development builds. → Mitigation: the route contains only local UI fixtures, no secrets, no network side effects, and exists solely to mount real components without mocks.
- [Risk] Full `mypy --strict` still fails on unrelated backend typing debt. → Mitigation: document this explicitly; keep current configured mypy layer green and avoid adding backend Python code in this change.
- [Risk] Pointer-event fixes could make a launcher unclickable if applied to both parent and child. → Mitigation: E2E asserts the parent is pointer-transparent and the button remains pointer-active.
