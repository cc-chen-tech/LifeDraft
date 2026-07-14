## Why

`NarrativeManager` owns storyline, world-fact, foreshadowing, and habit state
transitions, but the maintained gate currently covers only 4.96 percent of its
363 statements. The existing broad game-core suite mixes unrelated mock-based
tests, leaving these deterministic transitions absent from the maintained
regression boundary.

## What Changes

- Add provider-free `PlayerState` contracts for storyline expiry, fact
  replacement and trimming, foreshadowing cleanup and normalization, and habit
  strength and per-character limits.
- Promote only the new deterministic contract suite after two independent
  passes.
- Keep maintained backend workflow lists aligned and advance the coverage floor
  only when repeatable measurements prove the next integer.

## Capabilities

### New Capabilities
- `narrative-state-contract-coverage`: Deterministic regression contracts for
  narrative state transitions that affect future gameplay prompts and history.

### Modified Capabilities
- `test-gates`: The maintained backend workflows include the twice-verified
  narrative-state contract suite in the same order.

## Impact

- Adds a focused test file for `src/game/narrative_manager.py`.
- Updates only maintained test selection and coverage threshold if evidence
  supports it.
- Does not change production code or existing tests.
