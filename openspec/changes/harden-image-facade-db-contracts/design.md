## Context

The image facade selects active assets, derives character metadata, and reads
stored files. These branches can be exercised with persisted image rows and a
temporary local storage root.

## Goals / Non-Goals

**Goals:** Verify active-image selection, structured character metadata, and
stored-image fallback behavior without providers.

**Non-Goals:** Generate images, invoke external storage, or alter service code.

## Decisions

- Construct the facade with real SQLite sessions and local storage service.
- Assert public helper outputs and stored records, not provider implementation.

## Risks / Trade-offs

- [Local file behavior] -> Keep all media under pytest temporary directories.
