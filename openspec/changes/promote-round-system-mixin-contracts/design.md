## Context

The existing 38-test contract exercises real `RoundSystemMixin` initialization, current-event delegation, helper signatures, and invalid-entry behavior without provider access or framework mocks.

## Goals / Non-Goals

**Goals:** Promote this deterministic orchestration contract in both maintained workflows.

**Non-Goals:** Change gameplay behavior or add mocks, skips, random input, external network access, or environment mutation.

## Decisions

- Append the existing contract to both identical workflow selections.
- Only raise the coverage threshold after a strict full-suite candidate passes.

## Risks / Trade-offs

- [Method existence tests can be shallow] -> This file also exercises initialization and state delegation paths.
