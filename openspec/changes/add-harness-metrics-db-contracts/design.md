## Context

HarnessMetrics owns a standalone SQLite schema for observable generation
results. The persistence and reports are deterministic with a `tmp_path`
database, so they can be tested without clock control, provider calls, or
mocking.

## Goals / Non-Goals

**Goals:** verify run/check persistence, aggregate pass rates, retry counts,
failure evidence, and report status tiers.

**Non-Goals:** alter schema, simulate SQLite failures, or invoke generation.

## Decisions

- Use an explicit temporary database per test and record fixed input data.
- Test query outputs, not SQL implementation details.
- Include a no-data report to preserve empty-install behavior.

## Risks / Trade-offs

- [Timestamp ordering is implementation-controlled] → Assert aggregates and
  content, not precise insertion ordering.
