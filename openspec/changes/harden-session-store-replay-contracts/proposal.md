## Why

Gameplay reconnect behavior relies on in-memory session state between an SSE
route and a database restore. Existing tests cover basic session creation but
do not lock down replay cache boundaries, story-specific option reuse, or the
owner-isolation lifecycle that prevents stale content being replayed.

## What Changes

- Add provider-free contract tests for SSE replay cache trimming and reset.
- Add deterministic tests for story-bound option cache and prefetch lifecycle.
- Add isolation and expiry-cleanup tests for per-user session store entries.
- Include the contract suite in the maintained backend test manifest.

## Capabilities

### New Capabilities
- `session-store-replay-contracts`: Deterministic contracts for reconnectable
  gameplay session state.

### Modified Capabilities

- None.

## Impact

Affected test code is `tests/test_session_store_replay_contracts.py` and the
maintained backend manifest. No API, persistence schema, or production
behavior changes.
