# Scheduled E2E failures at e73fdc5dd8

## Evidence and classification

Compared the complete job logs and retries for [October 28](https://github.com/cc-chen-tech/LifeDraft/actions/runs/40779269260/job/123136489186) and [October 27](https://github.com/cc-chen-tech/LifeDraft/actions/runs/40590899820/job/122494553326), both at `e73fdc5dd8d5aa0aede04ec4fea132ff8bbfc8ac`. Inspected the October 28 screenshot/trace artifact, including network response bodies and rendered error contexts.

Both runs fail the same seven tests on every retry. October 28 reports 727 passed / 7 failed / 4 flaky / 4 skipped; October 27 reports 724 passed / 7 failed / 7 flaky / 4 skipped. These seven hard failures have reproducible fixture or test-contract causes; the evidence does not establish a production regression.

| Tests | Evidence | Cause and repair |
| --- | --- | --- |
| Two choice-impact tests | `event-sync` returns 503, `故事结构检查未通过`, before any choice is submitted. | The deterministic Chinese story has 355 characters, below the daily expert budget of 800–1400. Supply complete scenes sized using the actual generation budget and localized measurement. Once generation succeeds, submit the required `event_id` and `revision` with the choice; omitting these correctly returns 409. |
| Long-story test | Trace contains no created game; `/play` redirects to the homepage. The measured 60 characters are homepage text. | The layout header was incorrectly accepted as game readiness. Create a game, require the listening view, and compare every displayed story paragraph to persisted API prose. Length and sentence completion are mandatory assertions. |
| Ancient-era test | Legacy `era.name`/`period` fields normalize to year 2024; the trace also shows story-shape rejection. The `.prose-story` selector predates the listening view. | Supply canonical origin `1150-01-01`, assert the persisted year, use ancient-compatible deterministic prose/options, and inspect the actual transcript. A Python regression verifies the real era validator accepts the cast and rejects an added phone anachronism. |
| SSE polling test | A named error event containing `Simulated SSE timeout` produces a terminal visible error, with only the initial state GET. | A business error is not a transport disconnect. End a partial stream without `complete`, verify one reconnect with `Last-Event-ID: -1`, then a persisted snapshot read and enabled restored choices. Separately assert terminal validation errors remain visible and retry only when clicked. Preserve the v2 timeline in the mocked snapshot. |
| Mobile Safari: ready after real 20-second poll timeout | Baseline reproduced on WebKit 26.0. The real `HTMLMediaElement.play()` rejects with `NotAllowedError` after delayed readiness; the existing UI offers `点击播放，开启自动朗读`. | Browser autoplay policy, not evidence of a failed player. Observe the real rejection; only in that case require the recovery prompt and perform a trusted Play click. Keep the original 15-second assertion requiring advancing media time and the original-voice/no-fallback assertion. |
| Mobile Safari: Range-aware WAV autoplay | Playback advances; the failed assertion is `rangeRequests.length > 0`, not `expectRealPlayback`. WebKit requests a full 200 response. | A Range request is not mandatory for valid playback. Retain real autoplay, time updates and audio-node continuity. Add a separate explicit fixture test for exact 206 byte payload/headers and 416 unsatisfiable ranges, without depending on the browser's request strategy. This checks the fixture, not the production audio endpoint. |

## Provider boundary

Running the entire affected file after repairing game setup also exposed a previously vacuous progression test. Its broad button matcher clicked the transcript toggle, then looked for an obsolete header. It now clicks an actual numbered choice, requires a successful choice response, checks the persisted day increment and visible day label, and verifies the next event belongs to that date. The pre-fix failure was observed in the expanded run.

`E2E_DETERMINISTIC_STORY=1` remains the only activation path. The client passes the actual budget and prompt to the existing isolated provider. Chinese fixtures cover modern and South Song settings at fast/expert/master budgets; complete sentences are appended until the localized minimum is met. Production shape, era, required-cast and continuity validators remain active and unchanged.

The optional consistency model judge also receives a deterministic response in this mode. Previously it fell through to the CI dummy API key after fixing prose length. This replaces a model response at the E2E provider boundary; it does not disable the production validator. A disabled-mode regression verifies that normal calls still fall through to the real provider. English fixture expansion is outside these Chinese failures and has not been claimed as repaired.

## Verification

Regression tests were observed failing before their fixes: the real localized daily shape gate rejected short prose, the optional judge required an unavailable OpenAI client, and historical prose measured with raw `len` still fell below the localized expert minimum. The final implementation uses the production measurement function.

Completed checks:

- Provider, daily opening delivery, and production era contracts: **63 passed**.
- Frontend unit tests: **125 suites, 2,234 tests passed**.
- Frontend integration tests: **2 passed**.
- Audio transport E2E, all eight cases on Chromium and Mobile Safari, no retries: **16 passed**.
- TypeScript `tsc --noEmit` and production frontend build passed.
- Independent read-only review found no critical or important issues; its Range-test naming clarification was incorporated.

AI browser verification: **14 passed**, no retries, across the complete `choice-impact-visible`, `claude-code-improvements`, `era-validator-no-false-positive`, and `sse-timeout-sync` files. The added progression and restored-choice assertions passed in that final run.

Commands (with the E2E services and environment described below):

```bash
python -m pytest tests/test_e2e_deterministic_story_provider.py tests/test_daily_opening_delivery.py tests/test_era_validator_production_contract.py -q
cd frontend
npm run test:unit -- --runInBand
npm run test:integration -- --runInBand
npx tsc --noEmit
npm run build
npx playwright test --no-deps --workers=1 --retries=0 --project=ai-heavy choice-impact-visible.spec.ts claude-code-improvements.spec.ts era-validator-no-false-positive.spec.ts sse-timeout-sync.spec.ts
npx playwright test --no-deps --workers=1 --retries=0 --project=core --project="Mobile Safari" story-listening-audio-transport.spec.ts
```

Local browser versions match Playwright 1.58.2: Chromium 145.0.7632.6 and WebKit 26.0. Local runtime is Python 3.12 / Node 24; Actions uses Python 3.11 / Node 20. Browser dependencies were supplied locally because system installation is unavailable. No playback or browser execution was mocked by that environment setup.

Local model and image base URLs were directed to a loopback-only endpoint for final AI verification. Optional extraction/summary calls outside the deterministic narrative provider therefore exercise existing connection-failure fallbacks rather than contacting an external model with the CI dummy key. This is a verification-environment difference from the scheduled job, not a repository production configuration change.

The complete scheduled 742-test matrix and the separate flaky cases have not been verified as green by this change. No existing tests were skipped, no timeout was increased, and production validation thresholds were not relaxed.
