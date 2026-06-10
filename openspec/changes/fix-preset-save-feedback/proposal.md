## Why

Production QA found that the create-page "保存预设" sheet can look stuck while a save request is pending or after a save failure. The button disables and the global toast may be missed, but the sheet itself does not explain whether it is saving, failed, or ready to retry.

## What Changes

- Add modal-local preset save status to `useCharacterCreation`.
- Show inline "正在保存角色预设..." feedback inside each create-page save preset sheet while the request is pending.
- Show inline retry feedback inside the sheet after a save failure, while keeping the sheet open and the controls usable.
- Add hook and page regression coverage for the saving and failed states.

## Capabilities

### New Capabilities

### Modified Capabilities
- `character-creation-feedback`: Save preset sheets must expose inline pending and failure feedback.

## Impact

- Frontend create-page preset save hook state in `frontend/src/hooks/useCharacterCreation.ts`.
- Frontend create-page and completion save preset sheets.
- Regression coverage in `frontend/src/__tests__/hooks/useCharacterCreation.test.ts` and `frontend/src/__tests__/pages/CreatePage.test.tsx`.
