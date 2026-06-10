## 1. Contract Test Coverage

- [x] 1.1 Add `tests/test_contracts_historical_summary_selector.py` for boundary and fallback summary contracts.
- [x] 1.2 Add `tests/test_contracts_narrative_manager_overdue.py` for overdue escalation contracts.

## 2. SSE Helper Contracts

- [x] 2.1 Add `tests/test_contracts_sse_helpers.py` for prefetch/retry/cache contracts and background scheduling edges.

## 3. Session Service Contracts

- [x] 3.1 Add `tests/test_contracts_session_service.py` for era extraction and image-health check contracts.

## 4. Frontend/API Contract Spot Check

- [x] 4.1 Add `tests/test_contracts_collection_frontend_fields.py` to assert API collection response and store-facing field contracts remain stable.

## 5. Verification

- [x] 5.1 Run targeted pytest on newly added contract files.
- [x] 5.2 Run `pytest tests/test_gate_contracts_no_mock.py -q` and selected contract files for regression signal.
- [ ] 5.3 Commit test-only changes once pass in branch worktree.
