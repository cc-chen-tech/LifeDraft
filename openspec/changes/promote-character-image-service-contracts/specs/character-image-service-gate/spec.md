## ADDED Requirements

### Requirement: Character image contracts run in maintained tests
The maintained test suite SHALL execute the provider-free character image
service contracts against a real database session.

#### Scenario: Maintained image service run
- **WHEN** a maintained backend workflow executes
- **THEN** it MUST execute the character image service contract file
