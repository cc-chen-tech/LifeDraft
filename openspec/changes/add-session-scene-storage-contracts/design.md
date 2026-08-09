## Context

The tests call `SessionService._check_recent_scene_images` with a real in-memory SQLAlchemy session and temporary local image storage. They avoid the global restore path, background timer, provider calls, and mocks.

## Goals / Non-Goals

**Goals:** Cover missing-scene marking and valid-scene preservation in both maintained workflows.

**Non-Goals:** Change session restoration, run image generation, or use mocks, skips, random input, environment mutation, or external network access.

## Decisions

- Test the explicit DB/storage helper boundary directly to keep asynchronous provider work outside the maintained gate.
- Raise the coverage threshold only after a strict full-suite candidate passes.

## Risks / Trade-offs

- [Private helper contract can change] -> It captures a persisted state invariant that must remain stable regardless of orchestration structure.
