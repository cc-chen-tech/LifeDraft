## Context

Terminal SSE helpers work entirely from an in-memory event operation and GameEvent values.

## Goals / Non-Goals
**Goals:** Gate completion, failure, timeout, replay, and pool lifecycle behavior without a provider.
**Non-Goals:** Start event-generation workers or modify production code.

## Decisions
- Use real EventGenerationOperation and GameEvent objects with zero-time terminal checks.
- Add the existing no-mock thread-pool lifecycle suite in the same batch.

## Risks / Trade-offs
- [Timeout tests race] -> Use a zero timeout against an operation intentionally left running.
