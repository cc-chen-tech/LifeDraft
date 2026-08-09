## ADDED Requirements

### Requirement: Content continuity contracts are deterministic
Maintained backend contracts SHALL cover item continuity and deterministic narrative-hint validators through public APIs with local text and state, without mocks, skips, providers, databases, randomness, or timing dependencies.

#### Scenario: Unavailable inventory item is used
- **WHEN** story text uses an item whose stored status is unavailable and it was not acquired earlier in the text
- **THEN** item continuity validation MUST return a failed result naming the missing item

#### Scenario: Narrative misses a configured hint
- **WHEN** long-form story text omits configured structure, arc, world-event, or conflict evidence
- **THEN** the corresponding deterministic narrative validator MUST return a failed result with structured details

#### Scenario: Narrative satisfies configured hints
- **WHEN** story text includes the required local hint evidence
- **THEN** the corresponding deterministic narrative validator MUST return a passing result
