# Choice HTTP Error Fallback Recovery - 2026-06-08

## Problem

After integrating the open PR fixes, code review found a recovery gap in the choice handlers. If a choice SSE request returned a non-2xx HTTP response before the browser created an SSE reader, `streamChoice` or `streamCustomChoice` rejected without invoking the SSE `onError` callback.

The hook catch block only logged the rejection, so the UI could remain in the choosing/processing state without invoking the existing fallback recovery path.

## Root Cause

The previous patch intentionally swallowed stream rejections after `onError` started handling fallback recovery. That was correct for reader/network errors emitted by `parseSSEStream`, but it also swallowed pre-SSE HTTP errors that never reached `onError`.

## Fix

- Added an `errorHandled` guard in `useChoiceHandler`.
- SSE `onError` marks the error as handled before running `handleChoiceError`.
- The outer catch now calls `handleChoiceError` only when no SSE `onError` path has handled the failure.
- The guard prevents duplicate fallback handling for errors that already came through SSE parsing.

## Regression Coverage

Added a Jest test covering three retried `502` responses followed by the existing synchronous choice recovery endpoint. The test asserts that fallback is called, recovered story text is rendered, and the UI enters the result phase.

## Verification

- `cd frontend && npx jest src/__tests__/hooks/useChoiceHandler.test.ts --runInBand`
- Full gate rerun required after this patch because it changes final `main`.
