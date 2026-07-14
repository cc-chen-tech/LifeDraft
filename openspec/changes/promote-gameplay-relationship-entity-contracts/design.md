## Context

The three selected suites exercise gameplay state transitions that historically surface during interactive sessions: recognition task lifecycle, deferred character introduction, and relationship event eligibility. They are deterministic and completed together in 168-test exploration without external interaction.

## Goals / Non-Goals

**Goals:**
- Add the verified gameplay-state suites to both maintained workflows.
- Detect queue, lifecycle, and relationship eligibility regressions before browser-level testing.

**Non-Goals:**
- Change gameplay implementation or existing test source.
- Expand the gate to providers, browser tests, or mock-based integration tests.

## Decisions

- Promote the three gameplay-facing suites together because they assert adjacent state authority: entity job state, NPC introduction state, and relationship event state.
- Keep image-only suites in a separate follow-up change to preserve coherent review and rollback boundaries.
- Use direct-suite execution, static hygiene, ordered workflow parity, and the full maintained gate as acceptance evidence.

## Risks / Trade-offs

- [Task-manager global state] → Each entity-recognition test resets manager state; validate it inside the full maintained order.
- [Character introduction timing behavior] → Retain its existing deterministic setup and avoid adding randomized coverage.
- [Workflow drift] → Extract and compare ordered lists before committing.
