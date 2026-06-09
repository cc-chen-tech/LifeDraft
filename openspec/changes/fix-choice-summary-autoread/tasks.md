## 1. Reproduction And Test Coverage

- [x] 1.1 Trace choice completion flow and confirm weekly summary uses `phase: "summary"`.
- [x] 1.2 Add a failing PlayPage regression test for auto-reading the completed choice story before weekly summary.
- [x] 1.3 Verify the new test fails because `activeAutoReadReady` remains false.

## 2. Implementation

- [x] 2.1 Include `summary` in completed-story media readiness.
- [x] 2.2 Preserve the current-story reading context and completed story text during summary.
- [x] 2.3 Treat `summary` as result-stage media for scene image fetching and refresh controls.

## 3. Verification And Delivery

- [x] 3.1 Run the new focused regression test.
- [x] 3.2 Run the related PlayPage and StoryVoiceControls test suites.
- [x] 3.3 Run TypeScript checking for the frontend.
- [x] 3.4 Run OpenSpec strict validation for this change.
- [x] 3.5 Commit, push, and open a ready PR.
