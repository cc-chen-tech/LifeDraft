## ADDED Requirements

### Requirement: Fallback prompts preserve safe visual identity
The maintained backend suite SHALL verify that deterministic image fallback helpers remove sci-fi era cues, preserve story identity, and retain a realistic full-body composition.

#### Scenario: Unsafe era description
- **WHEN** an era description contains futuristic visual triggers
- **THEN** the fallback prompt SHALL replace it with a safe contemporary visual description.

### Requirement: Appearance fallbacks retain extractable features
The maintained backend suite SHALL verify that fallback appearance anchors preserve recognized face shape, hair style, hair color, source description, and version metadata.

#### Scenario: Legacy visual description
- **WHEN** a character description contains recognized visual traits
- **THEN** the fallback anchor SHALL expose those traits without a provider call.

### Requirement: Maintained workflows run image prompt fallback contracts
Both maintained backend workflow lists SHALL include the image prompt fallback contract path in matching order.

#### Scenario: Workflow parity
- **WHEN** workflow test lists are compared
- **THEN** the image prompt fallback contract path SHALL occur in both lists at the same position.
