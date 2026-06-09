# Fix Choice Sync Idempotency

## Why

Production QA found a recovery loop after a completed choice fallback. The first
`choice-sync` request completed server-side and saved the round result, but a
duplicate recovery request saw `current_event=None` and returned
`choice_already_processed`. The frontend then stayed around fallback/recovery UI
even though the latest result was already persisted.

## What Changes

- Make `choice-sync` and `custom-choice-sync` idempotent for already processed
  choices.
- When the current event is missing because the latest choice was already saved,
  return the latest persisted round result instead of a 400/422 recovery error.
- Keep streaming choice endpoints strict; this recovery behavior is scoped to
  non-streaming fallback endpoints.

## Impact

- Prevents duplicate mobile/browser fallback requests from trapping the player in
  recovery UI after a choice already completed.
- Adds no-mock real DB integration coverage for the save -> duplicate request ->
  restored response chain.
