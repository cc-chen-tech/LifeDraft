## ADDED Requirements

### Requirement: Preset people are authoritative story cast
The system SHALL treat `character_settings.relationships.key_people` as authoritative setup facts for story generation, including each preset person's name, role, relationship, and description.

#### Scenario: Round prompt includes required people
- **WHEN** a round story prompt is built for a game whose settings include key people `陆昊然`, `陈晓雨`, and `林一凡`
- **THEN** the prompt SHALL include a required-cast section containing all three names
- **AND** the section SHALL include each person's role or relationship to the protagonist.

#### Scenario: Story generation validates required people coverage
- **WHEN** a generated story omits all required preset people during an early active round
- **THEN** validation SHALL fail with a cast-coverage issue
- **AND** retry guidance SHALL explicitly require introducing one or more missing preset people by canonical name.

### Requirement: Invented substitutes do not replace canonical preset people
The system SHALL not accept an invented character as a replacement for a preset person when the invented character uses the preset person's relationship or role.

#### Scenario: Friend substitute is detected
- **WHEN** the preset includes `陈晓雨` as a close friend
- **AND** generated story or extracted entities introduce `苏婉清` as the close friend while `陈晓雨` is absent
- **THEN** validation or canonicalization SHALL flag the drift
- **AND** downstream entity collection SHALL preserve `陈晓雨` as the canonical key person.

#### Scenario: Existing canonical person wins during extraction
- **WHEN** entity extraction returns a new person whose role/relationship matches a missing preset key person
- **THEN** collection synchronization SHALL map that candidate to the preset person's canonical name
- **AND** it SHALL not add a duplicate substitute person to `relationships.key_people`.

### Requirement: Preset relationships survive save and read
The system SHALL preserve key people and relationship metadata from game creation through persisted game state and subsequent gameplay recovery.

#### Scenario: Real DB game initialization preserves key people
- **WHEN** a game is created with three preset key people
- **THEN** the saved initial state SHALL contain all three key people under `character_settings.relationships.key_people`
- **AND** the loaded `PlayerState` SHALL expose relationship affinity entries for those names.
