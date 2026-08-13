## Context

The contract exercises relationship event lookups, thresholds, requirements, categories, and era normalization entirely in memory.

## Goals / Non-Goals

**Goals:** Promote the deterministic 31-test contract in both maintained workflows.

**Non-Goals:** Change event definitions or use mocks, skips, random input, environment mutation, or external network access.

## Decisions

- Append the existing contract to both identical selections and retain the current threshold unless a strict candidate passes.

## Risks / Trade-offs

- [Definition coverage is small in absolute lines] -> It protects a high-value state-machine specification at negligible runtime cost.
