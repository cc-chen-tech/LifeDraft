## ADDED Requirements

### Requirement: New events contain exactly three resilient options

The system SHALL produce exactly three options for every newly completed event and SHALL NOT discard a complete story because one option is invalid.

#### Scenario: One generated option exceeds the repair threshold

- **WHEN** two options are valid and one option exceeds its localized repair threshold
- **THEN** the system preserves the two valid options and repairs only the invalid slot

#### Scenario: Repair provider fails

- **WHEN** one or more invalid slots remain after the allowed repair call
- **THEN** the system fills only those slots with unique contextual deterministic options and returns the original complete story

### Requirement: Option lengths are localized and independently budgeted

The system SHALL target 8-24 Unicode characters for Chinese options and 3-12 words for English options, SHALL repair above 40 Chinese characters or 16 English words, and SHALL use no more than the request option-call allowance.

#### Scenario: English option contains twelve words

- **WHEN** an English option contains twelve measured words
- **THEN** it is within the target band and does not require repair

### Requirement: Legacy option groups remain readable

The system SHALL restore and display saved events containing two, three, or four options without migration or truncation.

#### Scenario: Four-option legacy save resumes

- **WHEN** a saved event contains four valid options
- **THEN** all four options remain available after restore

### Requirement: Completed story remains visible while choices are pending

The client SHALL keep non-empty story text visible while option generation is incomplete and SHALL show an inline “正在准备选择” state.

#### Scenario: Story complete and options absent

- **WHEN** streaming has produced a complete story but no options yet
- **THEN** the story remains visible and the client does not show a full-page retry state

### Requirement: Option controls are stable and accessible

The client SHALL render touch-safe option controls limited visually to two lines, preserve full option text in the accessible name, and show immediate selected/loading feedback.

#### Scenario: User chooses a long option

- **WHEN** the user activates a visually clamped option
- **THEN** assistive technology can read the full text and the selected control immediately enters a loading state while other options are disabled
