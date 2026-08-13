## ADDED Requirements

### Requirement: Collection identity and recognition field coverage
The maintained backend suite SHALL verify that collection recognition retains valid first-seen names, ignores malformed values, and appends an unfinished current story once.

#### Scenario: Aggregate current-story entity context
- **WHEN** structured settings and an unfinished current event provide eligible character names
- **THEN** the recognition helpers return normalized unique names and one current-round history entry

### Requirement: Collection session and no-op command coverage
The maintained backend suite SHALL verify authenticated player-state lookup and existing-description responses without invoking a provider.

#### Scenario: Read an existing item description
- **WHEN** an authenticated session contains a URL-encoded item name with a sufficiently detailed description
- **THEN** the route returns the existing-description response without generation

#### Scenario: Reject unauthenticated collection access
- **WHEN** a collection helper or command receives no user identity
- **THEN** it raises a 401 HTTP error
