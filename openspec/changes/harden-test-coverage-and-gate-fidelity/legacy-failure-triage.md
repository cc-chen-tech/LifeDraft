## Legacy Failure Triage

This change keeps maintained gates explicit while full backend failures are sorted. The full backend suite is useful for visibility but is not currently a reliable merge gate.

## Restore Production Behavior

- `tests/security/test_api_security.py`: setup fails before exercising SQL injection behavior because the users table is missing. Fix test DB initialization, then keep the security behavior as a valid contract.
- `tests/test_error_recovery_contract.py`: SSE disconnect behavior is user-visible recovery behavior. Recheck against current SSE implementation before updating tests.
- `tests/test_story_generator_best_story_db.py`: best-story fallback may affect generation quality. Reproduce with a narrow targeted run before deciding whether implementation or test expectation is stale.

## Update Obsolete Contracts

- `tests/test_music_cache_contract.py`
- `tests/test_music_cache_integration.py`
- `tests/test_music_service.py`
- `tests/test_music_service_health_contract.py`
- `tests/test_music_service_url_contract.py`

These tests assert removed `NeteaseMusicClient` internals such as `_url_cache`, `URL_CACHE_TTL`, `HEALTH_CHECK_TIMEOUT`, and cached availability state. Current implementation degrades 503 URL lookups through the maintained `tests/test_music_degradation_no_mock.py` gate. Do not restore old class-level cache behavior unless a new product requirement requires it.

## Reconcile Current Contracts

- `tests/test_chinese_text_normalization_contract.py`: overlaps with maintained normalization checks in `tests/test_gate_gameplay_behavior_no_mock.py`, but broader expectations differ. Reconcile expected punctuation policy before restoring the file as a gate.
- `tests/test_era_validator_integration.py`, `tests/test_era_validator_production_contract.py`, `tests/test_music_era_recommendation_contract.py`: era and ancient/modern classification affects story quality and music search. Update these together so validation and music keyword policy agree.
- `tests/test_scene_image_sse_contract.py`, `tests/test_scene_image_sse_integration.py`: scene image SSE is user-visible. Current focused frontend coverage now records failed SSE errors; backend contract should be updated around current event format and auth policy.
- `tests/test_sse_retry_contract.py`: current frontend retry logic appears to live in `frontend/src/lib/api.ts`, while this contract checks `frontend/src/lib/sse.ts`. Decide whether SSE streaming requests still need retry there or whether this is obsolete route-specific coverage.
- `tests/test_frontend_contract_alignment.py`: likely route/type drift checks. Compare with maintained `tests/test_shift_left_e2e_contract_no_mock.py` before restoring.
- `tests/test_contracts_new_features.py`, `tests/test_narrative_integration.py`, `tests/test_story_generator_narrative.py`: feature-default expectations may predate recent narrative and music redesigns. Reclassify after checking current OpenSpec scope.
- `tests/test_harness_retry_loop.py`: retry temperature decay is implementation detail unless tied to generation stability. Keep only if behavior is still intentional.
- `tests/test_image_cache_contract.py`: reconcile with current image cache headers and production caching policy.
- `tests/test_music_router.py`: update to current local-only playlist and degradation behavior.
- `tests/test_security_prompt_injection_contract.py`, `tests/test_security_sqlalchemy_raw_sql_contract.py`: security contracts should remain important, but the exact static assertions may need modernization.

## Explicit Exclusions

No maintained-gate exclusions were added in this pass. The stale groups remain outside maintained coverage because they are not wired into `test.sh` preflight/mypy/imports/contract/db. Any future exclusion from an existing maintained gate must include a reason in this file or a successor triage artifact.
