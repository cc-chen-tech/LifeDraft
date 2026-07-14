## ADDED Requirements

### Requirement: Local paths remain compatible
The maintained backend gate SHALL verify that local image storage resolves both
relative persisted paths and legacy absolute paths, and produces an API URL
with non-ASCII path segments encoded.

#### Scenario: Relative and legacy paths resolve
- **WHEN** a local image is addressed with a relative path and then its absolute
  path
- **THEN** the service SHALL resolve and retrieve the same stored bytes

#### Scenario: Local API URL encodes a Chinese path segment
- **WHEN** a local image path contains Chinese characters
- **THEN** the service SHALL return an API image URL with its path segment URL
  encoded while retaining path separators

### Requirement: Local image lifecycle is deterministic
The maintained backend gate SHALL verify existence, deletion, missing-file
handling, and hashing without external storage dependencies.

#### Scenario: Deletion is idempotent
- **WHEN** a local image is deleted twice
- **THEN** the first deletion SHALL succeed and the second SHALL return false

#### Scenario: Missing local image cannot be read
- **WHEN** the service reads a nonexistent local path
- **THEN** it SHALL raise `ImageStorageError`

#### Scenario: Image bytes receive a stable SHA-256 hash
- **WHEN** fixed image bytes are hashed
- **THEN** the service SHALL return their expected SHA-256 digest
