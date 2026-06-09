## Why

The runtime player resource numbers (`精力`, `情绪`, `学识`, `财富`) do not help gameplay decisions and add noise to the story experience. They should be hidden from the frontend while preserving the underlying state fields for compatibility.

## What Changes

- Remove runtime 4D resource metric rendering from the game status bar.
- Hide resource-only choice impact cards so choices do not expose raw resource deltas.
- Remove final numeric resource stats from the ending page.
- Remove resource curves from the life review card.
- Update frontend unit and browser E2E tests to reject visible runtime resource metrics.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `gameplay-side-controls`: Runtime side/header controls must not display numeric player resource metrics.
- `gameplay-continuity`: Ending and review surfaces must preserve story continuity without exposing raw resource-score summaries.

## Impact

- Affected frontend components: `StatusBar`, `ChoiceImpactDisplay`, `EndingPage`, and `LifeReviewCard`.
- Affected frontend tests and E2E specs that previously asserted resource metric visibility.
- No API schema or persistence changes; `energy`, `mood`, `knowledge`, and `wealth` remain available as internal state.
