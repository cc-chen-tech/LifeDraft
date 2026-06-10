## MODIFIED Requirements

### Requirement: Gameplay date labels follow the saved era year
Gameplay date labels generated from player state SHALL use the player's saved
era year instead of falling back to a hard-coded modern default when an explicit
year is recoverable from the era setting.

#### Scenario: Era year is stored in text fields
- **Given** a player state has no numeric `character_settings.era.year`
- **And** `era_name`, `era_description`, or `world_context` contains an explicit
  year such as `2026`
- **When** the game computes date information for summaries or history labels
- **Then** the computed year SHALL be `2026`
- **And** the date string SHALL start with `2026年`.

#### Scenario: Era has no explicit year
- **Given** a player state has no explicit year in any era field
- **When** the game computes date information
- **Then** the existing 2024 fallback MAY be used.
