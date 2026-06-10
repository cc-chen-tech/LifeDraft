## 1. Tests

- [x] Add a round-event regression test where quick validation fails twice.
- [x] Verify the test fails because fallback omits all preset key people.

## 2. Fix

- [x] Read canonical preset key people in the round fallback builder.
- [x] Include one preset key person in fallback text without inventing new named people.

## 3. Verify

- [x] Run targeted round-event retry tests.
- [x] Run related cast authority tests.
- [x] Run OpenSpec validation.
