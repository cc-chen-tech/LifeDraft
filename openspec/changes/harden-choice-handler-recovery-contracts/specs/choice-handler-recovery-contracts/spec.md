## ADDED Requirements

### Requirement: Choice retry replaces partial story with replacement content
The frontend suite SHALL verify that a retry status restores the pre-choice story
before replacement stream content is accepted.

#### Scenario: SSE stream enters retry before completion
- **WHEN** a choice SSE stream emits a retry status then a replacement story chunk
- **THEN** the hook restores the base story and reports retry processing
- **AND** it completes the choice without retaining partial stream text

### Requirement: Custom choice accepts terminal-story fallback
The frontend suite SHALL verify that a custom choice whose SSE stream contains no
story chunk uses the terminal story field.

#### Scenario: Custom choice completes without story chunk
- **WHEN** the terminal event contains a story continuation but no story chunk
- **THEN** the hook appends that continuation to the base story and enters result
phase
