## Context

ImageStorageService handles local persistence independently of image providers. It assigns user-visible round coordinates to paths and falls back to original bytes when compression rejects malformed input.

## Goals / Non-Goals

**Goals:** gate local save, fallback persistence, retrieval, and deletion using a real temporary directory.

**Non-Goals:** contact OSS or an image provider, or change storage behavior.

## Decisions

- Use `tmp_path` with the production local storage service.
- Deliberately use invalid image bytes to cover the documented compression-fallback behavior without fixtures or mocks.

## Risks / Trade-offs

- [Filesystem isolation] -> every test owns its temporary directory.
- [Workflow drift] -> validate ordered workflow parity and the full maintained gate.
