# Collection Empty Whitelist Auto-Sync QA Evidence

Date: 2026-06-10
Branch: `codex/fix-entity-collection-ui-e2e-20260610`

## Reproduced

- Backend recognition returned `[]` for story text containing `马老板`, `方蕾`, `赵子豪`, and `王丽华` when `eligible_character_names=[]`.
- Frontend `CollectionPanel` skipped auto-recognition when characters only contained the protagonist but items and landmarks were already populated.

## Fix

- Backend deterministic person fallback now treats an empty eligibility list as absent metadata, while non-empty eligibility lists remain strict.
- Chinese name fallback recognizes explicit action text such as `方蕾要求...`.
- Frontend collection panel runs initial auto-recognition when `characters.length <= 1`, so later story characters can be added even if old item/landmark collections already exist.

## Verification

- `pytest tests/test_live_gameplay_recovery_collection_contract.py -k "empty_character_whitelist" -q`
  - Red before fix: returned `[]`.
  - Green after fix.
- `pytest tests/test_live_gameplay_recovery_collection_contract.py -q`
  - `6 passed`.
- `pytest tests/test_live_gameplay_recovery_collection_contract.py tests/test_collection_recognition_current_event.py tests/test_entity_recognition_async.py -q`
  - `48 passed`.
- `cd frontend && npx jest --runTestsByPath src/__tests__/components/game/CollectionPanelAutoCollect.test.tsx --runInBand`
  - Red before frontend fix: `Unable to find an element with the text: 方蕾`.
  - Green after fix: `2 passed`.
