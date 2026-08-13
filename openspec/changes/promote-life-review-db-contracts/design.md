## Context

The existing suite exercises LifeReviewGenerator with real PlayerState and
Achievement values, including the ending evaluator handoff. It does not call a
provider or use mocks.

## Goals / Non-Goals

**Goals:** preserve life-review shape, resource curves, labels, and end-game
summary behavior in maintained coverage.

**Non-Goals:** change the suite or production behavior.

## Decisions

- Promote the existing verified test unchanged to avoid duplicate test logic.
- Keep workflow order identical in both maintained jobs.

## Risks / Trade-offs

- [The suite includes end-game composition] → It remains local and completed in
  under a second when isolated.
