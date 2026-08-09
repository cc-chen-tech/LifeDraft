## Context

The four selected suites provide deterministic, in-process coverage of creative narrative helper modules and completed `40` tests in isolation.

## Goals / Non-Goals

**Goals:** add these regressions to maintained release validation.

**Non-Goals:** change production narrative behavior or call external AI services.

## Decisions

- Promote the modules together because they form the creative narrative layer.
- Retain existing test bodies and verify the full maintained workflow before commit.

## Risks / Trade-offs

- [Workflow drift] → Compare ordered lists.
- [Unexpected suite interaction] → Run the complete maintained gate.
