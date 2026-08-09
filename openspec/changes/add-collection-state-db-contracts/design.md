## Context

Collection deletion is a consistency boundary: the in-memory PlayerState and
the database Image rows must change together. The candidate tests use the
repository's in-memory SQLite fixture and do not invoke image generation or
storage providers.

## Goals / Non-Goals

**Goals:**
- Verify URL-decoded collection deletion removes state and related DB rows.
- Verify manual item validation and character regeneration authorization.

**Non-Goals:**
- Test external image generation, image storage, or router authentication.
- Change collection behavior or pre-existing tests.

## Decisions

- Create only the minimal Game and Image rows required for real SQLAlchemy
  deletion queries.
- Use PlayerState dictionaries for deterministic input and no mock framework.
- Promote only after direct coverage and the full 51% maintained gate pass.

## Risks / Trade-offs

- [SQLite misses production SQL behavior] → Tests cover ORM filters and
  commits, while broader integration tests remain separate.
- [Provider construction has side effects] → Tests call only methods that do
  not invoke ImageService or ImageStorageService.
