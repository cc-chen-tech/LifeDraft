## Why

History review and story voice controls currently share the main reading surface too tightly. A selected historical round can become unreadable because side panels and gameplay controls overlap the text, while the story voice panel exposes a not-yet-production TTS feature as a noisy debug surface.

## What Changes

- Keep selected historical story text in a dedicated, readable review surface until the user explicitly returns to the current round.
- Hide or demote components that block history reading while still allowing users to generate/view historical scene images when they choose.
- Redesign story voice controls as a polished unavailable/preview panel instead of exposing debug fields and ineffective TTS controls to normal players.
- Preserve test hooks for store behavior without showing test-only UI in production gameplay.

## Capabilities

### New Capabilities
- `history-reading-surface`: History review text remains readable, pinned, and unobstructed while selected.
- `story-voice-preview-panel`: Story voice controls present a production-quality preview/unavailable state until provider-backed TTS is enabled.

### Modified Capabilities
- `history-review`: History review must remain pinned and readable without overlaying unrelated gameplay components.
- `story-voice-reading`: Playback controls must not present an unusable production feature when no supported TTS provider is available.

## Impact

- Frontend gameplay page and history viewing layout.
- Story voice controls component and related component tests.
- Existing history viewer and PlayPage tests.
- No backend API or persistence migration is required.
