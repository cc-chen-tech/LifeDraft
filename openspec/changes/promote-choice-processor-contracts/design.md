## Context

`RoundChoiceProcessor` applies player-visible resource and wealth transitions.
The maintained gate currently exercises only a small portion of those paths.
The existing broad suite has a contract test with hand-written fakes, but it is
not appropriate to promote unchanged under the gate's strict static policy.

## Goals / Non-Goals

**Goals:**
- Cover resource clamping and wealth transaction state changes through public
  state objects and the real `WealthLedger`.
- Keep tests deterministic, provider-free, database-free, and mock-free.
- Add the focused test file to both maintained workflow selections in the same
  order.

**Non-Goals:**
- Changing choice processing, wealth semantics, or existing tests.
- Exercising AI story generation or the full asynchronous post-choice pipeline.

## Decisions

- Exercise the processor's state helpers with a real `PlayerState` and real
  `WealthLedger`. This isolates the deterministic business rules without
  pretending an AI provider is available.
- Use one test for clamping at lower/upper resource bounds and one test for
  idempotent wealth transaction persistence plus invalid requested input. The
  paired cases cover the state invariants with small, readable setup.
- Include the new file only after two focused runs and two complete maintained
  runs agree. Raise the threshold only if the measured exact percentage clears
  the next integer floor.

## Risks / Trade-offs

- [Internal helper coverage may couple to implementation] -> Assertions target
  persisted state and returned contract data rather than local implementation
  details.
- [Coverage gain is smaller than a provider-backed integration path] -> The
  selected paths are deterministic and guard resource/wealth regressions that
  would otherwise reach gameplay or browser testing late.
- [Workflow drift] -> Compare the backend and coverage test selections before
  commit.
