## 1. Tests

- [x] Add E2E regression proving history and collection dialogs cannot remain open together.

## 2. Fix

- [x] Make the play page open collection/history panels as mutually exclusive surfaces.

## 3. Verify

- [x] Run `openspec validate fix-history-collection-panel-exclusion --strict`.
- [x] Run `cd frontend && npx tsc --noEmit --strict`.
- [x] Run `./test.sh e2e`, including the collection panel E2E gate.
