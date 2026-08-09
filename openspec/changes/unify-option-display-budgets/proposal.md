## Why

A complete story can still strand the player when one generated option is long, duplicated, malformed, or missing. The backend currently retries or discards the group as a unit, while the frontend either hides the story behind a retry state or renders uneven multi-line controls without clear selection feedback.

## What Changes

- Resolve one localized `DisplayBudget` for every new option group: exactly three options, Chinese target 8-24 characters with repair after 40, English target 3-12 words with repair after 16, at most two provider calls, and two display lines.
- Preserve valid options and repair only invalid, duplicate, or malformed items; fill any remaining slots with contextual deterministic options when AI repair fails.
- Keep persisted legacy groups of two to four options readable without rewriting stored data.
- Render option controls with a stable two-line layout, accessible full text, touch-safe height, and immediate selected/loading feedback.
- Keep a completed story visible while options are pending and show “正在准备选择”; reserve the full-page retry state for missing story content.

## Impact

- Backend: `DisplayBudget`, option validation/repair/fallback, and event option-count contracts.
- Frontend: `OptionCards`, play-page pending-state rendering, accessibility, and loading feedback.
- Tests: localized option measurement, partial repair, fallback completion, legacy restore, component, and deterministic browser coverage.
- Rollout: stacked after `unify-narrative-generation-budgets`; no input-limit, summary, memory, CI, or DB-cleanup work.
