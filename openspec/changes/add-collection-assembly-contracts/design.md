## Context

CollectionService combines player state and cached images into the response consumed by the frontend collection panels. Its list assembly is deterministic once image lookup is supplied.

## Goals / Non-Goals

**Goals:**
- Exercise the public collection response with player, NPC, key-person, family, item, landmark, and image-cache sources.
- Protect entity de-duplication and default frontend fields.

**Non-Goals:**
- Query a database, invoke image generation, or change collection behavior.

## Decisions

- Use a CollectionService subclass that returns a fixed per-type image cache and does not initialize external services.
- Exercise `get_collection` rather than isolated helper methods, because the response counts and source precedence form the frontend contract.

## Risks / Trade-offs

- [Cache behavior differs from database query behavior] → Cache lookup is already the service boundary; query behavior remains DB-test scope.
- [Response schemas gain fields] → Assert important fields and counts without requiring full model serialization equality.
