## 1. Regression Coverage

- [x] 1.1 Add a PlayPage regression test that submits inline rewrite through SSE complete.
- [x] 1.2 Confirm the test fails before implementation because `currentEvent.story` remains old.

## 2. Implementation

- [x] 2.1 Update PlayPage `onRewriteComplete` handling to set visible story text.
- [x] 2.2 Update PlayPage `onRewriteComplete` handling to replace `currentEvent.story` while preserving options.

## 3. Verification

- [x] 3.1 Run the targeted PlayPage rewrite regression test.
- [x] 3.2 Run relevant ChatBar/PlayPage rewrite tests.
- [x] 3.3 Run `openspec validate fix-inline-rewrite-current-event-sync --strict`.
- [x] 3.4 Run `./test.sh preflight`.
