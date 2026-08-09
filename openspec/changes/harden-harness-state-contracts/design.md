## Context

Three pure harness validators are present but only covered through a conditional-import aggregate test module. The maintained suite needs focused tests whose imports and inputs are stable on every run.

## Goals / Non-Goals

**Goals:**
- Validate public APIs using real dictionaries and minimal `SimpleNamespace` world models.
- Cover invalid state/action combinations and explicit permitted/exempt paths.
- Preserve exact ordering parity across both maintained backend workflows.

**Non-Goals:**
- Change rule heuristics, travel semantics, validator implementation, or the legacy aggregate test file.
- Add provider, network, database, randomness, timing, mocks, or skips.

## Decisions

- Use a dedicated focused file instead of promoting the skip-capable aggregate suite.
- Keep inputs unambiguous: dead action, severe injury action, imprisonment action, overdue critical commitment, direct breach, remote movement, and fast-travel exemption.
- Use coverage runs twice before any floor ratchet, then validate once at the new floor.

## Risks / Trade-offs

- [Chinese regex heuristics can evolve] -> Assert structured status and branch results rather than incidental prose.
- [More maintained tests add runtime] -> The selected tests are pure in-process and add negligible runtime.
