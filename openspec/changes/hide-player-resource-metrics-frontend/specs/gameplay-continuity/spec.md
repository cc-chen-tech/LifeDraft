## ADDED Requirements

### Requirement: Ending and review surfaces hide resource score summaries
Ending and life review surfaces SHALL preserve story continuity without displaying raw resource-score summaries for energy, mood, knowledge, or wealth.

#### Scenario: Ending page hides final resource stats
- **WHEN** an ending response includes `final_stats` with `energy`, `mood`, `knowledge`, and `wealth`
- **THEN** the ending page MUST NOT display a final numeric resource grid or the labels `精力`, `情绪`, `学识`, or `财富`
- **AND** non-resource ending content such as title, summary, and relationship highlights MUST remain available

#### Scenario: Life review hides resource curves
- **WHEN** life review data includes resource curves for `energy`, `mood`, `knowledge`, or `wealth`
- **THEN** the life review card MUST NOT display resource curve labels, charts, or raw resource keys
- **AND** timeline, theme, achievement, regret, relationship, and turning point content MUST remain available
