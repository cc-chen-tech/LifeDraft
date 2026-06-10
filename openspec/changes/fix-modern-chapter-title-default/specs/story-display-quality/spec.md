## ADDED Requirements

### Requirement: Ordinary Modern Settings Use Timeline Titles

Chinese story prompts SHALL use modern week/round timeline titles for ordinary non-ancient character settings, even when the setting does not explicitly include words such as "现代" or "职场".

#### Scenario: Missing settings use the standard modern default

- **GIVEN** no character settings were provided
- **WHEN** a Chinese story prompt is built for the default protagonist context
- **THEN** the prompt MUST require a title such as "第N周·周一"
- **AND** the prompt MUST NOT require "第X回" chapter labels or seven-character couplet titles

#### Scenario: Age and career settings without ancient cues

- **GIVEN** character settings include an adult protagonist and a realistic career
- **AND** the settings do not include ancient, wuxia, palace, or xianxia cues
- **WHEN** a Chinese story prompt is built
- **THEN** the prompt MUST require a title such as "第N周·周一"
- **AND** the prompt MUST NOT require "第X回" chapter labels or seven-character couplet titles

#### Scenario: Scheduled commitment events use the same timeline title

- **GIVEN** a pending scheduled event or commitment event in a non-ancient Chinese save
- **WHEN** the scheduled-event prompt is built for a week and round
- **THEN** the prompt MUST use the display week and round title such as "第N周·周一"
- **AND** the prompt MUST include the same modern title constraint as ordinary story generation
- **AND** the prompt MUST NOT expose zero-based internal week values or require classical chapter labels

#### Scenario: Explicit ancient settings keep classical titles

- **GIVEN** character settings explicitly include ancient, wuxia, palace, or xianxia cues
- **WHEN** a Chinese story prompt is built
- **THEN** the prompt MAY require classical chapter labels
