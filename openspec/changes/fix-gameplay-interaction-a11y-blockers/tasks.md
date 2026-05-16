## 1. Test Coverage

- [x] 1.1 Add no-mock Playwright coverage for registration autofocus, creation step labels, choice accessible names, and bottom launcher pointer-event constraints.
- [x] 1.2 Wire the no-mock browser regression into `test.sh` E2E layer without skips.
- [x] 1.3 Ensure `test.sh` DB layer initializes the real DB schema before running real save/read integration tests.

## 2. Implementation

- [x] 2.1 Constrain collapsed bottom assistant pointer events to the visible launcher button.
- [x] 2.2 Add stable accessible names for story option buttons and custom-choice submission.
- [x] 2.3 Add accessible names and current-step state to character creation step indicators.
- [x] 2.4 Clarify the portrait step primary action while waiting and after image generation is ready.

## 3. Verification

- [x] 3.1 Run TypeScript static checking.
- [x] 3.2 Run focused no-mock Playwright regression.
- [x] 3.3 Run `test.sh db`.
- [x] 3.4 Run `test.sh all` and confirm all five configured layers pass.
