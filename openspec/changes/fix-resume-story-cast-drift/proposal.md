# Fix Resume Story Cast Drift

## Why

The story generation path now injects preset cast authority and validates newly generated stories, but the round resume path could still reuse a persisted current-round story and generate options only. If that persisted story already drifted away from preset people, the game would continue the bad story instead of regenerating it.

## What Changes

- Validate resumed current-round story text with the same quick story constraints used after generation.
- Reject resumed stories that ignore preset key people, introduce replacement relationship networks, contain meta leakage, or violate era constraints.
- Fall through to normal round generation when a resumed story fails validation.

## Impact

- Backend gameplay recovery only: `RoundEventGenerator` resume mode.
- No API schema change.
- Preserves fast options-only resume for valid persisted stories.
