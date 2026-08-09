## ADDED Requirements

### Requirement: Generation repair inherits the originating budget
Consistency rewrite, regeneration, and truncation continuation SHALL inherit the originating narrative budget, tracker, and deadline rather than using fixed token limits or independent retry loops.

#### Scenario: Consistency repair is requested
- **WHEN** Harness or deterministic validation requests a story repair
- **THEN** the repair call SHALL consume the request's remaining prose allowance
- **AND** it SHALL use the request's output-token ceiling
- **AND** exhaustion SHALL preserve the latest complete story instead of converting length or repair drift into an empty terminal result.

#### Scenario: Recovery is disabled by rollout flag
- **WHEN** `ENABLE_UNIFIED_NARRATIVE_BUDGETS` is false
- **THEN** the stable compatibility path SHALL remain callable
- **AND** stored story and API response schemas SHALL remain unchanged.
