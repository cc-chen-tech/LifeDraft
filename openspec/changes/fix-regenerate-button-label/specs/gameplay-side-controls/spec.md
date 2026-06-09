## ADDED Requirements

### Requirement: Regenerate And Rewrite Controls Use Distinct Labels
Gameplay side controls SHALL label full story regeneration as "重新生成" and rewrite-sheet editing as "改写" so the two actions remain visually distinct.

#### Scenario: Collapsed ChatBar exposes regenerate and rewrite actions
- **WHEN** the ChatBar is collapsed and a current story exists
- **THEN** the regenerate quick action MUST be labeled "重新生成"
- **AND** the rewrite quick action MUST be labeled "改写"
- **AND** clicking "重新生成" MUST invoke the regenerate callback
- **AND** clicking "改写" MUST open the rewrite sheet
