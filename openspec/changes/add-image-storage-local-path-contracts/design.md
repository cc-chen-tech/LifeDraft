## Context

Image records persist paths for locally generated assets. Both current relative
paths and historical absolute paths must remain readable through the storage
service and image API URL builder. Existing coverage uses patched settings and
methods, while the maintained gate accepts only deterministic no-mock tests.

## Goals / Non-Goals

**Goals:** exercise local path conversion, URL construction, filesystem
read/existence/delete lifecycle, and content hashing with a real `tmp_path`.

**Non-Goals:** invoke image compression, generate random filenames, initialize
an OSS client, call a provider, or modify production code.

## Decisions

- Construct `ImageStorageService` with explicit `storage_type="local"` and
  `local_path=tmp_path`, so settings are not patched and each test has an
  isolated filesystem.
- Assert externally visible behavior for both a relative file and a historical
  absolute file. This covers the compatibility branches without relying on
  implementation-private substitutions.
- Keep a missing-file read and repeated delete assertion to preserve error and
  idempotency semantics.
- Add the suite at the same ordered location in both maintained workflows after
  passing direct coverage, hygiene, workflow parity, and the full gate.

## Risks / Trade-offs

- [Filesystem semantics vary by host] → Limit assertions to `tmp_path` creation,
  byte content, and standard `Path` behavior.
- [More maintained tests increase gate duration] → Keep the suite synchronous,
  local, and provider-free.
