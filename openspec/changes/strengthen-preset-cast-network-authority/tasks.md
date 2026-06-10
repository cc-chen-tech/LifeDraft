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

## 4. 2026-06-11 Single Substitute Follow-up

- [x] Add a quick-validator regression where one preset person appears, two preset people are mentioned only as absent, and one invented strong-role character takes over mentor/investor/main-plot functions.
- [x] Treat preset names in absent/non-participating phrases as not satisfying preset-cast usage.
- [x] Reject a single invented strong-role substitute when the preset relationship network is underused.
- [x] Run targeted preset-cast, round-event retry, and gameplay behavior gate tests.
