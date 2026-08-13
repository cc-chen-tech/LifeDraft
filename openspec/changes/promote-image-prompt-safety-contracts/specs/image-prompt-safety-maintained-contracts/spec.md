## ADDED Requirements

### Requirement: Image prompt safety contracts are maintained
The maintained backend gate SHALL exercise local era sanitization and prompt injection defenses without provider calls or doubles.

#### Scenario: Unsafe era or name input is supplied
- **WHEN** era text has sci-fi triggers or a name has instruction injection text
- **THEN** the image prompt contract MUST fail if the unsafe content survives sanitization
