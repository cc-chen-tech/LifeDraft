## Context

The images router exposes persisted assets and scene records through game-owned
queries. These handlers can be called directly with a real SQLite session.

## Goals / Non-Goals

**Goals:** Verify asset field payloads, soft deletion, ownership, and
week/stage scene identity.

**Non-Goals:** Trigger generation, call storage providers, or alter routes.

## Decisions

- Call endpoint functions directly with real model rows and integer user IDs.
- Test read paths only where stored rows short-circuit auto-generation.

## Risks / Trade-offs

- [Router dependencies] -> Pass concrete session and user values directly.
