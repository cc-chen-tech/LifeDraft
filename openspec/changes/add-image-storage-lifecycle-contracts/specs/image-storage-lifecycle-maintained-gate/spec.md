## ADDED Requirements

### Requirement: Local image storage lifecycle is maintained
The maintained backend workflows SHALL execute provider-free local image storage lifecycle contracts.

#### Scenario: Compression fallback persistence regression
- **WHEN** local image storage receives bytes that compression cannot decode
- **THEN** it preserves the original bytes under a stable relative path that remains readable and deletable.
