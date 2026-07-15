## Context

`ImageGenerator` translates MiniMax HTTP and payload failures into typed, safe exceptions. These paths are deterministic when a local recording session replaces the HTTP client.

## Goals / Non-Goals

**Goals:** cover content-inspection parsing, invalid JSON, and download HTTP classification without network calls or mocks.

**Non-Goals:** retry timing, remote provider availability, or production code changes.

## Decisions

- Use small fake responses with fixed status, JSON behavior, and bytes.
- Assert exception type, category, retryability, operation-specific code, and original prompt where applicable.

## Risks / Trade-offs

- [Fakes differ from requests internals] → tests exercise the public session boundary and all service-owned branching.
