## ADDED Requirements

### Requirement: Story people are collected comprehensively

The collection system SHALL recognize concrete named people that appear in accepted story text.

#### Scenario: Multiple named people appear in the story

- **WHEN** story text mentions named people such as `赵怀安`, `苏小二`, and `沈掌柜`
- **THEN** those people MUST be returned as candidate characters
- **AND** the protagonist MUST NOT be duplicated.

### Requirement: Items and landmarks stay curated

The collection system SHALL avoid collecting every incidental noun as an item or landmark.

#### Scenario: Incidental objects appear once

- **WHEN** story text contains incidental objects such as ordinary cups, doors, or tables
- **THEN** they SHOULD NOT be collected as important items.

#### Scenario: Important artifacts appear

- **WHEN** story text presents an object as a named, repeated, or plot-bearing artifact
- **THEN** it SHOULD be returned as an item candidate.
