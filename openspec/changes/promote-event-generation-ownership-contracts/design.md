## Context

The maintained backend workflows currently select 52 deterministic test files and enforce a 44 percent source coverage floor. `tests/test_event_generation_contract.py` covers the in-memory coordinator that serializes event-generation producers, preserves replay semantics, and reports failures, but it is outside those selections.

## Goals / Non-Goals

**Goals:**
- Make coordinator ownership and SSE error framing regressions fail in the maintained gate.
- Preserve exact path-list parity across the two maintained workflows.
- Keep the coverage floor evidence-based.

**Non-Goals:**
- Test provider-backed round generation in this fast gate.
- Change event generation behavior, concurrency primitives, or test implementations.
- Replace release-only end-to-end validation.

## Decisions

- Promote the operation contract suite because it exercises concurrent claims, replacement after failure, completed-operation reuse, and replay in-process. These are deterministic state-machine invariants with a high gameplay failure impact.
- Do not include provider or background-thread suites in this batch because their test doubles and timing behavior violate the maintained-gate constraints.
- Append one test path identically to both workflow lists and retain the existing floor unless measured coverage reaches the next integer.

## Risks / Trade-offs

- [Thread scheduling could expose rare flakiness] -> Run the suite twice before promotion and use its bounded executor test rather than timing assertions.
- [The suite has narrow source scope] -> Treat the 99 percent operation-module result as a focused contract signal, not evidence that all event generation is covered.
- [Workflow selections diverge] -> Normalize and diff both lists before committing.
