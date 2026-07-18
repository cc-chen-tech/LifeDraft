# Harden Choice Handler Recovery Contracts

## Why

Choice SSE streams can retry after emitting partial story, or finish with a
terminal payload rather than a story chunk. Both transitions should be verified in
the hook before a browser flow discovers duplicate or missing text.

## What Changes

- Add hook integration tests driven by the real SSE parser fixture.
- Cover retry replacement and custom-choice complete-only story fallback.

## Scope

This change adds frontend tests and OpenSpec artifacts only.
