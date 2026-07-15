## ADDED Requirements

### Requirement: Image transport failures remain typed and safe
The maintained backend suite SHALL verify that image edit safety responses, invalid provider JSON, and failed downloads become typed provider failures without exposing provider internals.

#### Scenario: Provider response fails transport validation
- **WHEN** an image transport response is unsafe, malformed, or unsuccessful
- **THEN** the generator returns the corresponding typed error semantics
