## ADDED Requirements

### Requirement: Character initialization normalizes deterministic settings
Maintained backend contracts SHALL verify era alignment, family-name normalization, and rule-based attributes without providers, mocks, random patches, databases, or timing dependencies.

#### Scenario: Life vision conflicts with generated era
- **WHEN** a modern or explicitly classical life vision conflicts with an era
  setting
- **THEN** normalization MUST return an aligned era profile and preserve the
  appropriate bounded year

#### Scenario: Initial settings contain placeholder names or extreme traits
- **WHEN** family names contain player placeholders or rule-based traits imply
  changed initial attributes
- **THEN** normalization MUST preserve valid member data and return bounded
  initial attributes
