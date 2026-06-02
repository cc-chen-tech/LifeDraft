## Overview

This change treats the live failures as state-machine and contract bugs rather than isolated UI glitches. The backend must expose stable generation/recovery states, the frontend must render actionable states for every backend outcome, and collection/auth contracts must be explicit enough to test before E2E.

## Goals

- A game can never remain indefinitely on a contentless `故事生成中...` screen after timeout, refresh, or retry.
- A private ID shown after registration can be submitted through the UI using the same field contract expected by the API.
- Story generation prompts use the canonical created character/world settings, not only a weak free-text preference.
- Collection recognition only proposes entities that satisfy system metadata rules and always exits loading with success, empty, or error state.
- Media failures degrade visibly and safely without blocking story progress.

## Non-Goals

- Rewriting the full LLM generation pipeline.
- Guaranteeing every AI generation is high quality; this change adds guardrails and recovery, not a new model.
- Adding new premium voice/music features.

## Design

### Generation Recovery

Represent generation as a recoverable lifecycle:

- `generating`: content may be absent or streaming.
- `partial`: story text exists but options/result are still pending.
- `recoverable_error`: generation timed out or failed after a persisted attempt; UI must offer retry/resume and preserve partial content.
- `ready`: story text and choices/result are present.

Backend recovery endpoints should derive the current lifecycle from persisted game state rather than volatile in-memory flags. If a timeout occurs after game creation, the game record must not be left in a state where `/play` only shows a loading label forever.

Frontend rendering should never show a bare loading string for longer than the timeout threshold without actionable controls. Existing recovery controls should be kept visible until the recovered content is actually available.

### Private ID Login

The user-facing credential is the private ID. The frontend may label it as a private key for users, but the request body must match the backend contract (`private_id`) or the backend should accept a backwards-compatible alias. API errors should distinguish validation mismatch, invalid credential, and network/server failure.

### Character Setting Continuity

Created settings are the source of truth. Opening and round prompts should include structured constraints for:

- role/profession and premise
- era/time period
- setting/world
- gender/person name
- narrative perspective/person

Generated opening text should be validated for obvious premise drift when the structured setting is explicit, with a retry or fallback prompt before committing.

### Collection Recognition

Recognition should use the system's relationship/importance metadata as the gate for character proposals. Text-only entity detection can suggest candidates internally, but candidates must pass metadata checks before appearing in the collection UI.

The recognition task must produce one terminal UI state:

- `candidates`: add button enabled with candidates.
- `empty`: no candidates, clear explanation.
- `error`: retryable error message.

It must not keep `添加中...` while analysis is still pending, and it must not repeat already-collected entities.

### Media Degradation

Music and image failures should not block gameplay. Music URLs emitted to an HTTPS page must be HTTPS-safe or proxied. If no era/mood-suitable track is available, the UI should show a neutral unavailable state rather than recommending obviously mismatched music as if it were confident.

## Test Strategy

- Write backend contract tests first for auth payload compatibility, generation recovery state derivation, character-setting prompt constraints, collection gating/de-duplication, and media URL safety.
- Add focused frontend tests for login payload, recovery UI not hiding controls, and collection loading terminal states.
- Add a minimal Playwright regression only for the browser behavior that unit/contract tests cannot cover: `/play` with a persisted recoverable generation error must render story/retry controls, not a bare loading screen.
- Run targeted tests during development; run broader gates before PR.
