# MiniMax local audio mode no longer requires production credentials

## Problem

PR #142 removed the hard-coded `MINIMAX_API_KEY=test-key` override from local E2E, but the backend still treated a missing MiniMax API key as unavailable before honoring `MINIMAX_E2E_LOCAL_AUDIO=1`.

This caused the MiniMax production-like E2E path to fail locally:

- Story narration requested `preferred_provider=minimax` but fell back to `browser_speech` instead of attaching a deterministic audio asset.
- AI music generation returned `503 MiniMax music generation requires MINIMAX_API_KEY`, so the generated track was never inserted ahead of the NetEase future queue.

## Root Cause

The deterministic local audio mode was implemented in lower-level clients, but availability checks happened earlier:

- `MiniMaxTTSProvider.metadata()` only considered `api_key`.
- `MiniMaxTTSProvider.synthesize()` fell back to browser speech before checking local audio mode.
- `MiniMaxMusicGenerationProvider.generate_to_asset()` raised on missing `api_key` before the local WAV branch.
- `/api/music/generate` and `/api/music/generate-async` rejected missing credentials before allowing local audio mode.

## Reproduction

On the #142 branch after merging latest `origin/main`:

```bash
pytest tests/test_minimax_audio_generation_contract.py -k "local_audio_mode_works_without_credentials or returns_ready_track_from_story_without_netease_blocking or returns_quickly_and_persists_future_playlist_track" -q
```

Initial failures confirmed:

- MiniMax TTS metadata reported `available=False`.
- MiniMax music provider raised `RuntimeError: MiniMax music generation requires MINIMAX_API_KEY`.
- `/api/music/generate?sync=true` returned `503`.

## Fix

Treat `MINIMAX_E2E_LOCAL_AUDIO=1` as a valid backend-audio capability for deterministic local E2E only:

- TTS metadata now reports backend audio as available when local audio mode is enabled.
- TTS synthesis only falls back to browser speech when both credentials and local audio mode are unavailable.
- TTS file extension/media type now follows `MiniMaxConfig.local_audio_enabled`.
- Music generation provider checks the local WAV branch before requiring a production API key.
- Music API routes allow missing credentials when local audio mode is enabled.

Production behavior remains credential-gated because `MINIMAX_E2E_LOCAL_AUDIO` is not enabled there.

## Verification

Passed:

```bash
pytest tests/test_minimax_audio_generation_contract.py -k "local_audio_mode_works_without_credentials or returns_ready_track_from_story_without_netease_blocking or returns_quickly_and_persists_future_playlist_track" -q
pytest tests/test_minimax_audio_generation_contract.py tests/test_minimax_audio_generation_db.py -q
cd frontend && npm test -- --runInBand frontend/src/__tests__/stores/useStoryVoiceStore.test.ts frontend/src/__tests__/stores/useMusicStore.musicQueuePolicy.test.ts frontend/src/__tests__/components/StoryVoiceControls.test.tsx frontend/src/__tests__/components/game/MusicPlayer.test.tsx
./test.sh e2e
```

Key E2E evidence:

- Main browser E2E: `303 passed`.
- Story voice E2E: `8 passed`.
- MiniMax story audio E2E: `4 passed`.
- Entity/collection E2E: `27 passed`.

