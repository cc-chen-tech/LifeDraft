## Why

The 2026-06-08 UX report found that clicking "收集" and "历史" can leave two dialogs open at the same time. This creates overlapping modal state and makes the play page controls ambiguous.

## What Changes

- Opening the collection panel closes the history panel.
- Opening the history panel closes the collection panel.
- Add an E2E regression in the existing collection panel E2E gate so `test.sh e2e` covers the interaction.

## Impact

- Frontend only.
- No API or database schema changes.
