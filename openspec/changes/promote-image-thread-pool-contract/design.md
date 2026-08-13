## Context

`src.services.image_service` exposes a global `ThreadPoolExecutor` helper. The existing test calls the real helper, validates executor replacement after shutdown, and leaves a usable pool for subsequent work. The maintained workflows use ordered identical selections.

## Goals / Non-Goals

**Goals:**

- Promote the deterministic lifecycle contract in both maintained workflows.
- Preserve the test-selection ordering and verify the complete maintained suite.

**Non-Goals:**

- Change executor sizing, image provider behavior, or image generation logic.
- Use a mocked executor or provider.
- Raise the coverage threshold without a strict candidate result.

## Decisions

- Promote the existing real-helper test because it verifies resource ownership directly and introduces no provider dependency.
- Append it at the end of both workflow selections so executor shutdown cannot affect earlier selected tests.
- Retain the current threshold unless the full maintained suite passes an exact next-threshold candidate.

## Risks / Trade-offs

- [Global executor state could affect later tests] -> Run this selection last and have its final assertion recreate a usable pool.
- [Lifecycle coverage can overlap existing imports] -> Count promotion as reliability coverage; use exact full-suite coverage results for gate changes.
