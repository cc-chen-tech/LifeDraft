## 1. Reproduction And Test Coverage

- [x] 1.1 Trace the automatic read effect and confirm it did not check voice settings readiness.
- [x] 1.2 Add a failing regression test where `autoReadReady` is true while `/voice-reading/settings` is still pending.
- [x] 1.3 Confirm the failing test shows `/voice-reading/read` is called too early.

## 2. Implementation

- [x] 2.1 Gate the automatic read effect on voice settings readiness.
- [x] 2.2 Preserve browser fallback and completed-choice auto-read behavior after settings load.

## 3. Verification And Delivery

- [x] 3.1 Run the focused regression test.
- [x] 3.2 Run the full StoryVoiceControls test suite.
- [x] 3.3 Run the related PlayPage auto-read tests.
- [x] 3.4 Run frontend TypeScript checking.
- [x] 3.5 Run OpenSpec strict validation for this change.
