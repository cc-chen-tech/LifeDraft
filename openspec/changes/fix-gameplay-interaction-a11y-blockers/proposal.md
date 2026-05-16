## Why

The deep Story101.live exploration found five interaction and accessibility issues that directly affect onboarding and gameplay progression. The most important blocker is a bottom fixed control surface intercepting pointer events above its visible button, preventing story choice buttons from advancing Week 1 and later rounds.

## What Changes

- Constrain collapsed bottom controls so only the visible launcher/button receives pointer events.
- Make gameplay choice buttons expose stable accessible names containing their ordinal and full choice text.
- Make the character creation step indicator expose accessible labels and current-step state.
- Clarify the portrait step action state: while image generation is pending, show an explicit waiting state; once a portrait exists, use the same "next step" navigation language as prior steps.
- Preserve registration sheet autofocus behavior with browser-level regression coverage.
- Add no-mock Playwright browser regression tests covering the reported blockers and wire them into `test.sh`.
- Ensure the real DB layer initializes its schema before running real database integration tests.

## Capabilities

### New Capabilities

- `gameplay-interaction-accessibility`: Browser-verifiable requirements for choice clickability, bottom fixed controls, accessible labels, onboarding focus, and character creation progress controls.

### Modified Capabilities

- None.

## Impact

- Frontend components: `ChatBar`, `OptionCards`, character creation page.
- Frontend E2E: add a focused no-mock Playwright regression covering the exploration findings.
- Test runner: `test.sh` runs the focused E2E regression and initializes the real DB schema before DB integration tests.
- Known constraint: full-repository `mypy --strict` currently fails on pre-existing backend typing debt unrelated to this frontend blocker fix; the existing `test.sh` mypy layer passes under the repository's current mypy configuration.
