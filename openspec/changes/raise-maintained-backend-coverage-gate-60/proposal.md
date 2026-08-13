## Why

The maintained backend suite now has repeatable 62.81% statement coverage,
while its CI threshold is still 51%. The gate therefore permits a material
coverage regression despite the additional stable contracts already merged
into its test list.

## What Changes

- Raise the maintained backend coverage failure threshold from 51% to 60%.
- Keep the maintained test selection unchanged; legacy full-suite failures are
  not reclassified or silently ignored by this threshold change.

## Capabilities

### New Capabilities
- `maintained-backend-coverage-floor`: CI enforcement that maintains at least
  60% statements coverage for the curated stable backend suite.

### Modified Capabilities

None.

## Impact

- Updates only `.github/workflows/coverage.yml` and OpenSpec artifacts.
- No production API, database, dependency, or legacy-suite behavior changes.
