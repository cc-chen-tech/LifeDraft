## ADDED Requirements

### Requirement: Collection item mutation fields reach the selected store action
The frontend suite SHALL verify that a selected item's regeneration feedback is
trimmed and submitted with the current game ID and item name.

#### Scenario: Submit item image feedback
- **WHEN** a user enters surrounding whitespace in item image feedback and
  submits it
- **THEN** the store receives the game ID, selected item name, and trimmed
  feedback

### Requirement: Collection mutations remain reachable from detail UI
The frontend suite SHALL verify deletion confirmation and ungenerated-landmark
batch actions call their corresponding store actions.

#### Scenario: Confirm item deletion
- **WHEN** a user confirms deletion of a selected item
- **THEN** the item deletion action receives the game ID and item name

#### Scenario: Batch generate landmarks
- **WHEN** the landmarks tab contains images pending generation
- **THEN** the batch generation action receives the current game ID

### Requirement: Collection mutation errors can be dismissed
The frontend suite SHALL verify that an existing visible collection error calls
the error-clear action.

#### Scenario: Dismiss visible error
- **WHEN** a collection error is displayed
- **THEN** activating the close control clears the error action
