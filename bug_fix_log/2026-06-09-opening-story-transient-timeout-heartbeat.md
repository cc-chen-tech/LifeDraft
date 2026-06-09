# Fix: Opening Story Transient Timeout Becomes User-Visible Failure

Date: 2026-06-09

## Problem

Production QA on `story101.live` found that a fresh game could reach `/story/opening` and show:

```text
故事生成失败: Generation timeout
```

Clicking retry later recovered and displayed the opening story. This made the first game start look broken even though the backend and model provider were still able to produce a valid story.

Evidence:

- `docs/story101-production-qa-heartbeat-2026-06-09-0637.md`
- `docs/qa-evidence/2026-06-09-heartbeat-0637-production/20-opening-page.png`
- `docs/qa-evidence/2026-06-09-heartbeat-0637-production/22-opening-retry-success.png`

## Root Cause

The opening-story SSE endpoint treated an `asyncio.wait_for(q.get())` timeout before the next heartbeat deadline as a hard generation timeout.

That conflated two different states:

- transient queue wait timeout while the worker thread is still alive
- actual generation failure or hard timeout

When the queue wait timed out transiently, the endpoint emitted an `event: error` with `Generation timeout`, causing the frontend to enter a terminal retry screen even though generation could still complete.

## Regression Test

Added:

```text
tests/test_opening_story_contract.py::TestOpeningStoryAPIContract::test_opening_story_wait_for_timeout_while_thread_alive_is_heartbeat_not_failure
```

The test patches the first queue wait to time out while the generation thread is still alive, then verifies the stream keeps sending heartbeat/status and eventually completes with story text instead of emitting `Generation timeout`.

## Fix

Changed `src/api/routers/character.py` so opening-story SSE:

- sends heartbeat/status while the generation thread is alive
- only emits `Generation timeout` after a hard inactivity limit or after generation exits without usable story text
- keeps the existing guard that prevents empty `complete` events

## Verification

Commands run:

```bash
python -m pytest tests/test_opening_story_contract.py::TestOpeningStoryAPIContract::test_opening_story_wait_for_timeout_while_thread_alive_is_heartbeat_not_failure tests/test_opening_story_contract.py::TestOpeningStoryAPIContract::test_opening_story_timeout_does_not_emit_empty_complete tests/test_opening_story_contract.py::TestOpeningStoryAPIContract::test_opening_story_heartbeat_on_slow_generation -q
python -m pytest tests/test_opening_story_contract.py -q
TEST_RUN_ROOT=/tmp/story2-codex-test-runs TEST_NAMESPACE=opening_timeout_contract_1780989005 ./test.sh contract
TEST_RUN_ROOT=/tmp/story2-codex-test-runs TEST_NAMESPACE=opening_timeout_all_1780989150 ./test.sh all
```

Results:

- `3 passed`
- `7 passed`
- `127 passed, 9 warnings`
- `./test.sh all`: Preflight PASS, Layer 1 mypy PASS, Layer 2 imports PASS, Layer 3 contract PASS, Layer 4 db PASS, Layer 5 e2e PASS

## Remaining Risk

This fix prevents premature timeout errors in the opening-story stream. It does not address the separate UX issue where opening and round story generation can produce very long text and long waits before choices appear.
