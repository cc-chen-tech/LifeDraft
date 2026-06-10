## ADDED Requirements

### Requirement: Save Preset Sheets Expose Inline Progress And Failure
Character creation save preset sheets SHALL show modal-local status while saving and after save failure so users do not have to rely only on a disabled button or a transient global toast.

#### Scenario: Save preset request is pending
- **WHEN** the player opens a save preset sheet, enters a preset name, and starts saving
- **THEN** the sheet MUST show an inline polite status message indicating that the preset is being saved
- **AND** the save action MUST remain visibly disabled while the request is pending

#### Scenario: Save preset request fails
- **WHEN** a save preset request fails
- **THEN** the sheet MUST remain open
- **AND** the sheet MUST show an inline alert explaining that the preset was not saved and can be retried
- **AND** the save action MUST become available again after the failed request finishes
