## 1. Regression Coverage

- [x] 1.1 Update ChatBar regression coverage so collapsed regenerate is labeled "重新生成" and collapsed rewrite remains "改写".
- [x] 1.2 Run the targeted ChatBar test before implementation and confirm it fails on the old "重写" label.
- [x] 1.3 Update the browser E2E discoverability contract after confirming it failed on the old "重写" label.

## 2. Implementation

- [x] 2.1 Rename the collapsed regenerate quick action label from "重写" to "重新生成".
- [x] 2.2 Preserve regenerate callback behavior and rewrite sheet behavior.

## 3. Verification

- [x] 3.1 Run the targeted ChatBar regression test.
- [x] 3.2 Run `openspec validate fix-regenerate-button-label --strict`.
- [x] 3.3 Run `./test.sh all`.
