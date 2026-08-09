## Context

`SceneImageService` coordinates provider output, local storage, and a unique
`SceneImage` row. Provider-level tests do not prove that a successful local
result is readable from the database, and mock-heavy tests can miss a rollback
that leaves a partial row after a provider exception.

## Goals / Non-Goals

**Goals:**
- Use the real SQLite test fixture and a temporary `ImageStorageService` path.
- Use a local provider fake with no network access.
- Verify stored row fields, file delivery, and provider failure rollback.

**Non-Goals:**
- Test external provider HTTP behavior.
- Change provider retries, image prompts, or production code.

## Decisions

- Seed a real `Game` because scene rows carry a game foreign key.
- Test the scene subservice directly: it owns the write transaction while the
  `ImageService` facade delegates to it.
- Assert the package-level typed service error rather than a provider-specific
  implementation detail.

## Risks / Trade-offs

- Temporary local storage confirms application delivery semantics but does not
  exercise an object-store deployment adapter.
