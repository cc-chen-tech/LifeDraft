## Why

`StoryService` handles user-authored choices and narrative state compression, but its maintained coverage leaves its delegation, prompt-safety, and failure-recovery behavior unguarded. These paths can regress without requiring a browser or external AI provider.

## What Changes

- Add provider-free contract tests for compression and world-update delegation.
- Add deterministic tests for custom-choice sanitization, retry behavior, and localized fallback results.
- Promote the new test module to both maintained backend coverage workflows.

## Capabilities

### New Capabilities
- `story-service-recovery-contracts`: Maintained regression coverage for StoryService delegation and custom-choice recovery behavior.

### Modified Capabilities

- None.

## Impact

- Affects `tests/` and the maintained backend test lists in GitHub Actions.
- Does not change application code, APIs, runtime dependencies, or external-provider behavior.
