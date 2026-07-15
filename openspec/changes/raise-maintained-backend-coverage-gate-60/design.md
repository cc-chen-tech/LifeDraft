## Context

The maintained backend workflow runs a curated, stable test selection that now
measures 62.81% coverage. Its current 51% threshold does not reflect this
baseline and does not protect the work already invested in high-risk contracts.

## Goals / Non-Goals

**Goals:**
- Require at least 60% coverage from the existing maintained suite.
- Preserve a measurable 2.81-point buffer below the verified baseline.

**Non-Goals:**
- Do not set a 70% backend threshold yet.
- Do not alter curated test selection or full-suite legacy failure handling.
- Do not add production code or external services.

## Decisions

- Raise the floor to 60%, not directly to 65% or 70%. This is below the
  verified baseline but high enough to prevent a meaningful regression.
- Change only the coverage workflow because the backend test workflow does not
  produce coverage data.
- Retain the test list and environment so the measured threshold has the same
  operational meaning as the existing gate.

## Risks / Trade-offs

- [Small headroom] → Keep the suite selection stable and only raise again after
  additional verified coverage batches.
- [Legacy failure confusion] → State explicitly that this gate remains the
  maintained selection, not a claim that the full suite is clean.

## Migration Plan

The workflow is additive in enforcement. Revert the single threshold value if
CI reveals an environment-specific coverage discrepancy.

## Open Questions

None.
