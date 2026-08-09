## ADDED Requirements

### Requirement: Maintained character-image parameter propagation coverage
The maintained backend workflows SHALL execute
`tests/test_character_image_extra_params.py` in identical ordered selections.

#### Scenario: Caller parameters reach the image-provider boundary
- **WHEN** character image generation receives provider extra parameters
- **THEN** the provider-boundary call receives the same parameter values.

#### Scenario: Omitted parameters remain supported
- **WHEN** character image generation omits optional extra parameters
- **THEN** generation completes through the provider-boundary protocol without
  an argument error.

### Requirement: Verified 51 percent maintained gate
The coverage workflow SHALL require 51% only after the complete promoted
selection passes at that value.

#### Scenario: Verified threshold advance
- **WHEN** the complete maintained selection passes `--cov-fail-under=51`
- **THEN** the workflow coverage minimum is set to 51%.
