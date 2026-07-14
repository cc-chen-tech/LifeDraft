## Context

The maintained backend gate contains 55 deterministic test files at a 45 percent floor. Fallback and scheduling contracts are provider-free pure logic suites that pass repeatedly and directly cover recovery events, time resolution, state transitions, merge rules, cleanup, and persistence-shaped round trips.

## Goals / Non-Goals

**Goals:**
- Bring recovery and scheduling regressions into the maintained fast gate.
- Preserve exact ordered workflow-list parity.
- Base any floor increase on the expanded suite's measured result.

**Non-Goals:**
- Change fallback text, time parsing behavior, or scheduling implementation.
- Replace real gameplay integration and browser coverage.
- Include tests with provider dependencies or framework mocks.

## Decisions

- Promote the two suites together because fallback events and scheduling are adjacent gameplay continuity mechanisms and both are deterministic.
- Append paths identically in both workflows to preserve the existing selection order.
- Keep the current 45 percent floor unless the full maintained run supports a higher integer; high local module coverage is not sufficient evidence by itself.

## Risks / Trade-offs

- [Automatic IDs vary internally] -> Tests assert stable observable shape rather than a generated value.
- [Pure logic misses persistence integration] -> The gate retains existing DB suites and this change does not claim to replace them.
- [Workflow lists diverge] -> Normalize and diff selections before commit.
