## Context

`useSceneImageStore` translates EventSource messages into scene-image state
used by the gameplay UI. Route and polling tests cannot reliably cover browser
event delivery branches. The store is a deterministic boundary when EventSource
is replaced with a minimal fake implementation.

## Goals / Non-Goals

**Goals:**
- Verify ready events update the matching stage and replace duplicate scene
  keys.
- Verify terminal failures expose retryable UI state without mutating images.
- Verify heartbeats are state no-ops and reconnect lifecycle closes old
  resources.

**Non-Goals:**
- Test a real browser EventSource connection, backend stream transport, or
  image generation providers.
- Change the store's EventSource URL, payload, or retry policy.

## Decisions

- Use a fake EventSource that captures handlers rather than mocking the store.
  This exercises the public subscribe/unsubscribe API and actual message
  parsing paths.
- Reset the Zustand store per test and assert visible state only. This prevents
  module-level request state from leaking across tests.
- Keep all messages synchronous; no timers or network calls are needed for
  these state transitions.

## Risks / Trade-offs

- [Fake EventSource differs from browser implementation] -> retain existing
  Playwright coverage for real connectivity while using these tests to pin
  deterministic state behavior.
- [Module-level failure tracking can outlive a test] -> each test drives a
  ready event or explicit cache cleanup before the next test.
