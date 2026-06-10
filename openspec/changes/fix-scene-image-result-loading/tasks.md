## 1. Reproduction And Test Coverage

- [x] 1.1 Trace current gameplay scene-image rendering for options/result/summary phases.
- [x] 1.2 Add a failing regression test for result-stage loading with a stale event illustration present.
- [x] 1.3 Confirm the regression test fails before the display policy exists.

## 2. Implementation

- [x] 2.1 Add a focused scene-image display policy helper.
- [x] 2.2 Use the policy from the play page rendering path.
- [x] 2.3 Render a result loading placeholder instead of stale event fallback while result image loading is active.

## 3. Verification And Delivery

- [x] 3.1 Run focused scene-image frontend tests.
- [x] 3.2 Run frontend type checking.
- [x] 3.3 Run OpenSpec strict validation for this change.
- [x] 3.4 Commit, push, and open a ready PR.
