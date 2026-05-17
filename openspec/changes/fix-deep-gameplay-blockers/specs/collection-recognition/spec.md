## ADDED Requirements

### Requirement: Story people are collected comprehensively

The collection system SHALL recognize concrete named people that appear in accepted story text.

#### Scenario: Multiple named people appear in the story

- **WHEN** story text mentions named people such as `赵怀安`, `苏小二`, and `沈掌柜`
- **THEN** those people MUST be returned as candidate characters
- **AND** the protagonist MUST NOT be duplicated.

#### Scenario: Current event has not been chosen yet

- **WHEN** the currently displayed story mentions named people
- **AND** the player has not chosen an option yet so the story is not in round history
- **THEN** smart recognition MUST still include those named people as candidate characters
- **AND** it MUST keep item recognition curated.

#### Scenario: Long history is truncated for recognition

- **WHEN** the stored story history is longer than the AI recognition context limit
- **AND** recent or currently displayed story text mentions named people such as `石无言`
- **THEN** smart recognition MUST preserve recent/current story context before truncation
- **AND** those named people MUST still be returned as candidate characters.

#### Scenario: Pronoun fragments and short aliases are not people

- **WHEN** smart recognition falls back to rule-based person extraction
- **THEN** it MUST reject pronoun, time-span, or action fragments such as `施主此`, `于是你`, `许久`, and `马蹄踏`
- **AND** it MUST reject verb-fragment suffixes such as `陆辞知`, `陆辞现`, `陆辞坐`, and `陆辞苦`
- **AND** it MUST avoid collecting short title aliases such as `沈伯`, `沈先生`, `林姑娘`, or `陆公子` when the fuller name `沈伯安`, `林见微`, or `陆辞` is present.

#### Scenario: AI recognition returns duplicate aliases

- **WHEN** AI recognition returns both a fuller person name and a title alias such as `沈伯安` and `沈先生`
- **THEN** the collection system MUST keep the fuller person name and drop the title alias
- **AND** when it returns both a fuller place name and its short suffix such as `城南思源茶楼` and `思源茶楼`
- **THEN** the collection system MUST keep the fuller place name and drop the short suffix.

### Requirement: Items and landmarks stay curated

The collection system SHALL avoid collecting every incidental noun as an item or landmark.

#### Scenario: Incidental objects appear once

- **WHEN** story text contains incidental objects such as ordinary cups, doors, or tables
- **THEN** they SHOULD NOT be collected as important items.

#### Scenario: Important artifacts appear

- **WHEN** story text presents an object as a named, repeated, or plot-bearing artifact
- **THEN** it SHOULD be returned as an item candidate.
