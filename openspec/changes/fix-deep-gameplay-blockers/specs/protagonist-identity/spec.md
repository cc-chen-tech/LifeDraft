## ADDED Requirements

### Requirement: Story generation preserves the saved protagonist identity

The narrative system SHALL preserve the saved protagonist name and gender across opening story, weekly story, and round story generation.

#### Scenario: Ancient setting resembles a famous detective trope

- **WHEN** the saved protagonist is `林见微`
- **AND** the saved gender is `女`
- **AND** the setting is ancient China
- **THEN** generated prompts MUST explicitly identify `林见微` as the protagonist
- **AND** they MUST forbid replacing her with `狄仁杰` or any other template/historical character.
