## Context

`NarrativeManager` is explicitly stateless around a real `PlayerState`, but its
maintained coverage is only 4.96 percent. Storylines, established facts,
foreshadowing seeds, and habits control subsequent prompt context, so malformed
updates or incorrectly retained state can cause delayed gameplay regressions.

## Goals / Non-Goals

**Goals:**
- Cover representative state transitions with concrete `PlayerState` objects.
- Assert normalization, expiry, deduplication, recency ordering, and bounded
  collections at externally visible state boundaries.
- Keep all new tests deterministic and independent of AI, provider, database,
  random, time, or mock behavior.

**Non-Goals:**
- Change narrative transition rules, logging, prompt construction, or provider
  behavior.
- Test probabilistic foreshadowing activation, which needs control of random
  input and is deliberately outside this maintained batch.
- Promote the existing `test_game_core.py`, which contains unrelated mocks.

## Decisions

- Use a single focused test file with scenario-sized cases instead of copying
  the broad legacy suite. This preserves a readable regression map and avoids
  unrelated dependencies.
- Cover deterministic cleanup paths in `process_foreshadowing_seeds` rather
  than random activation selection. It validates both lifecycle integrity and
  metadata normalization without test doubles.
- Exercise the fact and habit limits with concrete, ordered state to verify the
  documented priority rules.
- Promote the file only after two clean local runs, then measure the full
  maintained selection twice before changing a floor.

## Risks / Trade-offs

- [Large fixture lists hide the contract] -> Keep list builders local and
  assert a small set of ordering and count invariants.
- [A behavior change is intentional] -> Assertions are based on current
  source-level state contracts and will be reviewed with any future rule
  change.
- [Coverage result is near an integer boundary] -> Retain the current 35
  percent floor unless two expanded runs prove 36 percent.
