## MODIFIED Requirements

### Requirement: Subsequent Rounds Preserve Core Premise

Round generation SHALL preserve the core character premise unless the player choices explicitly change it.

#### Scenario: Week one advances after opening
- **Given** the opening story is based on structured near-future investigation settings
- **When** the user chooses an option
- **Then** the resulting round SHALL continue the investigation/reporter premise
- **And** it SHALL keep the protagonist name and gender from the stored character settings.

#### Scenario: Preset key people use relation instead of role
- **Given** the stored character settings define preset key people with `relation` labels such as mentor, close friend, or peer
- **When** a later story or round prompt builds required cast authority and available-people context
- **Then** each preset person SHALL retain that relationship function in the prompt
- **And** the prompt SHALL NOT render relation-only key people as unnamed-role or empty-role characters.
