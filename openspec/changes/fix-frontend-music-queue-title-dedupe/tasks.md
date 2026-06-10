## 1. Tests

- [x] Add a frontend music store regression test for reported duplicate title families.
- [x] Verify the test fails before the frontend queue policy change.

## 2. Fix

- [x] Add frontend title-family normalization consistent with the backend playlist policy.
- [x] Apply title-family dedupe in optimistic playlist merge and empty-playlist queue setup.

## 3. Verify

- [x] Run targeted frontend music queue policy tests.
- [x] Run frontend type checks.
- [x] Run OpenSpec validation.
