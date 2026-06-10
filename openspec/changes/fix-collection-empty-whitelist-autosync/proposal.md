# Fix Collection Empty Whitelist Auto-Sync

## Why

Live gameplay reports showed story characters and objects appearing in the visible narrative while the collection panel stayed empty or stale. The backend recognition path treated an empty eligible-character whitelist as a hard deny-list, so clear named story people were filtered out when no relationship metadata existed. The frontend panel also skipped auto-recognition once old item and landmark collections existed, which hid later story characters.

## What Changes

- Treat an empty eligible-character whitelist as missing metadata for deterministic story-person fallback, while preserving strict filtering for non-empty whitelists.
- Extend conservative Chinese person extraction to handle explicit action patterns such as `方蕾要求...`.
- Auto-sync collection recognition when the collection only has the protagonist, even if item and landmark collections already contain entries.
- Add backend and frontend regression tests for the live UI path.

## Impact

- Backend entity recognition fallback behavior.
- Frontend collection panel initial auto-sync condition.
- Collection recognition tests and QA evidence.
