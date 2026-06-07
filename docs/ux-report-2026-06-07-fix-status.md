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
- Mainline round illustration generation no longer auto-generates missing entity/person/item/location images by default. Production browser probing showed post-event image backfill could fan out into extra image API calls and hit upstream 429 rate limits; scene illustrations still generate, while entity images remain available through explicit collection/image flows or by setting `AUTO_GENERATE_ENTITY_IMAGES_FOR_SCENES=true`.
  - Regression coverage: `tests/test_sse_helpers.py::TestTriggerRoundIllustration::test_entity_image_backfill_disabled_by_default`, `tests/test_illustration_service.py::TestSyncGeneration::test_sync_generation_skips_missing_entity_image_backfill_by_default`
- `/play` no longer exposes partial streaming story text to the global music player. Music recommendation and MiniMax music generation now wait until the round story reaches `options` or `result`, matching the product requirement that music work starts after story generation finishes.
  - Regression coverage: `frontend/src/__tests__/pages/PlayPage.test.tsx`
- The empty-generation recovery button is now limited to truly empty loading state. A restored or partially streamed story without options no longer shows the same "恢复当前进度" button that force-cleared the visible story and started a duplicate `/event` request.
  - Regression coverage: `frontend/src/__tests__/pages/PlayPage.test.tsx`
- Choice SSE interruptions now fall back to `choice-sync` even when part of the result stream has already arrived. The fallback rebuilds the result from the pre-choice story text, so a broken `/choice` stream cannot leave the `/play` page in `error` with a half-appended continuation.
  - Regression coverage: `frontend/src/__tests__/hooks/choiceUtils.test.ts`
- Choice fallback now preserves structured FastAPI error details. When the original `/choice` stream actually completed server-side but the browser saw `ERR_INCOMPLETE_CHUNKED_ENCODING`, a later `/choice-sync` can return `{error: "choice_already_processed"}`; the frontend now recognizes that structured detail and recovers to the result phase instead of showing a generic Bad Request error.
  - Regression coverage: `frontend/src/__tests__/hooks/choiceUtils.test.ts`, `frontend/src/__tests__/lib/api.error-handling.test.ts`
- Event SSE completion is now persisted immediately in the worker thread after `generate_round_event` returns. Production browser probing showed the browser can drop the stream before the async generator reaches its `complete` block; worker-side persistence lets subsequent `/games/{id}` state polling restore the generated story and options instead of overwriting the session with stale empty event data.
  - Regression coverage: `tests/test_sse_helpers.py::TestSSEAsyncFunctions::test_stream_round_event_persists_state_before_complete_event`
- Modern product-manager/workplace music intent now uses focused instrumental workplace queries and filters production-observed weak NetEase pop matches such as `说散就散`, `匆匆那年`, `夜曲`, and `一直很安静`.
  - Regression coverage: `tests/test_story_music_recommendation_contract.py::test_modern_product_workplace_searches_focus_ambience_not_vocal_pop_hits`, `tests/test_music_pool_cache_integration.py::TestGetOrBuildPool::test_supplement_pool_filters_modern_product_workplace_pop_mismatches`
- Modern workplace NetEase fallback now also rejects weak candidate metadata that does not look like score/background/ambient/electronic/workplace music. Production verification after `eef57d17` still returned `童话镇`, `童话`, and a `童话` vocal remix; this follow-up keeps those generic vocal-pop results out of the verified pool even when they come from broad "都市电子背景音乐" searches.
  - Regression coverage: `tests/test_music_pool_cache_integration.py::TestGetOrBuildPool::test_supplement_pool_filters_workplace_candidates_without_score_metadata`

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
- Production browser smoke after deploying `d4c36531`:
  - Chromium mobile/tablet/desktop viewports all showed the bottom chat launcher, `重写`, `改写`, `总结`, and the top settings button.
  - Chromium, Firefox, and WebKit desktop engines all showed the same controls and confirmed the settings menu did not open the chat panel.
- Production browser long-flow probe after deploying `d4c36531`:
  - First event SSE completed and returned 3 options.
  - Follow-up `/api/games/{id}/state` polling hit a 30s client timeout during the probe.
  - Backend logs showed post-event illustration/entity-image work immediately hit upstream image API 429 limits, so this follow-up disables default entity image backfill in the mainline scene flow before rerunning the browser week-4 path.
- Production browser long-flow probe after deploying `87a0454e`:
  - Reproduced `/api/games/{id}/event` `ERR_INCOMPLETE_CHUNKED_ENCODING` while the first event was still generating.
  - The UI then exposed "恢复当前进度" despite having about 3400 streamed characters, and clicking it cleared that partial story before the backend completed.
  - Backend logs also showed music recommendation URL probing during the unfinished event stream, so this follow-up prevents partial streaming story text from triggering global music recommendation/generation.
- Focused illustration regression batch after disabling default entity image backfill: 43 passed.
- Focused PlayPage regression batch after the recovery/music handoff fix: 59 passed.
- Frontend full unit suite passes locally in serial mode: `npm run test:unit -- --runInBand` with 97 suites and 1681 tests passing.
- Production deploy workflow now injects a temporary GitHub token for private-repo fetches on ECS and restores the clean GitHub remote URL after fetch, so the host does not need a persisted token in `origin`.
- Production browser long-flow probe after deploying `4d6b8b26`:
  - First event generation reached options and music recommendation only started after the completed story was ready.
  - The partial-story recovery control stayed hidden while story text was streaming.
  - Selecting the first option reproduced a remaining blocker: `/api/games/68/choice` failed with `net::ERR_INCOMPLETE_CHUNKED_ENCODING`, and the page entered `error` because the interrupted choice stream was not falling back to `choice-sync`.
- Focused choice/play regression batch after the interrupted-choice fallback fix: 98 passed.
- Production browser long-flow probe after deploying `8bde0f85`:
  - First event generation reached options, and music recommendation still waited until options were ready.
  - First choice reproduced `/api/games/69/choice` `ERR_INCOMPLETE_CHUNKED_ENCODING`; the new fallback recovered the page to the result phase.
  - Second choice reproduced the next blocker: the original `/choice` stream completed server-side, then `/choice-sync` returned a structured `choice_already_processed` 400. The API client collapsed that object-shaped detail into `Bad Request`, so the page still entered `error`.
- Focused choice/API regression batch after preserving structured fallback errors: 125 passed.
- Production browser long-flow probe after deploying `d3163f74`:
  - Authenticated voice settings returned `tts_provider: "minimax"` and `backend_audio_enabled: true`.
  - Real `/play` auto-read triggered `/api/voice-reading/read` and returned `provider=minimax`, `playback_mode=audio`, and an audio URL.
  - First `/choice` again failed with `ERR_INCOMPLETE_CHUNKED_ENCODING`, and the fallback recovered to `result`.
  - The next `/event` failed with `ERR_INCOMPLETE_CHUNKED_ENCODING`; backend logs showed event generation completed and options were produced, but state polling reloaded stale saved state where `current_event_data` was empty. This follow-up persists generated event state before emitting SSE `complete`.
- Focused SSE regression batch after moving event persistence before complete: 60 passed.
- Production browser long-flow probe after deploying `f877baa2`:
  - The first post-summary `/event` recovered, proving persisted event state can be read by the next round.
  - A later `/event` still timed out after browser disconnection because FastAPI closed the async generator before it reached the `complete`/autosave block, even though `generate_round_event` finished later in the worker thread. This follow-up moves the persistence into the worker thread immediately after generation returns.
- Production abort-and-restore probe after deploying `b2346978`:
  - Direct MiniMax TTS requests for both `warm_female` and `calm_male` returned 200 with `provider=minimax`, `playback_mode=audio`, `media_type=audio/mpeg`, and an audio URL.
  - A real `/api/games/72/event` stream was intentionally aborted after receiving early status chunks.
  - The worker continued generation after the browser abort, and `/api/games/72` polling restored `current_event` after about 59 seconds with story length 2513 and 3 options.
  - This validates the event-disconnect persistence path that previously left `/play` stuck in polling/error after the backend finished generation.
- Focused music recommendation regression batch after adding modern product/workplace filters: 62 passed.
- Full local preflight after adding modern product/workplace filters:
  - OpenSpec strict validation: 21 passed.
  - Backend preflight quality checks: 86 passed.
  - Frontend preflight Jest regression tests: 297 passed.
- Production API verification after deploying `eef57d17`:
  - `story101.live` returned `tts_provider: "minimax"`, `backend_audio_enabled: true`, and `playback_mode: "audio"`.
  - Direct MiniMax TTS requests for `warm_female` and `calm_male` both returned backend `audio/mpeg` assets that downloaded successfully.
  - Modern product/workplace music recommendation no longer returned the previously observed `说散就散`, `匆匆那年`, `夜曲`, or `一直很安静` terms, but still exposed a new weak NetEase match set: `童话镇`, `童话`, and a `童话` vocal remix. This follow-up adds the stricter weak-candidate metadata filter.
- Focused music recommendation regression batch after adding weak workplace candidate filtering: 63 passed.
- Full local preflight after adding weak workplace candidate filtering:
  - OpenSpec strict validation: 21 passed.
  - Backend preflight quality checks: 86 passed.
  - Frontend preflight Jest regression tests: 297 passed.
- Production API verification after deploying `0b396b15`:
  - `story101.live` returned `tts_provider: "minimax"`, `backend_audio_enabled: true`, and `playback_mode: "audio"`.
  - Direct MiniMax TTS requests for `warm_female` and `calm_male` both returned backend `audio/mpeg` assets that downloaded successfully.
  - Modern product/workplace music recommendation returned no NetEase songs after strict filtering, and had no bad hits for `说散就散`, `匆匆那年`, `夜曲`, `一直很安静`, `童话`, `童话镇`, `情歌`, or `type beat`.
  - Direct NetEase probing showed broad "职场/电子/纯音乐/lofi" queries still return many playable vocal-pop mismatches, so returning an empty safe baseline is currently preferable to poisoning the queue.
  - `/api/music/generate` returned an `ai_generated` track with an audio URL in about 112.7 seconds and inserted it into the playlist `future_queue`.

## Still Not Claimed As Production-Complete

- Remote GitHub checks are blocked by GitHub billing/spending-limit status, not by retrievable job logs.
- Fresh MiniMax music generation can take longer than 150 seconds on production; the current design keeps NetEase playback available and inserts generated music only after the asset is ready.
- Broader music matching quality still needs product tuning: strict modern workplace filtering prevents known bad NetEase songs, but for that scene class the safe NetEase baseline can be empty and the generated MiniMax track becomes the reliable queued music source.
- Browser/manual long playthrough to week 4 should still be rerun after deployment, because the production synchronous API probe and browser smoke do not validate all `/play` SSE progression states across 12 real rounds.
