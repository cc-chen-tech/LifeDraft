## ADDED Requirements

### Requirement: Character recognition has authoritative text evidence
Smart recognition SHALL propose a character only when the exact proposed name occurs in the analyzed story and is either an explicitly eligible configured name or a deterministic person-name extraction result. The system MUST NOT synthesize a full name from an honorific or role title.

#### Scenario: Honorific-only person in story
- **WHEN** the story mentions `周师傅` and no configured or story text contains `周建国`
- **THEN** recognition MAY propose `周师傅` but MUST NOT propose `周建国`

#### Scenario: Lexical fragments resemble names
- **WHEN** story text contains phase labels such as `周初` or numeric phrases such as `80000元减去500元`
- **THEN** recognition MUST NOT propose `周初` or `元减` as characters

#### Scenario: Configured person appears verbatim
- **WHEN** an eligible configured character name appears verbatim in the story
- **THEN** smart recognition SHALL retain that exact candidate when it is not already collected
