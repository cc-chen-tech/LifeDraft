## Why

The current music flow is directionally correct: it builds a structured `music_brief`, searches NetEase immediately, and generates a compact MiniMax instrumental prompt in the background. Matching quality is still uneven because the system lacks an explicit scene-matching score, prompt quality rubric, and feedback loop for whether selected/generated tracks actually fit the active story scene.

## What Changes

- Introduce a music-scene fit model that scores both NetEase candidates and generated/local AI tracks against the current `MusicBrief`.
- Strengthen `MusicBrief` extraction with clearer scene anchors, emotional arc, diegetic setting, intensity range, instrumentation priorities, and explicit avoid-list translation into generation prompts.
- Improve MiniMax prompts from a flat summary into a structured English music direction with primary emotion, scene action, setting texture, tempo/energy, instrumentation hierarchy, loop length, and negative instructions.
- Add deterministic fallbacks for common Story101 scenes such as modern workplace, suspense, recovery, family conflict, romance, action, and reflective endings.
- Add evaluation fixtures from report-observed mismatches so regressions can be tested without calling NetEase or MiniMax in CI.
- Add lightweight telemetry and debug metadata for selected tracks, rejected candidates, fit score, prompt version, and fallback reason.

## Capabilities

### New Capabilities
- `music-scene-matching-quality`: The system can score, explain, and improve story-to-music matching across NetEase, local AI-library, and newly generated MiniMax tracks.

### Modified Capabilities
- `music-and-media-degradation`: Weak or low-confidence matches should fall back to safer background music rather than surfacing obviously mismatched tracks.

## Impact

- Backend services:
  - `src/services/music_service.py`
  - `src/services/minimax_music_generation.py`
  - potential new `MusicSceneFitScorer` / prompt-builder module
- API:
  - `/api/music/recommend` continues returning compatible fields, with optional non-breaking diagnostics for fit score/prompt version.
  - `/api/music/generate` and `/api/music/generate-async` use the improved prompt builder and reject low-confidence reuse candidates when local-library work is present.
- Data:
  - Generated music metadata should record prompt version, fit-score inputs, and library/recommendation decision reasons where available.
- Tests:
  - Contract tests for brief extraction, scoring, prompt construction, negative cue enforcement, and safe fallback.
  - Regression fixtures for known mismatched scenes from UX reports.
  - Focused frontend tests verifying queue behavior remains stable while diagnostics/source metadata are preserved.
