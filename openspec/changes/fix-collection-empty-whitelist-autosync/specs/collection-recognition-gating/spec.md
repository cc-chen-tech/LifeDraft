## ADDED Requirements

### Requirement: Empty Character Metadata Still Allows Clear Story People

Collection recognition SHALL NOT treat an empty eligible-character metadata list as a hard deny-list for deterministic fallback recognition.

#### Scenario: Story has named people but no relationship metadata

- **WHEN** accepted story text contains clear named people such as `马老板`, `方蕾`, `赵子豪`, and `王丽华`
- **AND** the backend has no eligible relationship metadata for those people
- **THEN** deterministic recognition MUST still return those people as character candidates
- **AND** existing protagonist names MUST NOT be duplicated.

#### Scenario: Relationship metadata is non-empty

- **WHEN** an eligible-character metadata list is present and non-empty
- **THEN** smart recognition MUST keep filtering character candidates to that eligible set
- **AND** text fragments such as `水门就` or family/shop names such as `魏家` MUST NOT be proposed as characters.

### Requirement: Collection Panel Auto-Sync Includes Later Story Characters

The collection panel SHALL run initial auto-recognition when the player collection only contains the protagonist, even if item and landmark collections are already populated.

#### Scenario: Existing item and landmark but new story character

- **WHEN** the collection panel opens with the protagonist, an existing item, and an existing landmark
- **AND** recent story recognition returns a new story character such as `方蕾`
- **THEN** the panel MUST add the recognized character to the collection
- **AND** the character tab count MUST update without requiring a manual smart-recognition click.
