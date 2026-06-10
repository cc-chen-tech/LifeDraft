## Why

The production read button already waits for `/voice-reading/settings` before starting playback, but automatic reading of a completed story did not use the same gate. When auto-read was enabled and a story completed before runtime settings loaded, the frontend could start a backend TTS request with default runtime assumptions. On browser-only production settings this creates a silent first-start delay before falling back, making auto-read after choices appear broken.

## What Changes

- Gate automatic story reading on the same voice settings readiness used by the manual read action.
- Add a regression test proving auto-read does not call `/voice-reading/read` while settings are pending.
- Verify that once settings report browser fallback, auto-read starts browser speech without the backend request.

## Impact

- Frontend story voice controls only.
- No backend API, schema, or persistence migration is required.
