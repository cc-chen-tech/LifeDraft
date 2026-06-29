# Fix Story Voice First-Read Runtime Settings

## Why

When a user clicks story reading before `/voice-reading/settings` has populated
the client store, the first read can incorrectly call `/voice-reading/read`
before knowing whether production is configured for backend audio or browser
speech. On browser-fallback production this adds an unnecessary backend
roundtrip before speech starts, which makes the first click feel silent or
broken.

## What Changes

- Make `startReading` load runtime voice settings when provider state is still
  unknown.
- If settings report browser speech fallback, start browser speech immediately
  without first calling `/voice-reading/read`.
- Keep explicit E2E preferred-provider overrides unchanged.
- Add a store regression test for first-read settings hydration.

## Impact

- Frontend story voice store only.
- No backend API or schema changes.
