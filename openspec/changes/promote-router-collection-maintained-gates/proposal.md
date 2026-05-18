## Why

The full backend suite is now green, but two router-level groups were still documented as legacy follow-ups rather than maintained gates. `tests/test_images_router.py` and `tests/test_api_collection.py` now pass together in a targeted run, so they can be promoted to prevent regressions in image routing and collection API behavior.

## What Changes

- Promote the stable image router and collection API legacy suites into maintained backend local and CI gates.
- Update coverage/fidelity checks so future gate wiring drift catches these promoted suites.
- Replace the previous legacy exclusion note with a verification record for this promotion.

## Capabilities

### New Capabilities
- `router-collection-maintained-gates`: Image router and collection API legacy suites must be stable and included in maintained backend gates.

### Modified Capabilities
- None.

## Impact

- `test.sh` maintained backend coverage and contract gate lists.
- Backend and coverage GitHub Actions maintained test lists.
- OpenSpec failure inventory / triage notes for legacy backend follow-ups.
- Gate-fidelity tests that assert promoted high-risk groups remain wired.
