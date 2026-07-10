## Why

Production QA observed that the opening-story start button becomes actionable while the typewriter display still ends mid-sentence. The backend stream may be complete, but navigation must not let users skip text that has not yet become visible.

## What Changes

- Track completion of the visible typewriter text independently from SSE completion.
- Keep `开始我的人生` disabled and out of the ready state until both the final story payload and visible rendering are complete.
- Reset visible completion on retry and on every new stream attempt.
- Add no-mock component and browser coverage for the completion boundary and register it in `test.sh`.

## Capabilities

### New Capabilities
- `opening-visible-completion`: Defines when opening-story navigation becomes available relative to streamed and visibly rendered text.

### Modified Capabilities

## Impact

- `StreamingText` completion callback contract.
- Opening story page state and start-button readiness.
- Focused Jest and Playwright regression tests.
- `test.sh` E2E registration.
