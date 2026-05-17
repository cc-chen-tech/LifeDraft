## Context

The backend now exports OpenAPI schema and generated frontend types, while the frontend still uses a mix of generated aliases, hand-written `frontend/src/lib/types.ts` interfaces, API wrapper annotations, and Jest/Playwright mock payloads. Earlier browser-agent regressions showed that route existence, response field names, and stream event payloads can drift independently.

## Goals / Non-Goals

**Goals:**
- Fail fast when critical backend response fields are absent from generated schema, hand-written frontend types, or high-use mocks.
- Treat repaired field mismatches as hard contracts rather than warning-only documentation.
- Cover SSE event payloads that OpenAPI cannot model well.
- Keep the gate lightweight enough for maintained/preflight runs.

**Non-Goals:**
- Migrate every frontend import to generated OpenAPI types in this change.
- Generate TypeScript runtime validators.
- Add browser E2E coverage for every field contract; these tests should run before E2E.

## Decisions

- Use backend pytest contract tests for cross-language field checks. They can read backend Pydantic schemas, OpenAPI JSON, frontend TypeScript source, and frontend test fixtures without starting a browser.
- Keep generated OpenAPI artifacts checked in and gate them with existing CI diff checks. This change adds assertions that critical paths and schemas are present, rather than replacing the generator.
- Validate a curated set of high-risk surfaces first: game state, choice sync, character setting, collection, round scene images, and SSE scene-image/gameplay payloads. This avoids a brittle whole-repo parser while covering known regression areas.
- Prefer hard string/source assertions for hand-written TypeScript interfaces until the frontend fully migrates to generated type aliases.

## Risks / Trade-offs

- Source assertions can become brittle if TypeScript formatting changes. Mitigation: assert narrow field tokens and interface names rather than entire blocks.
- OpenAPI cannot express all SSE payload fields. Mitigation: add dedicated stream payload builders/fixtures tests against emitted JSON.
- Mock scanning can miss inline one-off mocks. Mitigation: start with reusable fixtures and known high-use test files, then expand when new regressions are found.
