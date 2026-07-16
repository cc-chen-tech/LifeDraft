## Why

The July 14 production playthrough persisted fabricated people such as `周建国` and lexical fragments such as `周初` and `元减`. The same playthrough displayed a valid Monday state as `第0轮`, so the UI exposes an internal zero-based index as a player-facing round number.

## What Changes

- Require smart-recognition character candidates to be explicit names supported by character settings or by an exact story mention; reject phase labels, numeric fragments, and inferred full names.
- Preserve honorific-only people such as `周师傅` instead of inventing an unsupported personal name.
- Define a player-facing scene-image round label for zero-based round indices.
- Add backend and frontend regression tests using the production failure examples.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `collection-recognition-gating`: Recognized people must have an authoritative source and must not be fabricated from role titles or lexical fragments.
- `gameplay-continuity`: Current gameplay round information must render a human-facing one-based round label while retaining zero-based internal state.

## Impact

- `src/services/entity_recognition_service.py` and `src/api/routers/collection.py` candidate filtering and persistence input.
- `frontend/src/components/game/StatusBar.tsx` and its component tests.
- Backend collection-recognition tests and frontend status-display tests.
