## 1. Regression Coverage

- [x] 1.1 Add a frontend regression test that opens `DialogContent` without an explicit `DialogDescription` and asserts no Radix missing-description warning.
- [x] 1.2 Add the regression test to `test.sh` preflight.
- [x] 1.3 Run the new test before implementation and confirm it fails for the current primitive.
- [x] 1.4 Add a frontend regression test that opens `SheetContent` without an explicit `SheetDescription` and asserts no Radix missing-description warning.
- [x] 1.5 Add the sheet regression test to `test.sh` preflight.

## 2. Implementation

- [x] 2.1 Add an accessible fallback description in the shared `DialogContent` primitive.
- [x] 2.2 Preserve existing explicit dialog descriptions and close button behavior.
- [x] 2.3 Add an accessible fallback description in the shared `SheetContent` primitive.
- [x] 2.4 Preserve existing explicit sheet descriptions and close button behavior.

## 3. Verification

- [x] 3.1 Validate the OpenSpec change in strict mode.
- [x] 3.2 Run the targeted frontend regression test.
- [x] 3.3 Run the relevant `./test.sh` layer(s).
- [x] 3.4 Run the Play page collection-panel regression and confirm the Radix missing-description warning is absent.
