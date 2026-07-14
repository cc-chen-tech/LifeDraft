## Context

The tests use concrete PlayerState and explicit image caches, avoiding database and provider access.

## Goals / Non-Goals

**Goals:** gate collection identity, compatibility, and cached-image regressions.

**Non-Goals:** change production code or existing tests.

## Decisions

- Exercise pure service helpers through an uninitialized service instance.

## Risks / Trade-offs

- [Workflow drift] → verify ordered parity and full maintained execution.
