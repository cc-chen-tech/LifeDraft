## 1. Reproduction And Test Coverage

- [x] 1.1 Trace story voice settings loading and local voice selection flow.
- [x] 1.2 Add a failing regression test where a stale settings response arrives after local voice selection.
- [x] 1.3 Confirm the failing test shows the stale server voice is used for the next reading request.

## 2. Implementation

- [x] 2.1 Record local user voice changes before persisting them.
- [x] 2.2 Ignore late `selected_voice_color` settings values after local voice changes.
- [x] 2.3 Keep existing mid-playback voice restart behavior unchanged.

## 3. Verification And Delivery

- [x] 3.1 Run the focused voice-selection race regression test.
- [x] 3.2 Run the full StoryVoiceControls test suite.
- [x] 3.3 Run frontend TypeScript checking.
- [x] 3.4 Run OpenSpec strict validation for this change.
- [x] 3.5 Commit, push, and open a ready PR.
