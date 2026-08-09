## ADDED Requirements

### Requirement: Maintained gate protects recovered collection context
The maintained backend test selection SHALL run deterministic regressions for relationship-gated recognition, empty-whitelist story people, existing-entity filtering, and current gameplay prompt constraints.

#### Scenario: Recognition receives incomplete relationship metadata
- **WHEN** recovered gameplay text contains character-like fragments and eligible relationship metadata
- **THEN** the maintained contract MUST reject non-eligible fragments while retaining eligible story people

#### Scenario: Opening story is generated from recovered character settings
- **WHEN** the opening prompt receives a life vision and preset key people
- **THEN** the maintained contract MUST require those constraints to appear in the generated prompt
