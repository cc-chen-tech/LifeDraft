## Context

The tests construct `GameLoop` with an explicit no-behavior AI stub and invoke the real `load_game` method. No provider calls occur.

## Goals / Non-Goals

**Goals:** Cover valid, stale, and partial saved event recovery in maintained workflows.

**Non-Goals:** Change recovery behavior or use framework mocks, skips, random input, environment mutation, or external network access.

## Decisions

- Use a minimal handwritten AI stub only to satisfy the provider boundary during construction.
- Raise the threshold only after a strict full-suite candidate passes.

## Risks / Trade-offs

- [Constructor dependencies evolve] -> The stub has no behavior and keeps tests focused on persisted state recovery.
