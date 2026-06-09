# Change: Fix story voice browser fallback

## Why
Production can fall back to browser speech when backend TTS audio is unavailable. In that mode the current UI still exposes three voice choices, but the browser speech path does not select a matching `SpeechSynthesisVoice`. Backend voice failures can also wait through retry backoff before browser speech starts, making first playback feel silent or broken.

## What Changes
- Select a matching browser speech voice for `warm_female`, `calm_male`, and `clear_neutral` when backend audio falls back to browser speech.
- Do not retry voice-reading API 5xx responses; let the story voice store immediately fall back to browser speech.
- Keep auto-reading completed choice-result stories working even while the unified sound panel remains collapsed.

## Impact
- Frontend story voice state machine and API retry policy.
- Focused Jest coverage for browser speech voice selection, immediate fallback, and collapsed-panel auto-read.
