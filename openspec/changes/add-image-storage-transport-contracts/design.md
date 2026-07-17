## Context

Image storage has deterministic local and OSS transport paths not covered by
the maintained gate.

## Goals / Non-Goals

**Goals:** Verify object storage save/read/url/delete/exists behavior without a network.

**Non-Goals:** Change production storage behavior or install OSS dependencies.

## Decisions

- Use a recording in-memory client through a storage subclass to exercise the
  real storage service transport methods without mocks.

## Risks / Trade-offs

- [Fake client diverges from SDK] → Assert only the adapter calls and values
  owned by this service.
