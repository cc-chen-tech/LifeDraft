## Context

The scene service already has helper contracts, but the early real-persistence branch that returns a valid saved scene is not in the maintained gate. It is deterministic with SQLite and a temporary local storage root.

## Goals / Non-Goals

**Goals:** Verify saved scene reuse and persisted appearance-anchor recovery without provider calls.

**Non-Goals:** Generate or edit images, invoke external image clients, or test missing-file regeneration.

## Decisions

- Use an isolated SQLite database and `ImageStorageService` rooted in `tmp_path`.
- Seed a valid `SceneImage` and assert the service returns it before analysis/generation.
- Seed an `Image` metadata anchor and assert the recovered anchor contributes to the manifest.

## Risks / Trade-offs

- [Does not cover provider generation] -> The test deliberately locks the no-provider cache-hit boundary that prevents duplicate generation.
