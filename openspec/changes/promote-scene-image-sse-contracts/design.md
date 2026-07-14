## Context

The maintained backend workflows currently select 53 deterministic test files and enforce a 44 percent source coverage floor. The scene-image SSE contract suite uses the FastAPI application, authentication tokens, and the test database to exercise payload delivery and ownership checks. It passed twice in the isolated worktree without mocks, skips, or external service calls.

## Goals / Non-Goals

**Goals:**
- Add a real HTTP/database contract for scene-image update delivery to the maintained gate.
- Preserve ordered parity between the regular backend and coverage workflows.
- Keep the coverage threshold based on the measured full maintained selection.

**Non-Goals:**
- Cover provider-backed image generation or background worker scheduling.
- Change route or database behavior.
- Replace browser E2E validation of visual image rendering.

## Decisions

- Promote the SSE suite because it validates the boundary closest to frontend consumers: ready and failed event fields, authentication, and game ownership.
- Accept the suite's narrowly scoped 17 percent router coverage because the asserted security and payload behavior is high-risk; broad image-route coverage remains a separate effort.
- Keep fixed test game IDs because the suite creates and deletes them and passed twice in the isolated worktree; it remains unsuitable for parallelizing within a shared database.

## Risks / Trade-offs

- [Shared database fixture collides with another process] -> Run maintained tests in isolated worktrees/namespaces; the suite cleans up every game it creates.
- [Global SSE cache leaks state] -> Each test removes its injected cached event in `finally`.
- [Workflow selections diverge] -> Normalize and diff both path lists before commit.
