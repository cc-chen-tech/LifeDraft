## Context

StoryAnalyzer turns model JSON into persisted dynamic facts and scheduled commitments. The parsing layer is deterministic once a response is supplied.

## Goals / Non-Goals

**Goals:** gate fact ID de-duplication, replacement provenance, invalidation, and actionable scheduled commitment filtering.

**Non-Goals:** invoke a model client or alter analysis behavior.

## Decisions

- Pass JSON response strings directly to the parser methods using a concrete unused `None` client.
- Assert structured returned records rather than logs or prompt text.

## Risks / Trade-offs

- [Workflow drift] -> validate ordered workflow parity and the full maintained gate.
