## Context

The existing pure contract suite exercises style matching across ancient, modern, and cyberpunk settings and covers 86% of the matcher.

## Goals / Non-Goals

**Goals:** gate deterministic style-selection regressions.

**Non-Goals:** change style matching or add provider-backed tests.

## Decisions

- Promote only the deterministic suite; exclude the UUID-based integration suite.

## Risks / Trade-offs

- [Workflow drift] → compare ordered test lists and run the full gate.
