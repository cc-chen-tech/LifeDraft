## ADDED Requirements

### Requirement: Configured wealth initializes game state
The system SHALL initialize `PlayerState.wealth` from the numeric wealth amount in `character_settings.wealth` when present.

#### Scenario: Yuan wealth survives game creation
- **WHEN** character settings contain `wealth.wealth = 50000`, `currency = "¥"`, and `currency_name = "元"`
- **THEN** the new game's initial state SHALL set `wealth` to `50000`
- **AND** it SHALL not fall back to the global default `10000`.

#### Scenario: Missing configured wealth uses default
- **WHEN** character settings do not contain a usable numeric wealth amount
- **THEN** the new game's initial state SHALL use the configured application default
- **AND** it SHALL keep existing validation bounds.

### Requirement: Currency label follows character settings
The frontend and prompt consumers SHALL display wealth using the currency metadata from `character_settings.wealth`.

#### Scenario: Frontend displays yuan amount
- **WHEN** the loaded game state has `wealth = 50000` and `character_settings.wealth.currency = "¥"`
- **THEN** the status display SHALL show a yuan-style wealth value such as `¥50,000`
- **AND** it SHALL not show `10,000 货币`.

#### Scenario: Prompt displays configured unit
- **WHEN** the story prompt receives `wealth = 50000` and `currency_name = "元"`
- **THEN** the prompt SHALL include `50,000元` or `¥50,000`
- **AND** it SHALL not hard-code a generic `货币` unit.
