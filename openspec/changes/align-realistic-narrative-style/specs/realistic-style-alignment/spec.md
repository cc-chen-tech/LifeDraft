## ADDED Requirements

### Requirement: Explicit realism overrides incidental genre keywords
The automatic narrative style matcher SHALL resolve an explicitly realistic, real-world, or no-supernatural setup to `nonfiction_novel` even when the setup contains ordinary modern technology, AI, network, or enterprise terms.

#### Scenario: Realistic product manager setup
- **WHEN** a contemporary character asks for realistic product-management growth with no supernatural or cyberpunk elements
- **THEN** automatic matching SHALL return `nonfiction_novel`
- **AND** it SHALL NOT return `cyberpunk` or `magical_realism`

#### Scenario: Explicit cyberpunk setup
- **WHEN** a setting positively requests an original futuristic cyberpunk world without negating cyberpunk
- **THEN** automatic matching SHALL remain eligible to return `cyberpunk`

### Requirement: Explicit user choice remains authoritative
The game initializer MUST preserve a supplied `narrative_style_id` without replacing it through automatic realism detection.

#### Scenario: User chooses cyberpunk
- **WHEN** `narrative_style_id` is explicitly `cyberpunk` while other text contains realistic details
- **THEN** the saved game and initial player state SHALL retain `cyberpunk`

### Requirement: Resolved style is consistent across persistence and display
The resolved realistic style SHALL survive the real database save-read path and SHALL be returned by the narrative-style API for frontend display.

#### Scenario: New realistic game round trip
- **WHEN** a realistic game is initialized and later loaded from the database
- **THEN** the stored state and style API SHALL both identify `nonfiction_novel`

### Requirement: Browser gate verifies visible style
The E2E gate SHALL run a no-mock browser test that creates a realistic modern game and observes a non-cyberpunk selected style in the settings panel.

#### Scenario: Realistic style menu
- **WHEN** `test.sh e2e` opens narrative style settings for the realistic game
- **THEN** `非虚构小说` SHALL be selected
- **AND** `赛博朋克` SHALL not be selected
