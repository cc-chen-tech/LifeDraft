## 1. Regression Coverage

- [x] 1.1 Add a no-mock real DB integration test for duplicate `choice-sync`.
- [x] 1.2 Add a no-mock real DB integration test for duplicate `custom-choice-sync`.
- [x] 1.3 Run the new tests before implementation and confirm they fail on `choice_already_processed`.

## 2. Implementation

- [x] 2.1 Detect the existing `choice_already_processed` restore error in sync fallback endpoints.
- [x] 2.2 Reconstruct the latest persisted choice result from saved `round_history`.
- [x] 2.3 Keep existing error behavior when no usable saved result exists.

## 3. Verification

- [x] 3.1 Run the focused new real DB tests.
- [x] 3.2 Run `openspec validate fix-choice-sync-idempotency --strict`.
- [x] 3.3 Run `./test.sh all`.
