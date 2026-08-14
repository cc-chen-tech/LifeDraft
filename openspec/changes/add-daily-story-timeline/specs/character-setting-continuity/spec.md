## MODIFIED Requirements

### Requirement: Opening Story Uses Canonical Character Settings
Opening daily story generation SHALL use the structured character settings and selected exact start date as the source of truth.

#### Scenario: User creates a dated character premise
- **WHEN** character settings specify an era year and a valid start month and day
- **THEN** the saved start date and era year MUST agree and day-one generation MUST preserve the canonical premise and exact date

#### Scenario: Era year changes
- **WHEN** the user changes the era year during creation
- **THEN** the start date year and derived birth year MUST be synchronized while preserving a valid month and day

### Requirement: Subsequent Rounds Preserve Core Premise
Subsequent daily generation SHALL preserve the core character premise unless accepted player choices explicitly change it.

#### Scenario: Day two follows the opening
- **WHEN** the player selects an option on day one
- **THEN** day two MUST continue the premise using the protagonist identity, accepted choice, and applied effects from stored state
