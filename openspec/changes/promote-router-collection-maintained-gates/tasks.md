## 1. Explore

- [x] 1.1 Re-run the previously excluded image router and collection API suites together.
- [x] 1.2 Confirm the result is stable enough for maintained-gate promotion.

## 2. Apply

- [x] 2.1 Add `tests/test_images_router.py` and `tests/test_api_collection.py` to local maintained contract and coverage gates.
- [x] 2.2 Add the same files to backend and coverage CI maintained gates.
- [x] 2.3 Update gate-fidelity tests to assert the promotion remains wired.
- [x] 2.4 Update legacy failure inventory and triage notes to remove the old exclusion.

## 3. Verify

- [x] 3.1 Run the targeted promoted suites.
- [x] 3.2 Run gate-fidelity tests.
- [x] 3.3 Run maintained backend coverage.
- [x] 3.4 Validate the OpenSpec change.
