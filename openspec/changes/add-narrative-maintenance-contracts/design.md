## Context

NarrativeManager updates persistent PlayerState structures after each round. Overdue flags control which storylines generation must address, while habit transitions govern character continuity. Both paths are pure, deterministic state transitions.

## Goals / Non-Goals

**Goals:**
- Protect escalation thresholds, idempotence, and importance filtering.
- Protect habit downgrade, disappearance, explicit deletion, and replacement semantics.
- Keep all test inputs as concrete PlayerState records.

**Non-Goals:**
- Exercise probabilistic foreshadowing selection or change NarrativeManager behavior.
- Alter existing legacy tests, prompt construction, or external providers.

## Decisions

- Represent state with real PlayerState instances and dictionaries matching persisted shape.
- Combine related lifecycle operations in each test only when their end states remain independently asserted.
- Keep historical mock-based tests untouched; this new module is self-contained and admitted to the maintained gate.

## Risks / Trade-offs

- [Transition tests can become coupled to record shape] → Assert only fields owned by each transition.
- [Boundary wording can change] → Use current threshold behavior as a precise state contract, independent of logs.
