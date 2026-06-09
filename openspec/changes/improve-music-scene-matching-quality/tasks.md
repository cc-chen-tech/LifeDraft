## 1. Tests And Fixtures First

- [x] 1.1 Add offline fixture stories for modern workplace, suspense, recovery, family conflict, romance, action/conflict, reflective ending, and generic fallback scenes.
- [x] 1.2 Add contract tests for scene-fit profile extraction from story text and character settings.
- [x] 1.3 Add scoring tests proving compatible candidates outrank weak candidates and negative-cue conflicts are rejected.
- [x] 1.4 Add MiniMax prompt-builder tests for structured English direction, prompt version, strict character budget, and negative instruction translation.
- [x] 1.5 Add degradation tests proving low-confidence candidate pools fall back to safe background music or pending music state.
- [x] 1.6 Add diagnostics tests proving fit score, prompt version, selected strategy, and rejection reasons are emitted without breaking existing response fields.
- [x] 1.7 Run the new targeted tests before implementation and confirm they fail for missing scene-fit behavior.

## 2. Scene-Fit Profile Extraction

- [x] 2.1 Add a `MusicSceneFitProfile` or equivalent typed structure for primary emotion, secondary emotion, scene action, scene type, setting, era, pacing, energy, tension, instruments, and negative cues.
- [x] 2.2 Extend `MusicContextBuilder` to derive the scene-fit profile from existing music analysis, story text, and character settings.
- [x] 2.3 Add deterministic templates for recurring Story101 contexts such as workplace AI collaboration, suspense/chase, recovery, family conflict, romance, action, and reflective endings.
- [x] 2.4 Keep `MusicBrief` response compatibility while adding any new fields as optional or internal metadata.

## 3. Candidate Scoring And Ranking

- [x] 3.1 Implement a `MusicSceneFitScorer` that returns a numeric score plus reason codes for candidate selection.
- [x] 3.2 Integrate scene-fit scoring into NetEase result ranking and dedupe without calling external providers in tests.
- [x] 3.3 Apply the same scoring and negative-cue checks to generated AI and local-library candidates when those candidates are present.
- [x] 3.4 Add conservative thresholds for selecting, rejecting, and falling back from weak music matches.

## 4. Versioned MiniMax Prompt Builder

- [x] 4.1 Add a dedicated MiniMax music prompt builder with a prompt version identifier.
- [x] 4.2 Build prompts with compact story context, mood, scene action, setting texture, pacing/tempo, energy, instrumentation hierarchy, loop/background constraints, and negative instructions.
- [x] 4.3 Enforce `MINIMAX_MUSIC_PROMPT_MAX_CHARS` while preserving the highest-priority scene and negative-cue instructions.
- [x] 4.4 Store prompt version and fit-profile metadata with generated music assets for diagnostics and future tuning.

## 5. Diagnostics And API Compatibility

- [x] 5.1 Emit sanitized logs or optional metadata for fit score, prompt version, selected strategy, fallback reason, and rejected candidate reasons.
- [x] 5.2 Ensure `/api/music/recommend`, `/api/music/generate`, and `/api/music/generate-async` remain backward compatible for existing frontend consumers.
- [x] 5.3 Update frontend music store tests to preserve unknown diagnostic/source metadata without changing visible playback behavior.

## 6. Verification

- [x] 6.1 Run targeted backend music contract tests for fixtures, scoring, prompt building, and fallback.
- [x] 6.2 Run targeted frontend music store/player tests affected by metadata preservation.
- [x] 6.3 Run `openspec validate improve-music-scene-matching-quality --strict`.
- [ ] 6.4 Run the relevant `./test.sh` layers for backend contract, DB, frontend, and music E2E behavior before implementation is marked complete.
