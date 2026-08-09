## Context

The world-model updater accepts AI-derived structured fields but also owns
deterministic safety checks. Existing maintained contracts cover successful
reconciliation; legacy mock-based tests cover some guard branches outside the
gate.

## Goals / Non-Goals

**Goals:**
- Exercise omitted-field rejection and no-op guards with a real `PlayerState`.
- Exercise scheduled-event cleanup and preset-role protection without an AI
  client, provider, or mock.
- Keep both maintained workflow lists identical.

**Non-Goals:**
- Change the updater, player state, API behavior, or legacy tests.
- Exercise AI extraction and profile-synthesis paths.

## Decisions

- Use direct static-method calls with `PlayerState` because the targeted paths
  are deterministic in-memory state transitions.
- Assert observable state rather than logger output or implementation calls.
- Register the new module in both workflow lists at the existing world-model
  test group to preserve gate parity.

## Risks / Trade-offs

- [Iteration order of relationship effects] -> Each assertion identifies one
  named relationship instead of asserting insertion order.
- [AI-dependent code remains uncovered] -> This batch intentionally covers
  only deterministic guard behavior and leaves provider behavior to separate
  integration contracts.
