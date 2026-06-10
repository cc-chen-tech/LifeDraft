## ADDED Requirements

### Requirement: Era regeneration honors life-vision direction
Character era setting generation SHALL preserve the user's explicit life-vision direction even when the user provides feedback for regeneration.

#### Scenario: Modern product-manager vision remains modern after era feedback
- **GIVEN** the user's life vision specifies a 2020s Chinese internet-company product-manager story
- **WHEN** era generation with feedback returns an ancient setting such as Tang, Chang'an, or imperial examination society
- **THEN** the returned era setting MUST be realigned to a modern year and modern internet-company context
- **AND** it MUST NOT keep ancient markers that contradict the life vision.

#### Scenario: Anti-modern classical vision remains historical
- **GIVEN** the user's life vision explicitly asks for a classical, traditional, or anti-modern story direction
- **WHEN** era generation returns a modern AI, internet, company, or technology setting
- **THEN** the returned era setting MUST be realigned to a historical/classical context
- **AND** it MUST NOT keep modern technology or company markers that contradict the life vision.
