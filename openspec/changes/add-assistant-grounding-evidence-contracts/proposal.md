## Why

The read-only assistant determines which in-game facts may be presented as
authoritative, but its current regression tests rely on mocks and are not part
of the maintained backend gate. That leaves evidence-capacity, serialization,
and rejection paths vulnerable to field or validation regressions.

## What Changes

- Add deterministic, no-mock contracts for evidence construction and assistant
  answer validation using real state-shaped data.
- Exercise authoritative record retention at the evidence limit, optional
  record serialization, unknown-person handling, and rejected response paths.
- Add the new contract suite to both maintained backend workflow lists in the
  same order.

## Capabilities

### New Capabilities
- `assistant-grounding-evidence-contracts`: Maintained contracts proving that
  the assistant only returns answers supported by retained structured evidence.

### Modified Capabilities

None.

## Impact

- Adds `tests/test_assistant_grounding_evidence_contracts.py`.
- Updates `.github/workflows/coverage.yml` and
  `.github/workflows/backend-tests.yml` only to run the new suite.
- Does not change production behavior, external APIs, or dependencies.
