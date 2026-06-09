## Why

The 2026-06-08 UX report captured a Radix accessibility warning: `Missing Description for DialogContent`. Dialog warnings are noisy in browser QA and signal that assistive technology may not receive a usable description for modal content.

## What Changes

- Add a base `DialogContent` fallback description so dialogs do not emit Radix's missing-description warning.
- Add the same fallback to `SheetContent`, because gameplay side panels are Radix Dialog content under the hood and can emit the same warning.
- Keep existing visible `DialogDescription` content unchanged for dialogs that already provide specific descriptions.
- Add frontend regression tests for `DialogContent` and `SheetContent` opened without an explicit description.
- Add the new regression test to `test.sh` preflight.

## Capabilities

### New Capabilities

### Modified Capabilities
- `gameplay-side-controls`: Add dialog accessibility coverage for modal descriptions.

## Impact

- Shared frontend dialog and sheet primitives: `frontend/src/components/ui/dialog.tsx`, `frontend/src/components/ui/sheet.tsx`.
- Frontend preflight Jest coverage in `test.sh`.
