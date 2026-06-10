## 1. Regression Coverage

- [x] 1.1 Add hook coverage that observes preset save pending state before the request resolves.
- [x] 1.2 Add hook coverage that verifies inline retry state after a save failure.
- [x] 1.3 Add create-page coverage that the save preset sheet renders an accessible saving status.
- [x] 1.4 Add create-page coverage that the save preset sheet renders an accessible failure alert.

## 2. Implementation

- [x] 2.1 Expose preset save status and message from `useCharacterCreation`.
- [x] 2.2 Render a shared inline status component in both create-page save preset sheets.
- [x] 2.3 Reset stale save status when the sheet closes or the preset name changes after an error.

## 3. Verification

- [x] 3.1 Run the targeted hook regression test.
- [x] 3.2 Run the targeted create-page regression test.
- [x] 3.3 Run `openspec validate fix-preset-save-feedback --strict`.
