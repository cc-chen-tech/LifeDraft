## Context

The maintained backend gate has reached 50% coverage by selectively promoting
deterministic tests. `tests/test_narrative_conflict_tower.py` runs without
provider calls, filesystem dependence, mock frameworks, random data, or
environment mutation, and reaches 54% direct statement coverage of
`src.ai.narrative.conflict_tower`.

## Goals / Non-Goals

**Goals:**
- Include the existing deterministic suite in both maintained backend workflow
  selections.
- Preserve ordered parity between the coverage and backend-test selections.
- Verify the selection, suite, and maintained coverage threshold before
  committing.

**Non-Goals:**
- Alter existing test assertions or production behavior.
- Raise the maintained threshold unless the complete maintained run provides a
  sufficient measured margin.
- Make legacy suites or external-provider tests part of the gate.

## Decisions

- Promote the whole file rather than duplicate its assertions. The suite is
  already deterministic and covers the public `ConflictTower` state contract.
- Add the file in the same position in both workflow selections. Exact parity
  prevents the functional and coverage jobs from drifting apart.
- Keep the threshold at 50% unless the verified full maintained run proves a
  higher threshold. A narrow margin is not treated as a reliable gate increase.

## Risks / Trade-offs

- [A pre-existing test becomes flaky] → Run the file directly and in the full
  maintained selection under CI-like environment variables before commit.
- [Workflow selections drift] → Compare the parsed ordered file lists before
  commit.
- [Promotion adds little global coverage] → Record the direct module result and
  use it only when the global maintained result remains stable.
