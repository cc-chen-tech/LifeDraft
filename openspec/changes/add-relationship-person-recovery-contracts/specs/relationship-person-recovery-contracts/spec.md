## ADDED Requirements

### Requirement: Relationship-person response normalization is maintained
The maintained backend suite SHALL verify that a valid relationship-person
response preserves its identity fields, maps `relationship_desc` to the legacy
`relationship` field, and supplies deterministic default state fields.

#### Scenario: Description-only relationship response succeeds
- **WHEN** the relationship generator returns a named person with a role and
  `relationship_desc` but no legacy relationship field
- **THEN** the returned person contains the mapped relationship and required
  default state fields

### Requirement: Relationship-person invalid-output recovery is maintained
The maintained backend suite SHALL verify that vague relationship output is
retried and repeated invalid output returns the documented usable fallback.

#### Scenario: Vague relationship text is retried
- **WHEN** the first response contains a forbidden vague relationship phrase
  and the next response is valid
- **THEN** the second response is returned after two generator calls

#### Scenario: Repeated invalid responses use Chinese fallback
- **WHEN** three relationship-person responses omit required identity fields
  in Chinese mode
- **THEN** the returned person has the indexed fallback name, friend role, and
  deterministic social-state defaults
