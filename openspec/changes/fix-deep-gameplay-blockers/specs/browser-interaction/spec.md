## ADDED Requirements

### Requirement: Primary gameplay controls respond to real clicks

The frontend SHALL make primary gameplay controls clickable with normal browser input, not only DOM-dispatched clicks.

#### Scenario: Choice button clicked by browser automation

- **WHEN** a visible enabled choice button is clicked with normal browser input
- **THEN** the click MUST invoke the choice handler once
- **AND** no overlay or fixed panel may intercept the click.

#### Scenario: ChatBar opened during gameplay

- **WHEN** the ChatBar open button is visible
- **THEN** a normal browser click MUST open the chat panel
- **AND** the panel MUST NOT block unrelated choice buttons after it is closed.
