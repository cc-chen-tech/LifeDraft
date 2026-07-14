## ADDED Requirements

### Requirement: Maintained style-manifest contract coverage
The maintained backend workflows SHALL execute
`tests/test_narrative_style_manifest.py` in identical ordered selections.

#### Scenario: Local style data behavior
- **WHEN** a maintained backend workflow runs
- **THEN** it validates manifest serialization and isolated local loader,
  cache, reload, and malformed-input behavior without an external provider.

#### Scenario: Ordered workflow parity
- **WHEN** the maintained coverage and backend-test selections are parsed
- **THEN** both lists include the StyleManifest suite in the same position.

### Requirement: Verified coverage milestone
The promotion SHALL retain the current coverage threshold unless the complete
maintained selection passes at the proposed next integer threshold.

#### Scenario: Threshold promotion
- **WHEN** the complete promoted selection passes a 51% coverage command
- **THEN** the maintained workflow threshold is updated to 51%.

#### Scenario: Threshold retention
- **WHEN** the 51% coverage command does not pass
- **THEN** the maintained workflow threshold remains at its previously verified
  value.
