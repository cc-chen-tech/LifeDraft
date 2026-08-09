## Context

SummaryGenerator receives model text but deterministically parses and normalizes summaries, world updates, and weekly bonus effects after a response is present.

## Goals / Non-Goals

**Goals:** gate summary cleanup, structured update preservation, absent-category defaults, and bonus bounds.

**Non-Goals:** perform network calls, exercise provider retry timing, or change summary behavior.

## Decisions

- Use a minimal deterministic local client that returns supplied response strings.
- Assert returned domain data rather than generated prompt wording.

## Risks / Trade-offs

- [Workflow drift] -> validate ordered workflow parity and the full maintained gate.
