# Fix Rewrite Progress Feedback

## Why

The 2026-06-09 production QA report found that the inline rewrite modal can remain on `正在改写中...` long enough to look stuck. The SSE client already exposes rewrite status events and retry callbacks, but the ChatBar ignored status messages and only repeated a static loading toast.

## What Changes

- Show rewrite SSE `status.message` text in the loading toast.
- Map known rewrite phases to useful fallback progress messages when the backend omits `message`.
- Show the same current progress inside the rewrite sheet with an `aria-live` region.
- Surface retry attempts as `连接中断，正在重试 X/Y`.
- Add a focused ChatBar regression test that manually streams rewrite progress events.

## Impact

- Frontend `ChatBar` rewrite progress UI.
- Frontend ChatBar regression coverage.
