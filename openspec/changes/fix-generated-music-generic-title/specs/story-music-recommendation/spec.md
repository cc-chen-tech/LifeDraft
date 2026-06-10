## ADDED Requirements

### Requirement: Generated AI music titles hide generic scene labels

Generated AI music tracks SHALL NOT expose generic internal scene labels as their user-facing title when better context is available.

#### Scenario: New generated track receives a generic scene type
- **GIVEN** MiniMax music generation receives a brief with `scene_type` equal to a generic narrative label such as `叙事` or `日常过渡`
- **AND** the brief includes an environment and mood
- **WHEN** the generated track is returned to the playlist
- **THEN** the track title SHALL use the environment and mood
- **AND** the track title SHALL NOT be `AI MiniMax 叙事` or `AI MiniMax 日常过渡`

#### Scenario: Reused local AI music receives a generic scene type
- **GIVEN** a ready local AI music library asset is reused for a new game
- **AND** the current brief has a generic narrative scene type with environment and mood context
- **WHEN** the reused track is inserted into the playlist
- **THEN** the reused track title SHALL use the current brief environment and mood
- **AND** the reused track title SHALL NOT expose the generic scene label.
