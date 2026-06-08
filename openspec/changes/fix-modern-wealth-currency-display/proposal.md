## Why

The UX report shows a modern game configured with yuan-scale wealth displaying as `10,000 货币`. The numeric preservation was later covered, but the UI still has a generic `货币` fallback that leaks into modern gameplay when currency metadata is missing from the player state.

## What Changes

- Add a UI contract for modern wealth display in `StatusBar`.
- Treat modern or unspecified real-world gameplay wealth as yuan instead of generic `货币`.
- Keep explicit currency symbols and explicit currency names as the highest-priority display sources.
- Register the StatusBar contract in `test.sh` preflight so the full gate catches regressions.

## Impact

- Frontend status display: `frontend/src/components/game/StatusBar.tsx`.
- Frontend tests: `frontend/src/__tests__/components/StatusBar.test.tsx`.
- Test gate: `test.sh`.
