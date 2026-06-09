## 1. Tests

- [x] Add a contract test for ordinary modern age/career settings that lack explicit modern keywords.
- [x] Add the contract test file to `test.sh contract`.

## 2. Fix

- [x] Update Chinese chapter-title classification so non-ancient settings use modern timeline titles.

## 3. Verify

- [x] Run the new contract test before the fix and confirm it fails.
- [x] Run `openspec validate fix-modern-chapter-title-default --strict`.
- [x] Run `./test.sh contract`.
- [x] Run full pre-PR gate before publishing.
