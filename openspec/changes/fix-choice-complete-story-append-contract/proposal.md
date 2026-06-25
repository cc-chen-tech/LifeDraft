## Why

The choice completion fallback is intentional: when a choice SSE stream completes
without emitting story chunks, the frontend must still display the backend's
completed continuation. A stale regression test still asserted that
`handleChoiceComplete` never writes story text, which contradicted the existing
`useChoiceHandler` behavior and caused the full frontend unit suite to fail.

## What Changes

- Align the choice completion regression test with the current fallback
  contract.
- Cover both retry and non-retry complete-only continuations.
- Preserve a no-duplicate guard when the same continuation was already appended
  by SSE story chunks.

## Impact

- `frontend/src/__tests__/hooks/choiceUtils.storyAppend.test.ts`
- `openspec/changes/fix-choice-complete-story-append-contract/specs/gameplay-continuity/spec.md`
