## ADDED Requirements

### Requirement: Dialog Content Has Accessible Description Fallback
Shared dialog and sheet content SHALL provide an accessible description fallback so missing-description warnings do not appear when a dialog or sheet opens.

#### Scenario: Dialog opens without explicit description
- **WHEN** a dialog renders `DialogContent` without a child `DialogDescription`
- **THEN** the content MUST still have an `aria-describedby` target
- **AND** opening the dialog MUST NOT emit `Missing Description for DialogContent`.

#### Scenario: Sheet opens without explicit description
- **WHEN** a sheet renders `SheetContent` without a child `SheetDescription`
- **THEN** the content MUST still have an `aria-describedby` target
- **AND** opening the sheet MUST NOT emit `Missing Description for DialogContent`.
