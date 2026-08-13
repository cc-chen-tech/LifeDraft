## 1. High-Risk Local Contracts

- [x] 1.1 Add fallback round-event context tests for Chinese, English, and
  context-free states without an AI generator.
- [x] 1.2 Add gameplay event protocol tests for connection limits, saved-view
  acknowledgement, and Last-Event-ID input validation.
- [x] 1.3 Add item and landmark extraction parser tests for valid, malformed,
  and normalized model output.
- [x] 1.4 Add local music-library metadata compatibility and negative-cue
  tests without a provider or database.

## 2. Stable Gate Promotion

- [x] 2.1 Run every new contract suite twice in the maintained environment.
- [x] 2.2 Add only twice-stable files to both maintained workflows in the same
  order.
- [x] 2.3 Run the expanded maintained selection twice with `--cov=src` and
  retain or raise an integer floor only when both results prove it.

## 3. Verification

- [x] 3.1 Record coverage deltas and remaining full-backend 70 percent gap.
- [x] 3.2 Validate OpenSpec, workflow parity, and the scoped diff.
- [x] 3.3 Commit only new tests, workflow selection, and OpenSpec artifacts.
