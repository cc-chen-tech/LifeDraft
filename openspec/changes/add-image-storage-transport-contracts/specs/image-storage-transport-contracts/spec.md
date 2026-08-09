## ADDED Requirements

### Requirement: Image storage transport is maintained
The maintained suite SHALL verify storage returns stable paths, URLs, bytes,
existence, and deletion results for supported object storage operations.

#### Scenario: Object storage lifecycle
- **WHEN** an image is saved, read, addressed, checked, and deleted through an
  object-storage client
- **THEN** each operation uses the stable object key and returns its expected result
