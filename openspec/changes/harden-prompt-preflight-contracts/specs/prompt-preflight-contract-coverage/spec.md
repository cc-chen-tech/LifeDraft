## ADDED Requirements

### Requirement: Prompt preflight has deterministic maintained coverage
Maintained backend contracts SHALL validate prompt marker completeness, token-limit warnings, and critical and optional context reporting using concrete local strings and dictionaries without doubles.

#### Scenario: Complete prompt and context are supplied
- **WHEN** a prompt includes every configured marker and context includes every required field
- **THEN** preflight MUST report no missing constraints and complete context fields

#### Scenario: Prompt lacks markers or exceeds token guidance
- **WHEN** a prompt omits configured markers or exceeds the token threshold
- **THEN** preflight MUST report the missing constraints or length warning
