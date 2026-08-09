## Context

Both existing suites run deterministically without doubles and assert FAST, EXPERT, and MASTER policy values.

## Goals / Non-Goals

**Goals:** promote existing contracts and preserve symmetric workflow selection.

**Non-Goals:** change profile policy or test bodies.

## Decisions

- Reuse verified tests and retain evidence-based floor ratcheting.

## Risks / Trade-offs

- [Gate time] -> pure configuration tests complete in milliseconds.
