## MODIFIED Requirements

### Requirement: Collection Panel Auto-Sync Includes Later Story Characters

The collection panel SHALL run initial auto-recognition when the player collection only contains the protagonist, even if item and landmark collections are already populated.

#### Scenario: Existing item and landmark but new story character

- **WHEN** the collection panel opens with the protagonist, an existing item, and an existing landmark
- **AND** recent story recognition returns a new story character such as `方蕾`
- **THEN** the panel MUST add the recognized character to the collection
- **AND** the character tab count MUST update without requiring a manual smart-recognition click.

#### Scenario: Real play page collection button auto-adds current story character

- **WHEN** the player is on the real `/play` page with a current story containing a new character such as `赵掌柜`
- **AND** the player clicks the visible `收集` button
- **THEN** the frontend MUST call collection recognition and add-entities for the active game
- **AND** the collection dialog MUST refresh and display `赵掌柜`
- **AND** the character count MUST reflect the newly collected character without requiring a manual smart-recognition click.
