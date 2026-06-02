# character-setting-continuity Specification

## Purpose
TBD - created by archiving change fix-live-gameplay-recovery-collection. Update Purpose after archive.
## Requirements
### Requirement: Opening Story Uses Canonical Character Settings

Opening story generation SHALL use the structured character settings created during character creation as the source of truth.

#### Scenario: User creates a near-future investigation reporter
- **Given** the character settings specify a near-future city, a female investigation reporter, technology-company corruption, and third-person narration
- **When** the opening story is generated
- **Then** the story SHALL preserve those constraints in premise, era, role, and narrative perspective
- **And** it SHALL NOT drift into an unrelated ancient or heritage-preservation premise.

### Requirement: Subsequent Rounds Preserve Core Premise

Round generation SHALL preserve the core character premise unless the player choices explicitly change it.

#### Scenario: Week one advances after opening
- **Given** the opening story is based on structured near-future investigation settings
- **When** the user chooses an option
- **Then** the resulting round SHALL continue the investigation/reporter premise
- **And** it SHALL keep the protagonist name and gender from the stored character settings.

