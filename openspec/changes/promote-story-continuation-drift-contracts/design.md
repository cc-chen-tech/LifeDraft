## Context

Story providers can return text that violates the configured era or introduces
unapproved people. The existing suite drives the real validators using
deterministic hand-written generators and verifies retry prompts and outputs.

## Goals / Non-Goals

**Goals:**
- Promote the provider-free regression suite unchanged.
- Verify gate parity and stable coverage before commit.

**Non-Goals:**
- Calling a provider, changing prompts, or modifying existing tests.

## Decisions

- Treat the hand-written generators as deterministic provider boundaries, not
  framework mocks; validators and StoryService execute normally.
- Do not raise a coverage threshold unless two complete maintained runs support
  the next integer.

## Risks / Trade-offs

- [Text rules can evolve] -> The tests assert current era/cast invariants that
  correspond to known production regressions.
