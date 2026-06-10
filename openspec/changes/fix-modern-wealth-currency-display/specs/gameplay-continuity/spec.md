## MODIFIED Requirements

### Requirement: Player Resources Remain Coherent Across Gameplay

Player resource values SHALL remain consistent and interpretable as gameplay advances.

#### Scenario: Modern wealth display has no explicit currency metadata
- **Given** a modern or unspecified real-world game has a numeric player wealth value
- **And** the player state does not include an explicit `currency` or `currency_name`
- **When** the frontend renders the status bar
- **Then** the wealth display SHALL use yuan (`元`) as the fallback unit
- **And** the display SHALL not use the generic `货币` label.

#### Scenario: Wealth display has explicit currency metadata
- **Given** a player state includes explicit wealth currency metadata
- **When** the frontend renders the status bar
- **Then** a `currency` symbol SHALL render before the formatted amount
- **And** a `currency_name` value SHALL render after the formatted amount when no symbol is present.

#### Scenario: Generated starting wealth initializes gameplay state
- **Given** character creation generated a numeric starting wealth value
- **And** that value is represented as `wealth.wealth`, `wealth.starting_wealth`, `wealth.initial_wealth_amount`, or a formatted numeric `wealth.initial_wealth`
- **When** the game is created or late character settings are patched before the first played round
- **Then** the player state's numeric wealth SHALL use that generated value
- **And** the value SHALL NOT fall back to the global default merely because a different generated field name was used.
- **And** formatted currency text such as `¥50,000`, `50,000元`, or `5万元` SHALL be parsed as the corresponding numeric yuan amount
- **And** qualitative labels such as `middle` SHALL NOT be treated as numeric starting wealth.
