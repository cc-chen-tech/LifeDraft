## 1. Tests

- [x] Update `frontend/src/__tests__/components/ChatBar.test.tsx` so the collapsed "人生总结" action expects a dedicated summary panel and no chat assistant panel/input.
- [x] Verify the new/updated test fails before production code changes.

## 2. Fix

- [x] Update `ChatBar` summary handling to use summary-specific state and render `life-summary-panel`.
- [x] Ensure collapsed and expanded summary actions do not append the summary to chat history or open the assistant input.

## 3. Verify

- [x] Run `openspec validate fix-life-summary-button-behavior --strict`.
- [x] Run targeted `ChatBar` Jest tests.
- [x] Run `./test.sh preflight` so the updated frontend regression is included in the shared gate.
- [x] Run `./test.sh all` so mypy, imports, contract, real DB, and E2E browser layers all pass.
