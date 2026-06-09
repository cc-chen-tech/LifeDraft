## Why

The 2026-06-08 UX report found that the collapsed ChatBar labels a regenerate action as "重写", while the same action is labeled "重新生成" in the expanded panel. This makes rewrite and regenerate appear interchangeable even though rewrite opens an edit sheet and regenerate creates a new story attempt.

## What Changes

- Rename the collapsed regenerate quick action from "重写" to "重新生成".
- Keep the collapsed "改写" button as the only rewrite entry point.
- Add regression coverage so the collapsed ChatBar exposes distinct regenerate and rewrite labels.
- Keep existing regenerate and rewrite callbacks unchanged.

## Capabilities

### New Capabilities

### Modified Capabilities
- `gameplay-side-controls`: Clarify that regenerate controls must use regenerate wording and rewrite controls must use rewrite wording.

## Impact

- Frontend ChatBar quick action labels in `frontend/src/components/game/ChatBar.tsx`.
- Frontend Jest regression coverage in `frontend/src/__tests__/components/ChatBar.test.tsx`.
- `test.sh` preflight remains the gate for this test file.
