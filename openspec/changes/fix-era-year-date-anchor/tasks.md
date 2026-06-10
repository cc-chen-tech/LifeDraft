## 1. Reproduction And Test Coverage

- [x] 1.1 Reproduce the 2026-to-2024 drift with a player state whose era text
      contains 2026 but lacks `era.year`.
- [x] 1.2 Add a failing regression test for `get_game_date_info`.

## 2. Implementation

- [x] 2.1 Parse a valid start year from `era.year` when it is numeric or a
      string.
- [x] 2.2 Parse a valid start year from `era_name`, `era_description`, and
      `world_context` when `era.year` is missing.
- [x] 2.3 Preserve the existing 2024 fallback when no explicit year is stored.

## 3. Verification

- [x] 3.1 Run the focused date-info regression tests.
- [x] 3.2 Run OpenSpec strict validation.
- [x] 3.3 Commit, push, and open a ready PR.
