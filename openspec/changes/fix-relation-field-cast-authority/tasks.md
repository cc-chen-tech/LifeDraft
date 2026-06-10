## 1. Tests

- [x] Add a failing contract test proving `relationships.key_people[].relation` is not included in required cast authority.
- [x] Add a failing prompt contract test proving available-people text renders relation-only people as empty-role labels.

## 2. Fix

- [x] Normalize `relation` into required cast role/relationship facts.
- [x] Use `relation` as a role label when formatting available people for prompts.
- [x] Deduplicate repeated role facts in required cast prompt text.

## 3. Verify

- [x] Run focused preset-cast authority tests.
- [x] Run related story continuation and gameplay behavior tests.
- [x] Run OpenSpec validation.
- [x] Run full `./test.sh preflight`.
