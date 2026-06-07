# UX Report 2026-06-07 Fix Status

Date: 2026-06-08
Branch: `codex/deep-ux-p0-fixes`
PR: #51

This note tracks follow-up fixes for `docs/ux-report-2026-06-07.md`.

## Closed In This Follow-Up

- Entity collection UI path now auto-collects recognized story entities when the collection is empty.
  - Unit coverage: `frontend/src/__tests__/stores/useCollectionStore.test.ts`
  - Browser coverage: `frontend/e2e/no-mock-regression.spec.ts`
- Persona drift detection now retries a round event when the generated story ignores all configured key people and fabricates a new named cast.
  - Backend coverage: `tests/test_gate_gameplay_behavior_no_mock.py`
- Modern debt/crisis music intent now prefers financial suspense/instrumental search terms and filters love-pop or `type beat` terms from top search queries.
  - Contract coverage: `tests/test_story_music_recommendation_contract.py`
- Music player queue advance now wraps or advances persisted playlists instead of getting stuck on the same track.
  - Store coverage: `frontend/src/__tests__/stores/useMusicStore.musicQueuePolicy.test.ts`
- Modern/2020s story prompts now require `第N周·周一/周中/周末` style timeline titles instead of classical `第X回 + 七字对仗标题`.
  - Prompt coverage: `tests/test_player_name_in_prompts_contract.py`, `tests/test_era_anachronism_contract.py`
- Wealth display now uses the configured currency symbol before the amount, for example `财富: ¥50,000`.
  - Component coverage: `frontend/src/__tests__/components/game/StatusBar.test.tsx`
- Summary/settings mismatch has focused guards: summary quick action must not trigger regeneration, and settings must not open the chat panel.
  - Coverage: `frontend/src/__tests__/components/ChatBar.test.tsx`, `frontend/e2e/quality-level.spec.ts`
- NetEase recommendation results now reject obvious LLM prompt/response leakage titles before they enter the playlist, so search results like "请提供需要分析的文本..." are filtered out even when they have playable URLs.
  - Regression coverage: `tests/test_music_pool_cache_integration.py::TestGetOrBuildPool::test_supplement_pool_filters_prompt_leak_song_titles`
- NetEase recommendation results now also reject playable songs whose title/album/artist metadata directly matches the story brief's negative cues, for example `type beat`, `喜欢你`, or `情歌` in a tense workplace suspense scene.
  - Regression coverage: `tests/test_music_pool_cache_integration.py::TestGetOrBuildPool::test_supplement_pool_filters_negative_cue_songs_for_story_context`
- Game creation now normalizes list-shaped `relationships` payloads into canonical `relationships.key_people` before initializing state, preventing a production 500 when clients send key people as a top-level list.
  - Regression coverage: `tests/test_game_initializer_relationships_contract.py`, `tests/test_api_games.py::TestCreateGame::test_create_game_accepts_relationships_list_payload`
- Music player unit coverage now matches the current playlist queue contract: recommendation refreshes persist baseline NetEase songs into `/api/music/playlist/{game_id}`, and legacy recommendation responses without `music_brief` must not call `/api/music/generate`.
  - Regression coverage: `frontend/src/__tests__/components/game/MusicPlayer.test.tsx`
- Week finalization no longer waits for non-critical post-week enrichment tasks before returning the choice result. Weekly summary, bonus effects, decay, and week advancement still finish synchronously; character profile synthesis plus item/landmark/period summaries now run after the week has advanced.
  - Regression coverage: `tests/test_finalizer.py::TestFinalizeWeek::test_finalize_week_does_not_wait_for_slow_enrichment_tasks`
- Collection display and entity recognition now accept legacy list-shaped `character_settings.relationships` payloads, so key people from older saves are not dropped from the collection panel or recognition candidate set.
  - Regression coverage: `tests/test_collection_cache_db.py::TestSessionServiceRestore::test_collection_service_accepts_legacy_relationships_list`, `tests/test_api_collection.py::TestRecognizeEntities::test_eligible_recognition_characters_accepts_legacy_relationships_list`

## Verification

- Focused backend prompt/music/persona tests: 18 passed.
- Focused frontend unit tests: 74 passed.
- `./test.sh e2e`: core 301 passed, AI music queue 1 passed, story voice 8 passed, MiniMax story audio generation 4 passed.
- Production deployment verification on `story101.live` after manually deploying PR #51 head to ECS:
  - `/api/voice-reading/settings` returns `tts_provider: "minimax"` and `backend_audio_enabled: true` for an authenticated user.
  - Browser UI on `/e2e-regression` returns `voice-reading-mode=audio`, `voice-reading-provider=minimax`, and a decodable `/api/voice-reading/audio/*.mp3` asset.
  - Browser auto-read stays idle during the simulated partial stream and starts only after the final story-ready signal.
  - `/api/music/generate` produces a MiniMax `ai_generated` MP3 asset with `insert_policy: future_queue`.
  - Browser UI inserts the generated MiniMax music track into the future queue without replacing the current NetEase track.
- Production real `/play` verification on game 50 after deploying `7ab5752f` to ECS:
  - Completed story auto-read called `/api/voice-reading/read` and returned `provider=minimax`, `playback_mode=audio`, and a generated `/api/voice-reading/audio/*.mp3` URL.
  - `/api/music/recommend` returned `music_brief`.
  - `/api/music/generate` returned a MiniMax `ai_generated` MP3 asset.
  - `/api/music/playlist/50` contained the generated MiniMax track in the future queue after the current NetEase baseline track.
- Production `/api/music/recommend` verification after deploying `aa46c27c` to ECS:
  - A modern workplace data-fraud suspense story returned `music_brief`.
  - Prompt-leak title matches: 0.
  - Direct negative-cue matches for `type beat`, `喜欢你`, `情歌`, and `双截棍`: 0.
- Production `/api/games` verification after deploying `261125f1` to ECS:
  - A top-level list-shaped `character_settings.relationships` payload returned 201 instead of 500.
  - Loading the created game returned `player_state.relationships` containing `陆昊然` and `陈晓雨`.
  - Loading the created game returned canonical `character_settings.relationships.key_people` count 2.
- Production long synchronous gameplay probe on game 55 reached week 4:
  - Ran 12 real production rounds using `event-sync -> choice-sync -> state`.
  - Final state was `week=4`, `round=0`, `round_history` length 12.
  - No week-2 deadlock reproduced on the synchronous API path.
  - Observed latency remains a product blocker: event generation took roughly 30-44s per round and choice processing took roughly 35-106s per round.
- Focused backend regression batch after the week-finalization and collection compatibility fixes: 51 passed.
- Production deployment verification after manually deploying `d4c36531` to ECS:
  - `/health` and `/api/health` are healthy, and `/opt/story2` is at `d4c36531`.
  - Production MiniMax env flags are present without exposing secret values.
  - Authenticated `/api/voice-reading/settings` returns `tts_provider: "minimax"` and `backend_audio_enabled: true`.
  - `/api/voice-reading/read` returned backend `audio/mpeg` MiniMax audio for both `warm_female` and `calm_male`.
  - `/api/music/generate` returned 200 in about 105s with an `ai_generated` track, an audio URL, and `insert_policy: "future_queue"`.
- Frontend full unit suite passes locally in serial mode: `npm run test:unit -- --runInBand` with 97 suites and 1681 tests passing.
- Production deploy workflow now injects a temporary GitHub token for private-repo fetches on ECS and restores the clean GitHub remote URL after fetch, so the host does not need a persisted token in `origin`.

## Still Not Claimed As Production-Complete

- Remote GitHub checks are blocked by GitHub billing/spending-limit status, not by retrievable job logs.
- Fresh MiniMax music generation can take longer than 150 seconds on production; the current design keeps NetEase playback available and inserts generated music only after the asset is ready.
- Broader music matching quality still needs follow-up: prompt-leak and direct negative-cue filters prevent the worst mismatches from entering the queue, but they do not guarantee every remaining NetEase recommendation is semantically strong.
- Browser/manual long playthrough to week 4 should still be rerun after deployment, because the production synchronous API probe does not validate all `/play` UI states, SSE streaming behavior, button interactions, media playback, or visual overlap.
