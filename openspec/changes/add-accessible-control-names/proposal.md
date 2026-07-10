## Why

Production QA found icon-only controls and history entries that cannot be identified reliably by screen readers, keyboard users, or browser automation. These controls perform sensitive actions such as copying credentials and deleting saved data, so each must expose a stable, descriptive accessible name.

## What Changes

- Give the registration credential copy control and profile public-ID copy control explicit state-aware names.
- Give each save deletion control a unique name that identifies the save it affects.
- Give character detail close and delete controls descriptive names tied to the character.
- Give each history round a unique name containing its week, round, and reading action.
- Add component and browser tests that locate these controls exclusively through accessible roles and names.

## Capabilities

### New Capabilities
- `accessible-control-names`: Defines stable accessible naming for credential, profile, save, character-detail, and history controls.

### Modified Capabilities

## Impact

- Frontend pages: registration, profile, and saves.
- Gameplay components: character details and round history drawer.
- Frontend Jest and Playwright accessibility coverage.
- `test.sh` E2E registration for the new browser contract.
