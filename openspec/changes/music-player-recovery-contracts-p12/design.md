## Context

`MusicPlayer` owns a browser `Audio` instance and has recovery paths for both
the element `error` event and a rejected `play()` promise. Existing tests cover
queue advancement and algorithmic stall simulation, but do not assert these
paths through the rendered component and the real Zustand store.

## Goals / Non-Goals

**Goals:**
- Exercise browser-style `Audio` event handlers through `MusicPlayer`.
- Keep tests deterministic with a local Audio double and fake timers.
- Assert visible recovery feedback and selected-song state.

**Non-Goals:**
- Change playback behavior or error strings.
- Exercise a real browser media decoder or external music provider.
- Modify existing tests.

## Decisions

- Use an isolated test file with its own Audio double so it cannot alter the
  existing component suite's assumptions.
- Seed the real Zustand store with a recommendation and disable auto-fetch.
  This isolates playback recovery from recommendation and playlist HTTP calls.
- Advance the 800 ms retry timer explicitly so the failover behavior remains
  synchronous and deterministic in CI.

## Risks / Trade-offs

- jsdom cannot decode media, so the Audio double verifies the component's event
  contract rather than the browser media stack. Real playback remains an E2E
  concern.
