## 1. Test Gates First

- [x] 1.1 Add preflight tests that validate the OpenSpec change, MiniMax secret scanning, and `test.sh` wiring; run them and confirm they fail before implementation.
- [x] 1.2 Add strict mypy gate expectations for new MiniMax provider/orchestration modules; run the static gate and confirm it fails before implementation.
- [x] 1.3 Add import validation for MiniMax TTS and music providers without credentials; run import tests and confirm they fail before implementation.
- [x] 1.4 Add provider/API contract tests for MiniMax TTS responses, MiniMax music request payloads, generated-track queue fields, and frontend consumer fields; run contract tests and confirm they fail before implementation.
- [x] 1.5 Add real DB integration tests for generated narration/music asset save-read-reuse flows; run DB tests and confirm they fail before implementation.
- [x] 1.6 Add focused frontend/browser E2E tests for provider audio playback state and generated music queue insertion; run them locally and confirm they fail before implementation.
- [x] 1.7 Update `test.sh` so every new gate is reachable from preflight, mypy, imports, contract, db, and e2e layers before production implementation begins.

## 2. Provider Configuration And Contracts

- [x] 2.1 Add MiniMax configuration helpers for API key, base URLs, model defaults, feature flags, timeouts, prompt budgets, and generated asset directories.
- [x] 2.2 Add typed provider request/response dataclasses or schemas for story narration assets, music briefs, generated music assets, provider status, and generation errors.
- [x] 2.3 Add secret-safe logging and error objects that preserve provider/model/status without exposing API keys or raw sensitive headers.
- [x] 2.4 Run targeted static/import/contract tests and keep all newly added tests green.

## 3. MiniMax Story TTS

- [x] 3.1 Implement `MiniMaxTTSProvider` behind the existing story TTS provider protocol using async TTS synthesis and persisted audio files.
- [x] 3.2 Add text chunking or bounded-input handling so over-limit story text fails gracefully or uses a configured fallback path.
- [x] 3.3 Integrate MiniMax provider selection into `build_story_tts_provider` while preserving browser speech fallback when credentials are missing or synthesis fails.
- [x] 3.4 Ensure equivalent text/voice/speed/provider/model/audio-format requests reuse existing ready narration assets.
- [x] 3.5 Run targeted TTS static/import/contract/DB tests and focused story voice browser E2E.

## 4. MiniMax Music Generation

- [x] 4.1 Implement a bounded `MusicBrief` builder from completed story text with mood, scene, tempo or energy, instrumentation, and negative cues.
- [x] 4.2 Implement `MiniMaxMusicGenerationProvider` using HTTP generation with instrumental/background defaults and safe asset download/storage.
- [x] 4.3 Persist generated music job/asset metadata, including provider, model, settings, prompt, brief hash, status, asset URL/path, duration, and error details.
- [x] 4.4 Reuse ready generated music assets for equivalent game/brief/provider/model/settings identity.
- [x] 4.5 Insert ready generated tracks into future playlist slots using existing queue policy without changing the current track.
- [x] 4.6 Run targeted music contract/DB tests and focused music browser E2E.

## 5. Story Completion Orchestration And Frontend

- [x] 5.1 Trigger story TTS only after final story text exists and only when the user has enabled auto-read or manually clicks read.
- [x] 5.2 Keep story auto-read default disabled in settings and frontend store initialization.
- [x] 5.3 Trigger AI music generation after story completion by default when not explicitly disabled, without blocking NetEase recommendations.
- [x] 5.4 Expose generated MiniMax track metadata in frontend music queue state and show generated-track readiness without disrupting playback controls.
- [x] 5.5 Verify browser automation observes decodable audio URL playback state for narration and generated music queue insertion.

## 6. Review, Verification, PR, And Deployment

- [x] 6.1 Perform a code review after the TTS implementation slice and fix any issues test-first.
- [x] 6.2 Perform a code review after the music generation implementation slice and fix any issues test-first.
- [x] 6.3 Run targeted local gates after each slice; defer `./test.sh all` until the branch is ready for PR.
- [x] 6.4 Run `./test.sh all` before opening the PR and record exact results.
- [x] 6.5 Create a commit only after code review and local verification pass.
- [x] 6.6 Push the branch and open a GitHub PR.
- [x] 6.7 Merge after checks are acceptable or any platform/billing blocker is clearly separated from code failures.
- [x] 6.8 After deployment completes, verify `story101.live` in browser for story reading and generated music behavior; if behavior is wrong, write a failing test before fixing.
