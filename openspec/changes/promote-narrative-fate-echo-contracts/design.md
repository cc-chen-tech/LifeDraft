## Context

The existing test executes the real in-memory FateEchoDatabase lifecycle without mocks, providers, or external state.

## Goals / Non-Goals

**Goals:** Promote deterministic narrative causality coverage in both maintained workflows.

**Non-Goals:** Change narrative behavior or use mocks, skips, random input, environment mutation, or network access.

## Decisions

- Append the existing stable contract to both identical selections.

## Risks / Trade-offs

- [Isolated narrative engine coverage] -> It protects deterministic causality rules independently of AI generation.
