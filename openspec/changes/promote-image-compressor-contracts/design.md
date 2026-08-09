## Context

The existing test uses real in-memory PIL images and no mocks, providers, or persistent state.

## Goals / Non-Goals

**Goals:** Promote full image-compressor branch coverage in both maintained workflows.

**Non-Goals:** Change compressor behavior or use mocks, skips, random input, environment mutation, or external network access.

## Decisions

- Append the existing contract to both identical workflow selections.

## Risks / Trade-offs

- [Small global increment] -> Removes a complete low-cost utility blind spot.
