## 1. Reproduction And Test Coverage

- [x] 1.1 Reproduce the history review readability issue locally or with component tests.
- [x] 1.2 Add a failing test that closing the history sidebar does not exit selected history reading.
- [x] 1.3 Add a failing test that history reading renders in a dedicated unobstructed surface.
- [x] 1.4 Add a failing test that production story voice controls hide raw debug fields and disabled TTS actions.

## 2. Implementation

- [x] 2.1 Keep history mode pinned when the drawer closes; exit only through return-to-current.
- [x] 2.2 Render a dedicated history reading surface before historical image controls and away from current-round actions.
- [x] 2.3 Redesign story voice controls into a polished preview/unavailable panel by default.
- [x] 2.4 Keep diagnostic controls available only through `showTestControls`.

## 3. Verification And Delivery

- [x] 3.1 Run targeted frontend tests for history and story voice controls.
- [x] 3.2 Run OpenSpec strict validation for this change.
- [x] 3.3 Run local browser-agent verification on the relevant gameplay/regression route.
- [x] 3.4 Run the appropriate local gate before commit.
- [ ] 3.5 Perform code review, commit, push, and open/update GitHub PR.
