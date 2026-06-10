# Tasks

## 1. Reproduce

- [x] 1.1 Inspect `ChatBar` rewrite SSE handling and confirm it repeats a static loading message.
- [x] 1.2 Add a failing ChatBar regression test for rewrite `status.message` progress updates.
- [x] 1.3 Verify the test fails before implementation because progress messages are not rendered.

## 2. Implement

- [x] 2.1 Map rewrite status phases/messages to user-visible progress text.
- [x] 2.2 Update loading toasts when status and reconnect events arrive.
- [x] 2.3 Render an `aria-live` progress line inside the rewrite sheet while rewriting.

## 3. Verify

- [x] 3.1 Run the focused rewrite progress test.
- [x] 3.2 Run the full ChatBar test suite.
- [x] 3.3 Run strict OpenSpec validation.
- [x] 3.4 Commit, push, and open a ready PR.
