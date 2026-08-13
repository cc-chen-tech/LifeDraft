# Harden Story Voice Concurrency Contracts

## Why

Story voice playback has asynchronous runtime-settings loading and browser-speech
fallback. A newer reading request must remain authoritative when an older request
resumes, and long browser-speech text must complete through every chunk.

## What Changes

- Add store-level regression tests for shared runtime-settings loading across
  overlapping reading attempts.
- Add a browser-speech chunk completion test that exercises the real store
  lifecycle without a browser-agent dependency.

## Scope

This change adds tests and OpenSpec artifacts only. It does not change production
behaviour or existing tests.
