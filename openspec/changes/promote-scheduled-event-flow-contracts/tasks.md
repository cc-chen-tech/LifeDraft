## 1. Qualify Existing Flow

- [x] 1.1 Verify the scheduled-event flow suite has no framework mocks, skips, external calls, or environment mutation.
- [x] 1.2 Run the suite twice and measure direct coverage across scheduled events, PlayerState, and Commitment paths.

## 2. Maintain Gate Selection

- [x] 2.1 Add the scheduled-event flow suite to the maintained coverage workflow.
- [x] 2.2 Add the same suite in the same position to the maintained backend test workflow.

## 3. Verify and Record

- [x] 3.1 Verify workflow path-list parity and strict OpenSpec validity.
- [x] 3.2 Run the expanded maintained coverage suite and raise the floor only when measurement supports it.
