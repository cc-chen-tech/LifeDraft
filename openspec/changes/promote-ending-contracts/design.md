## Context

The existing suite runs EndingEvaluator from real PlayerState data and covers
classification, output structure, and language templates.

## Goals / Non-Goals

**Goals:** preserve user-visible ending outcomes in the maintained gate.

**Non-Goals:** modify test or production behavior.

## Decisions

- Promote the verified suite unchanged and preserve ordered workflow parity.

## Risks / Trade-offs

- [It depends on current life review composition] → that composition is local
  and already included in the maintained suite.
