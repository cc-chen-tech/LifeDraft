## Context

The existing contract is pure deterministic state input/output coverage with no mocks or dependencies.

## Goals / Non-Goals

**Goals:** Promote all language detection branches in both maintained workflows.

**Non-Goals:** Change language behavior or add mocks, skips, random input, environment mutation, or network access.

## Decisions

- Append the existing contract to both identical selections and raise the threshold only after a strict candidate passes.

## Risks / Trade-offs

- [Small source module] -> It protects a recovery prerequisite and closes its remaining coverage gap.
