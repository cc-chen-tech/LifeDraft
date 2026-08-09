## ADDED Requirements

### Requirement: Repeated narrative entities are selected predictably
The maintained backend suite SHALL verify that an illustration reference contains established characters first, followed by only items that meet the repeated-occurrence threshold and then an established or recurring location.

#### Scenario: Selecting a bounded mixed reference set
- **WHEN** a story mentions known characters, a repeatedly established item, and a location
- **THEN** the selected entities preserve the priority order, de-duplicate names, and contain at most five references

### Requirement: World-model entity sources are resilient
The maintained backend suite SHALL verify that malformed dynamic facts are ignored, one-off items are excluded, and recurring world-model locations are used only when no established location is present.

#### Scenario: Selecting entities from mixed world-model facts
- **WHEN** dynamic facts contain valid, malformed, and one-off entity data
- **THEN** only valid repeated entities and the highest-priority eligible location are selected
