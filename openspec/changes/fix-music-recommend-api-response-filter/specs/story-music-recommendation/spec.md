## ADDED Requirements

### Requirement: Music recommendation API filters final response songs

The music recommendation API SHALL apply the structured story music brief as a final response safety net before resolving playback URLs.

#### Scenario: Dirty service output is filtered at the API boundary

- **WHEN** `POST /api/music/recommend` receives recommendation songs that include known vocal-pop title families or Anime/ACG opening metadata
- **AND** the recommendation includes a `music_brief` whose negative cues request no vocals, no lyrics, or no vocal-pop songs
- **THEN** the API response MUST exclude the conflicting songs
- **AND** playback URL lookup MUST only run for songs that remain eligible after filtering.
