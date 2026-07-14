## Context

The maintained backend workflows currently select 50 deterministic test files and enforce a 44 percent source coverage floor. The repository already has monthly and yearly summary contract suites that run without framework mocks, skips, network access, or provider credentials, but neither suite is selected by those workflows.

## Goals / Non-Goals

**Goals:**
- Include periodic summary contracts in the fast maintained backend gate.
- Verify equivalent ordered selections in the regular backend and coverage workflows.
- Measure the resulting maintained coverage before changing its threshold.

**Non-Goals:**
- Raise the maintained coverage threshold without evidence.
- Modify summary generation behavior or rewrite existing tests.
- Treat the maintained suite as a replacement for release-only full-suite validation.

## Decisions

- Promote both monthly and yearly suites together because they form a single periodic-summary boundary and use the same deterministic fake-provider pattern. Promoting only one would leave the adjacent annual aggregation path outside the gate.
- Append the two test paths at the end of both workflow selections in the same order. This preserves prior selection order and makes parity mechanically checkable.
- Retain the 44 percent coverage floor unless the expanded selection supports a higher integer floor. This keeps the gate evidence-based rather than treating test-count growth as proof of enough source coverage.

## Risks / Trade-offs

- [A hand-written fake drifts from the provider protocol] -> The suites assert the production-facing `generate_completion` calls and remain provider-free; higher-level provider integration stays in release validation.
- [Workflow lists diverge] -> Compare normalized path lists before committing.
- [Coverage growth is too small to raise the floor] -> Keep the existing floor and continue with higher-risk uncovered modules in a subsequent change.
