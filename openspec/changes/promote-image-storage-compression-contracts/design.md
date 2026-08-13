## Context

The existing contract uses real PIL images and pytest temporary directories to exercise `ImageStorageService` compression, readback, resizing, and URL generation. It has no provider, mock, or persistent database dependency.

## Goals / Non-Goals

**Goals:** Promote this deterministic storage contract in both maintained workflows with exact selection parity.

**Non-Goals:** Change image storage behavior, access external services, or add mocks, skips, random input, or environment mutation.

## Decisions

- Promote the existing real-filesystem contract because it covers a high-risk storage boundary more faithfully than a mocked service test.
- Keep the threshold unchanged unless the full maintained suite passes a strict next-threshold candidate.

## Risks / Trade-offs

- [PIL encoding differs by platform] -> Assertions use stable semantic properties: valid image, dimension limit, and size reduction.
