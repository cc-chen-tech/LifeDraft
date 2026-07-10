## ADDED Requirements

### Requirement: Sensitive icon actions expose descriptive names
The frontend SHALL expose a Chinese accessible name for credential copy, public-ID copy, save deletion, and character-detail icon controls without requiring SVG or DOM inspection.

#### Scenario: Registration credential copy
- **WHEN** a newly registered user is shown the one-time private credential
- **THEN** the copy button SHALL be discoverable as `复制私有密钥`
- **AND** after a successful copy it SHALL remain discoverable with a name that communicates both the completed state and the private-credential purpose

#### Scenario: Public ID copy
- **WHEN** an authenticated user views their profile
- **THEN** the public-ID copy button SHALL be discoverable as `复制公开 ID`

#### Scenario: Save deletion
- **WHEN** the save list contains one or more saves
- **THEN** every delete button SHALL have a unique accessible name containing the visible player identity and save ID

#### Scenario: Character detail controls
- **WHEN** a non-player character detail dialog is open
- **THEN** its close and delete buttons SHALL expose names containing that character's name

### Requirement: History entries expose unique reading actions
The history drawer SHALL expose every selectable round as a named button containing the one-based week, round label, and the action `阅读正文` when story content exists.

#### Scenario: Multiple recorded rounds
- **WHEN** history contains multiple rounds across one or more weeks
- **THEN** each recorded round SHALL be locatable by a unique role and accessible name
- **AND** activating that named button SHALL select the corresponding round and close the drawer

### Requirement: Accessible names are browser verified
The project test gate SHALL run a no-mock browser test that locates the reported controls by role and accessible name.

#### Scenario: E2E gate execution
- **WHEN** `test.sh e2e` runs
- **THEN** the accessible-control browser specification SHALL execute without being skipped
