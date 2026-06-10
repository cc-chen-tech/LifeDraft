## Why

Character creation era regeneration can still drift away from the user's life vision when feedback is provided. The live report class of failures is that a modern product-manager vision can be regenerated into an ancient China setting, because feedback bypassed the existing life-vision alignment guard. The opposite direction also needs protection: if the user explicitly asks to avoid modern technology, a modern AI/company setting should not survive.

## What Changes

- Keep life-vision era alignment active even when `feedback` is provided to the era setting generator.
- Add a classical/anti-modern intent guard so explicit ancient or traditional visions are not overwritten by modern defaults.
- Add focused backend regression tests for both directions.
- Document the reproduction, root cause, and verification commands.

## Impact

- Backend character era generation only.
- No API schema or database migration.
