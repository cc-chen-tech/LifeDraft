## Why

The preset-cast validator turns a seven-person relationship network into a
six-of-seven requirement on every generated story. Normal focused rounds that
use four or five canonical people therefore emit `CAST_COVERAGE_LOW` and can
consume extra retry attempts even when no invented person has replaced a
preset role.

## What Changes

- Stop treating the aggregate preset-cast coverage ratio as a per-round warning
  or retry gate.
- Preserve hard validation for explicitly required people that are missing.
- Preserve hard validation when an invented named person takes over a preset
  relationship role or drives the story in place of the preset cast.
- Prevent places, items, organizations, titles, and ordinary nouns from being
  treated as named-person takeover evidence.
- Remove the global 80% relationship-network instruction from the shared cast
  authority prompt.
- Keep legacy parsing of historical `CAST_COVERAGE_LOW` messages.

## Capabilities

### New Capabilities

- `preset-cast-coverage-validation`: Defines non-blocking aggregate coverage and
  blocking explicit-cast/takeover validation behavior.

### Modified Capabilities

- None. The earlier completed cast-authority change remains historical; this
  change adds the corrected validation contract without rewriting that record.

## Impact

- Backend quick validation and shared relationship-authority prompt assembly.
- Retry behavior indirectly changes because coverage-only findings disappear.
- Tests and OpenSpec contracts only; no database, API, frontend, dependency, or
  feature-flag changes.
