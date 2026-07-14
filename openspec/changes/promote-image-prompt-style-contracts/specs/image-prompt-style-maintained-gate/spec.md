## ADDED Requirements

### Requirement: Local image-control contracts are maintained
The maintained backend workflows SHALL execute appearance-anchor, prompt-enhancer, and style-manager contracts without invoking an image provider.

#### Scenario: Prompt or appearance regression
- **WHEN** an appearance, local prompt rule, palette, or temporal style invariant regresses
- **THEN** both maintained backend workflows fail before release.

### Requirement: Image-control workflows remain ordered equivalents
The coverage and backend-test workflows SHALL list the promoted image-control suites in identical order.

#### Scenario: Ordered parity
- **WHEN** maintained test paths are extracted from both workflow files
- **THEN** the resulting ordered lists are identical.

### Requirement: Promoted image-control tests remain local
The promoted image-control suites SHALL use deterministic in-process behavior and temporary local files only.

#### Scenario: Provider-free execution
- **WHEN** CI runs the maintained backend suite
- **THEN** the promoted image-control suites complete without browser or external image-provider access.
