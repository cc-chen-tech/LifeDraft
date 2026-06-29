## 1. Reproduce

- [x] Run the focused stale choice append test and confirm it fails because the
      complete payload fallback writes story text.

## 2. Test

- [x] Update the regression contract to expect complete-only fallback appending.
- [x] Add coverage proving already streamed continuation text is not duplicated.

## 3. Verify

- [x] Run the focused choice append Jest test.
- [x] Run the related `useChoiceHandler` and choice append Jest tests together.
- [x] Run OpenSpec validation.
- [x] Run preflight.
