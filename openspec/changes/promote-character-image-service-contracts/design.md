## Context

Character image service requests cross provider, storage, and persistence
boundaries. Existing tests substitute only the provider and storage edges
while exercising the real service and DB session.

## Goals / Non-Goals

**Goals:**
- Promote the verified deterministic suite unchanged.
- Verify it remains stable in two complete maintained runs.

**Non-Goals:**
- Calling an image provider or altering image generation behavior.
- Changing existing contract tests.

## Decisions

- Hand-written fakes are allowed because the file contains no mock framework
  imports or calls and real persistence remains exercised.
- Preserve workflow selection order parity and do not raise a threshold unless
  full-run evidence supports it.

## Risks / Trade-offs

- [Provider behavior is not exercised] -> This gate targets deterministic
  request, persistence, and error-mapping regressions; provider integration
  remains release-only coverage.
