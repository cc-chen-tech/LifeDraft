## Context

The collection router aggregates character settings, relationship effects, and unfinished current-story data before image or extraction services are invoked. Its most important deterministic behavior can be validated using real player state and the shared session store, avoiding provider-backed image and description generation.

## Goals / Non-Goals

**Goals:**
- Preserve authenticated user requirements and session player-state lookup behavior.
- Preserve first-seen entity names, current-story append rules, and URL-decoded existing-description responses.
- Keep test inputs real where the router depends on player/session models.

**Non-Goals:**
- Call image, item-extraction, or landmark-extraction providers.
- Change collection behavior or edit existing tests.
- Cover route branches that require a configured persistent database service.

## Decisions

- Construct real `GameLoop` and `PlayerState` objects and install them through `session_service`; remove their exact session identities in `finally`.
- Exercise existing-description branches because they are user-visible, provider-free commands that must not accidentally regenerate assets.
- Assert normalized field output and HTTP statuses rather than internal implementation details.

## Risks / Trade-offs

- [Session storage is shared] -> use unique IDs and cleanup in `finally`.
- [Provider-backed branches remain uncovered] -> leave them for dedicated integration tests with controlled providers.
- [Collection helpers accept legacy shapes] -> include malformed and structured shapes to preserve defensive behavior.

## Migration Plan

No migration is required. This test-only change can be reverted by removing the added module and workflow entries.
