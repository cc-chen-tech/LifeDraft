## Context

Persisted field semantics are a high-risk frontend/backend contract boundary.
The style-restore suite uses real in-process `GameLoop` loading with
deterministic state dictionaries, and checks present, omitted, null, and empty
`narrative_style_id` values without mock frameworks or external providers.

## Goals / Non-Goals

**Goals:**
- Promote the existing restore contract suite into the maintained workflow pair.
- Preserve ordered workflow-list parity.
- Run an exact 51% candidate gate after verifying the current threshold.

**Non-Goals:**
- Change restoration semantics, sources, or existing tests.
- Add database/provider integration requirements to this unit-level gate.
- Raise the threshold without a real successful full command.

## Decisions

- Promote the whole existing file because it explicitly covers persisted-field
  compatibility and constructor-to-load behavior, unlike simple import tests.
- Append it after the related narrative style suites in both lists.
- Perform threshold promotion as an independently verified workflow edit only
  if `--cov-fail-under=51` succeeds.

## Risks / Trade-offs

- [A concrete generator setup acquires external behavior] → The direct suite is
  executed before promotion and must remain local and deterministic.
- [State restoration is too narrow] → The suite is used as a field contract;
  broader GameLoop recovery remains covered by the existing maintained suite.
- [51% is not met] → Preserve 50% and continue promotion with another scoped
  high-value contract.
