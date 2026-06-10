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

#### Scenario: Inline rewrite keeps modern timeline title authority

- **GIVEN** a non-ancient Chinese save whose current story text contains a stale classical title such as "第X回"
- **WHEN** the player rewrites a segment of that story
- **THEN** the rewrite prompt MUST include the current display week and round title such as "第N周·周一"
- **AND** the prompt MUST instruct the model to replace stale classical or conflicting titles
- **AND** the prompt MUST NOT preserve seven-character couplet title requirements for the modern save

#### Scenario: Explicit ancient settings keep classical titles

- **GIVEN** character settings explicitly include ancient, wuxia, palace, or xianxia cues
- **WHEN** a Chinese story prompt is built
- **THEN** the prompt MAY require classical chapter labels

#### Scenario: Generated modern story still uses a stale classical title

- **GIVEN** a non-ancient Chinese save has modern timeline-title prompt constraints
- **WHEN** the model output still starts with a classical chapter label such as "第三回"
- **THEN** quick validation MUST reject the story before display or persistence
- **AND** the retry instruction MUST require a modern timeline title such as "第N周·周一"
- **AND** explicit ancient, wuxia, palace, or xianxia saves MUST NOT be rejected for using classical chapter labels

#### Scenario: Plain realistic settings are validated as modern at runtime

- **GIVEN** character settings include ordinary realistic fields such as age, wealth, family, education, relationships, occupation, or career
- **AND** the settings do not include explicit ancient, wuxia, palace, or xianxia cues
- **WHEN** quick validation checks a Chinese story that starts with a classical chapter label such as "第三回"
- **THEN** quick validation MUST treat the story as modern
- **AND** quick validation MUST reject the classical chapter label before display or persistence

#### Scenario: Weekday and everyday words do not imply ancient settings

- **GIVEN** a realistic Chinese character setting includes everyday words such as "周末", "说明", or "清晨"
- **AND** the setting does not explicitly name an ancient dynasty, wuxia, palace, or xianxia context
- **WHEN** quick validation infers the era type
- **THEN** those single characters MUST NOT cause the save to be classified as ancient
- **AND** modern timeline-title validation MUST remain active
