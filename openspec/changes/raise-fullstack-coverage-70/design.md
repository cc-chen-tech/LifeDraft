## Context

At the current `main` baseline, Jest has 1,816 passing tests and meets 70% for
each global metric (78.75% lines, 77.87% statements, 71.32% functions, and
72.16% branches). The maintained Python selection has 243 passing tests but
reports 31.87% statement coverage across all `src`. The mismatch arose because
the backend gate selects stable regression tests, while its coverage command
still measures the entire backend source tree.

The repository also has a full backend suite with historical failures. A
coverage change must not hide those failures by expanding a maintained list
with provider-dependent, order-sensitive, or skipped tests.

## Goals / Non-Goals

**Goals:**
- Enforce the already-proven frontend 70% floor for all four Jest measures.
- Add only new, deterministic tests for high-risk backend behavior and
  frontend runtime paths below the target.
- Keep the two maintained backend workflow selections byte-for-byte equivalent
  in test-file membership.
- Measure every backend batch against the full `src` denominator and record
  the exact result before changing any backend threshold.

**Non-Goals:**
- Reaching 70% full-backend `src` coverage in one change.
- Modifying production behavior, existing tests, or excluding source files to
  inflate a metric.
- Treating mocked providers, browser-agent checks, or legacy full-suite
  failures as stable maintained coverage.

## Decisions

### Separate frontend and backend claims

The frontend has already crossed the requested floor; its configuration can
therefore enforce 70% immediately. The backend is roughly 8,880 covered
statements short of 70% at its current 23,293-statement denominator. A single
test-only branch large enough to close that gap would be unreviewable and
would duplicate system behavior. The backend progresses through small
domain-focused batches and only raises a floor after repeated evidence.

Alternative considered: set a global backend 70% threshold now. Rejected,
because it would fail every current run and provide no actionable regression
signal.

### Prefer contract and state tests over broad mock scripts

Each backend batch will instantiate concrete state or use a real lightweight
database fixture where it exercises a persisted contract. External AI,
network, image generation, and background work will not be selected for the
maintained gate until a deterministic boundary exists. This focuses coverage
on identity, response shape, retry/fallback, and state-transition defects that
previously escaped into browser-agent testing.

Alternative considered: mock every collaborator to unit-test private methods.
Rejected for maintained coverage because mock topology can raise statements
without proving integration semantics.

### Ratchet only with repeatable evidence

Candidate tests run twice in the workflow environment. They are promoted to
both backend workflow selections together only when both runs pass without
skip, xfail, provider, network, or timing dependencies. A backend threshold is
raised only when two full measurements meet the next integer floor.

## Risks / Trade-offs

- [Risk] High-risk modules contain provider and thread boundaries that make
  deterministic coverage difficult. → Mitigation: target pure transforms,
  explicit fallback branches, and real DB contracts first; document a failing
  production contract separately instead of changing behavior here.
- [Risk] Frontend test additions can create slow, brittle DOM fixtures. →
  Mitigation: target stores and component state transitions with existing
  Testing Library patterns before adding browser E2E coverage.
- [Risk] Backend coverage can appear better by narrowing `collectCoverage` or
  `--cov` scope. → Mitigation: retain `--cov=src` and report the total
  denominator on every validation run.

## Migration Plan

1. Add the frontend 70% threshold and run the full Jest coverage suite.
2. Add and validate one backend domain batch at a time, preserving workflow
   parity and recording both targeted and maintained results.
3. Raise the backend floor only when two maintained measurements support it;
   otherwise retain the prior stable floor and continue with the next domain.
4. Run the full backend suite only during the main-release integration flow,
   following the repository policy, and triage legacy failures separately.

## Open Questions

- Which high-risk backend domain gives the best statement-to-maintenance-value
  ratio after the first world-model/collection/illustration exploration?
- Whether the next backend floor should be a global percentage or a domain
  floor once the maintained selection has meaningful representation across
  gameplay, collection, session, and image paths.
