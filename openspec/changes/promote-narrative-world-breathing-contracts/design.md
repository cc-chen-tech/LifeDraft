## Context

The existing test executes WorldBreathingEngine entirely in memory, covering its event calendar, weekly advancement, information propagation, event typing, and style degradation rules.

## Goals / Non-Goals

**Goals:** Promote deterministic world-state contracts in both maintained workflows.

**Non-Goals:** Change narrative behavior or use mocks, skips, random input, environment mutation, or network access.

## Decisions

- Append the existing stable contract to both identical selections.

## Risks / Trade-offs

- [Standalone engine coverage] -> It protects deterministic world-state rules independently of AI generation.
