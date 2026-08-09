## Context

The choice processor state contracts cover bounded values and ledger writes,
but not its explicit unavailable-state fallback. That branch is deterministic
and requires no provider, database, or test double.

## Goals / Non-Goals

**Goals:**
- Verify the fallback returns an equal but independent effects mapping.
- Verify the fallback returns no resource warnings.
- Verify custom-choice effect generation supplies empty state context when
  player state is unavailable.
- Use measured coverage rather than rounding to decide a 43% gate raise.

**Non-Goals:**
- Changing choice processing or testing full choice generation.

## Decisions

- Reuse the maintained choice processor state test file so the related
  deterministic state contracts remain discoverable together.
- Assert both equality and object identity to prevent accidental caller-input
  mutation in recovery paths.
- Use a recording service object rather than a framework mock to verify the
  delegated request contract.

## Risks / Trade-offs

- [Small branch-specific test] -> The branch guards an explicit public safety
  fallback and is assessed with a full maintained run before threshold changes.
