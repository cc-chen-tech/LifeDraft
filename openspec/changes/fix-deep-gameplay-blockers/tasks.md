# Tasks

## 1. Generation Recovery / Timeout

- [x] 1.1 Reproduce week-2-style stale generating state locally with active game state containing no visible story/options.
- [x] 1.2 Add failing backend and/or frontend tests that refresh/recovery never restores a no-body generating state when a completed event or retry path exists.
- [x] 1.3 Implement stale generation expiry, recovery precedence, and retry/continue UX.
- [x] 1.4 Run targeted tests for gameplay recovery and SSE timeout behavior.

## 2. Protagonist Identity Lock

- [x] 2.1 Add prompt contract tests for opening, week, and round prompts with `林见微` / `女`.
- [x] 2.2 Ensure prompts derive canonical protagonist name from `player_state` or request payload without requiring optional explicit args.
- [x] 2.3 Run targeted prompt tests.

## 3. Collection Recognition

- [x] 3.1 Reproduce story text containing named people plus many items/locations where collection misses characters.
- [x] 3.2 Add failing tests: all concrete story people are recognized; incidental items are filtered unless important/repeated.
- [x] 3.3 Implement recognition fallback/normalization and collection merge behavior.
- [x] 3.4 Run targeted collection/entity tests.

## 4. Browser Click Stability

- [x] 4.1 Reproduce normal-click failures with agent-browser or Playwright on week progression, ChatBar, and choice buttons.
- [x] 4.2 Add failing browser/component tests that detect overlay or hit-target blocking.
- [x] 4.3 Fix z-index/pointer-events/button ownership without changing unrelated UI.
- [x] 4.4 Run targeted browser/component tests.

## 5. Integration

- [x] 5.1 Merge worker branches into `codex/gameplay-blockers-integration`.
- [x] 5.2 Resolve conflicts only in integration.
- [x] 5.3 Run `openspec validate fix-deep-gameplay-blockers --strict`.
- [x] 5.4 Run targeted suites for all fixed areas.
- [x] 5.5 Run `./test.sh all` from integration worktree.

## 6. Live Opening State Parity Regression

- [x] 6.1 Reproduce `/story/opening` false "缺少角色数据" error with incomplete store state but available resolved/injected character data.
- [x] 6.2 Add frontend test asserting opening request payload uses resolved/injected character data, not stale store snapshot.
- [x] 6.3 Fix opening page generation payload source and complete-story fallback behavior for streamed text.
- [x] 6.4 Run targeted opening page tests.

## 7. Event Complete Recovery Regression

- [x] 7.1 Reproduce complete-event-without-options and complete-event-without-story paths leaving gameplay in generating phase.
- [x] 7.2 Add frontend unit tests asserting malformed complete events enter retryable error instead of silently returning.
- [x] 7.3 Fix event completion handling to clear retry state and switch to error phase when no playable event exists.
- [x] 7.4 Run targeted event completion tests.

## 8. Scene Illustration Background Regression

- [x] 8.1 Reproduce local background scene generation failing with `RoundIllustrationService` missing `generate_round_scene`.
- [x] 8.2 Add a front-loaded contract test asserting image router background service calls exist.
- [x] 8.3 Fix background scene generation to use the standard `ImageService.generate_round_scene_image` path.
- [x] 8.4 Run targeted scene image contract test and local browser scene image verification.

## 9. Collection Current Event Recognition Regression

- [x] 9.1 Reproduce smart recognition returning no entities while the currently displayed story contains named people.
- [x] 9.2 Add backend tests for recognizing current unresolved event text and avoiding obvious shop-name/person false positives.
- [x] 9.3 Include current event text in recognition input while keeping item recognition curated.
- [x] 9.4 Run targeted collection recognition tests and local browser verification.

## 10. Music 503 Degradation Regression

- [x] 10.1 Reproduce local music search 503 leading to noisy backend errors and unclear empty-state UI.
- [x] 10.2 Add backend/client and frontend component tests for graceful unavailable-state degradation.
- [x] 10.3 Downgrade music upstream 503 to warning and show a clear continue-gameplay message for empty recommendations.
- [x] 10.4 Run targeted music degradation tests and local browser verification.

## 11. Refresh Restore Re-generation Regression

- [x] 11.1 Reproduce `/play` refresh with saved `current_event_data` showing no body/options while `/event` starts a new generation.
- [x] 11.2 Add a backend contract test that loaded `current_event_data` survives round service initialization.
- [x] 11.3 Preserve loaded current event when initializing round services so refresh returns the existing event instead of regenerating.
- [x] 11.4 Run targeted backend restore test and local browser refresh verification.

## 12. Result Scene Round Alignment Regression

- [x] 12.1 Reproduce result-stage scene image request using the next round after choice completion.
- [x] 12.2 Add a frontend hook test asserting result scenes use the just-completed round.
- [x] 12.3 Fetch result-stage round scene images with `current_round - 1` after choice advancement.
- [x] 12.4 Run targeted frontend scene round test and local browser log verification.

## 13. Ancient Scene Illustration Era Regression

- [x] 13.1 Reproduce ancient story scene analysis producing modern visuals like down jackets, electric heaters, roads, and restaurants.
- [x] 13.2 Add scene analyzer tests for ancient visual era constraints and modern-output rejection.
- [x] 13.3 Inject visual era red-lines into scene analysis and reject analyzer output that violates ancient era constraints.
- [x] 13.4 Run targeted scene analyzer tests and local browser/log verification after backend restart.

## 14. Collection False Positive Regression

- [x] 14.1 Reproduce smart recognition suggesting pronoun/action fragments and duplicate short aliases as characters.
- [x] 14.2 Add entity recognition tests for `施主此`, `于是你`, `沈伯`, `沈先生`, and AI-returned duplicate alias false positives.
- [x] 14.3 Filter pronoun fragments and prune short title/person/location aliases when fuller names exist.
- [x] 14.4 Run targeted entity tests and local browser smart-recognition verification after backend restart.

## 15. Scene Image Premature Fetch Regression

- [x] 15.1 Reproduce frontend requesting a new round scene image before the round story exists, causing `no story text available` 404.
- [x] 15.2 Add a frontend hook test asserting scene images are not fetched during loading/generating without renderable story text.
- [x] 15.3 Fetch round scene images only when the UI is showing options/result and has story text, preserving completed-round result alignment.
- [x] 15.4 Run targeted hook tests and local browser/log verification.

## 16. Choice Continuation Narrative Person Regression

- [x] 16.1 Reproduce third-person event story switching to narrative `你` after a choice result.
- [x] 16.2 Add prompt contract tests for Chinese and English choice continuations requiring third-person narration and no current-story repetition.
- [x] 16.3 Update choice continuation prompts to forbid narrative second-person protagonist references and re-narrating already shown story.
- [x] 16.4 Run targeted prompt tests and local browser verification on the next choice result.

## 17. Duplicate Scene Generation Race Regression

- [x] 17.1 Reproduce concurrent SSE/frontend scene generation inserting the same `(game, week, round, stage)` scene and logging an unexpected `IntegrityError`.
- [x] 17.2 Add a backend RoundIllustrationService test for unique scene conflicts.
- [x] 17.3 Handle unique scene conflicts as idempotent by rolling back and reusing the existing scene record.
- [x] 17.4 Run targeted illustration service test.

## 18. Continue Loading Without Event Regression

- [x] 18.1 Reproduce continuing into the next week showing `故事生成中...` without any `/event` request.
- [x] 18.2 Add frontend state-machine tests for continue-after-summary and continue-to-next-round when player-state sync hangs.
- [x] 18.3 Add a guarded fallback that starts event generation after a short sync wait without duplicating generation.
- [x] 18.4 Run targeted state-machine tests and local browser recovery verification.

## 19. Collection Character False Positive Follow-up

- [x] 19.1 Reproduce local smart-recognition candidates containing time/action fragments such as `许久` and `马蹄踏`.
- [x] 19.2 Add a backend regression test that rejects those fragments while preserving real named people.
- [x] 19.3 Tighten deterministic person fallback filtering.
- [x] 19.4 Reproduce local smart-recognition candidates containing title aliases and verb fragments such as `林姑娘`, `陆公子`, `陆辞知`, `陆辞现`, and `陆辞坐`.
- [x] 19.5 Add backend regression coverage for title aliases and verb fragments.
- [x] 19.6 Tighten title-alias and name-plus-verb filtering while preserving full names.
- [x] 19.7 Run targeted entity recognition tests and local browser smart-recognition verification.

## 20. Collection Long History Recent Character Regression

- [x] 20.1 Reproduce smart recognition missing a recent/core character because long history truncation drops the newest story text.
- [x] 20.2 Add a backend regression test that preserves recent/current story people such as `石无言` under truncation.
- [x] 20.3 Adjust entity recognition truncation to retain both early and recent/current context.
- [x] 20.4 Run targeted entity recognition tests and local browser smart-recognition verification.

## 21. Collection Recognition Empty Dialog Regression

- [x] 21.1 Reproduce recognition dialog rendering only footer buttons when open with no recognition result.
- [x] 21.2 Add a frontend component test for open/no-result/non-loading dialog state.
- [x] 21.3 Render an explicit no-result state instead of an empty dialog body.
- [x] 21.4 Run targeted dialog tests and local browser verification.

## 22. Collection Recognition Truncation Bound Regression

- [x] 22.1 Reproduce recognition truncation returning more characters than its declared maximum.
- [x] 22.2 Add a backend unit test for max-length-bounded head/tail truncation.
- [x] 22.3 Adjust the truncation helper so marker text is included within the maximum length.
- [x] 22.4 Run targeted entity recognition tests.
