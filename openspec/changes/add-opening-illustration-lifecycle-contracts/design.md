## Context

`SceneImageService` owns opening-illustration replacement and regeneration. The maintained suite covers scene constraints and helper formatting, but not the persisted lifecycle that frontend opening-story views consume.

## Goals / Non-Goals

**Goals:**
- Exercise lifecycle behavior with a real test database and deterministic image-client and storage fakes.
- Assert replacement, reference-source precedence, and persisted metadata through the public service methods.

**Non-Goals:**
- Call a remote image provider, write files, alter production code, or cover unrelated round-scene generation.

## Decisions

- Use small recording fakes rather than mocks so each assertion reflects the service boundary passed to the provider and storage layers.
- Use `ImageModel` records in the existing test database to verify inactive old records and active newly persisted records.
- Cover both reference paths: current illustration bytes take precedence; absent current bytes fall back to the supplied player image callback.

## Risks / Trade-offs

- [Fakes do not prove a provider response is visually valid] → Provider integration remains outside deterministic maintained coverage.
- [Database fixture schema differs from deployment database] → Assertions use model fields and public methods already shared by application code.
