## Context

`WorldModelUpdater` carries story facts between rounds in mutable dictionaries on `PlayerState`. The current tests cover several location and character paths, but the causal-chain test probes a method that does not exist and silently succeeds, so it does not protect the live `process_causal_updates` lifecycle.

## Goals / Non-Goals

**Goals:**

- Exercise live lifecycle methods with a real `PlayerState`, not a mock shape.
- Lock in the exact retention boundary for resolved causal chains and commitments.
- Verify causal data survives the normal state serialization boundary.

**Non-Goals:**

- Change lifecycle retention policy or implementation.
- Call external AI analyzers or exercise generated narrative quality.

## Decisions

- Test `process_causal_updates` directly because it is the production mutator; do not assert that an obsolete helper exists.
- Trigger cleanup with a harmless unmatched update because cleanup runs inside the updater's non-empty update path.
- Assert both the retained item at week 19 and its expiry at week 20, preventing an off-by-one regression.
- Use `PlayerState.to_dict()` / `from_dict()` between lifecycle steps to cover the actual save payload shape.

## Risks / Trade-offs

- [Retention policy intentionally changes] -> The test names and assertions identify the precise lifecycle boundary that must be consciously updated with the policy.
- [No database write in this test] -> This is a deterministic state-machine contract; repository persistence is covered separately by DB tests.
