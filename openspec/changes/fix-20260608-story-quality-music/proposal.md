## Why

The 2026-06-08 live UX run showed that the product now has working surface integrations, but the core story quality and music behavior still regress in real play: required preset relationships are ignored, music recommendation ignores negative cues or collapses into duplicates, `/api/music/generate` can hang or return gateway errors, and initial wealth loses the user-visible currency amount.

This change fixes those live blockers with explicit contracts so future prompt, recommendation, and state changes cannot silently erase the player’s setup.

## What Changes

- Enforce preset key people and relationship facts in story generation prompts and post-generation validation.
- Prevent generated stories and entity extraction from replacing preset people with invented substitutes when canonical names are available.
- Make music recommendation negative cues and duplicate filtering effective at the returned-song layer, not only in the brief.
- Ensure MiniMax music generation uses accepted audio settings, fails within a bounded timeout, and returns a structured JSON error instead of hanging or returning HTML/empty responses.
- Preserve and display initial wealth as the configured currency amount, including yuan-style values such as `¥50,000`, through create -> save -> read -> frontend display.
- Add regression tests across static typing/imports, contracts, real DB integration, and browser E2E gates; update `test.sh` before code changes and do not skip or mock the new coverage.

## Capabilities

### New Capabilities

- `preset-relationship-authority`: Required preset people, roles, and relationships are authoritative in story generation, validation, and entity recognition.
- `music-recommendation-quality`: Music recommendation and generated music endpoints honor exclusion cues, dedupe songs, and degrade with bounded JSON failures.
- `currency-resource-consistency`: Initial wealth amount and currency unit stay consistent across character settings, game state, prompts, persistence, and frontend display.

### Modified Capabilities

- `gameplay-generation-recovery`: Polling/SSE recovery must not wait indefinitely when generation progress stops.
- `music-and-media-degradation`: Music endpoints must return structured degraded responses rather than 502/HTML/empty responses.

## Impact

- Backend prompt/context builders in `src/game/world_model.py`, `src/game/round/*`, and AI validation paths.
- Entity collection and relationship synchronization in `src/services/collection_service.py` / related extraction code.
- Music recommendation and generation services in `src/services/music_service.py`, `src/services/minimax_music_generation.py`, and `/api/music/*` routers.
- Character creation, game initialization, state persistence, and frontend resource display.
- Test gates in `tests/`, `frontend/e2e/`, and `test.sh`.
