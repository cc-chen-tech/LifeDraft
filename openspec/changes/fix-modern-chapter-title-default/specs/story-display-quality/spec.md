## ADDED Requirements

### Requirement: Ordinary Modern Settings Use Timeline Titles

Chinese story prompts SHALL use modern week/round timeline titles for ordinary non-ancient character settings, even when the setting does not explicitly include words such as "现代" or "职场".

#### Scenario: Age and career settings without ancient cues

- **GIVEN** character settings include an adult protagonist and a realistic career
- **AND** the settings do not include ancient, wuxia, palace, or xianxia cues
- **WHEN** a Chinese story prompt is built
- **THEN** the prompt MUST require a title such as "第N周·周一"
- **AND** the prompt MUST NOT require "第X回" chapter labels or seven-character couplet titles

#### Scenario: Explicit ancient settings keep classical titles

- **GIVEN** character settings explicitly include ancient, wuxia, palace, or xianxia cues
- **WHEN** a Chinese story prompt is built
- **THEN** the prompt MAY require classical chapter labels
