## ADDED Requirements

### Requirement: Expanded sound controls use one unified panel

The expanded global sound controls SHALL present scene music and story narration as peer controls inside one sound panel.

#### Scenario: Music and narration are available together
- **Given** the current story has music context and an active reading context
- **When** the user expands the global sound controls
- **Then** the UI SHALL expose one expanded sound panel
- **And** that panel SHALL contain a scene music section
- **And** that panel SHALL contain a story narration section
- **And** the embedded story narration controls SHALL not render as a separate bordered card or separate top-divided control strip.
