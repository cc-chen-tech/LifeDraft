## Why

Story voice reading has a user-visible state chain from validated context through
job persistence, audio asset reuse, and reload recovery. Its maintained
coverage is low, so regressions in fallback mode and response fields can escape
to browser validation.

## What Changes

- Add real-DB contract tests for voice reading settings, browser fallback jobs,
  deterministic asset creation and reuse, and recovered job response fields.
- Validate source identity and text-hash boundaries without relying on mutable
  environment configuration.
- Register the new test module in both maintained backend workflows.

## Capabilities

### New Capabilities

- `story-voice-reading-db-contracts`: Maintained real-DB contracts for story
  voice reading state, asset ownership, provider fallback, and response shape.

### Modified Capabilities

- None.

## Impact

Adds a test module and maintained workflow entries only. Production voice
reading code, existing test files, API routes, and external TTS integrations
remain unchanged.
