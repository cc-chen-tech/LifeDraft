## 1. Tests

- [x] Add a prompt contract requiring 80% preset relationship network authority for multi-person scenes.
- [x] Add a quick-validator regression for partial preset-cast mention plus outside named-cast takeover.
- [x] Add a quick-validator regression proving family-only stories cannot satisfy preset key-people authority.

## 2. Implementation

- [x] Update preset-cast prompt constraints.
- [x] Update quick validation for outside named-network dominance.
- [x] Make quick validation distinguish required `relationships.key_people` from broader available people such as family members.

## 3. Verification

- [x] Run preset cast authority contract tests.
- [x] Run related story continuation, era drift, and round-event retry tests.
- [x] Run OpenSpec strict validation for this change.
