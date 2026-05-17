## Legacy Failure Triage

This change keeps maintained gates explicit while full backend failures are sorted.

Latest full backend result:

- Previous exploration: `3100 passed, 67 failed, 13 errors, 1 skipped, 6 xfailed`
- Current restoration pass: `3186 passed, 0 failed, 0 errors, 1 skipped, 6 xfailed`
- Command: `python -m pytest --last-failed -q`

## Restore Production Behavior

- `tests/security/test_api_security.py`: updated the ownership test to mock the current session restoration dependency.
- `tests/test_error_recovery_contract.py`: restored explicit SSE disconnect errors in `frontend/src/lib/sse.ts`.
- `tests/test_story_generator_best_story_db.py`: restored longest generated story fallback when option generation fails after retries.
- `tests/test_scene_image_sse_contract.py`, `tests/test_scene_image_sse_integration.py`: restored scene image SSE event cache, publish helper, and optional-auth event endpoint.
- `tests/test_security_prompt_injection_contract.py`, `tests/test_security_sqlalchemy_raw_sql_contract.py`: restored the sanitized StoryGenerator player-name compatibility entry point and removed the raw f-string SQL static violation.

## Update Obsolete Contracts

- `tests/test_contracts_new_features.py`: reclassified `story_voice_reading` as an explicitly default-enabled shipped feature while keeping other experimental defaults off.
- `tests/test_music_service.py`: updated URL retry coverage to use HTTP 500; HTTP 503 remains fast-degrade per `tests/test_music_degradation_no_mock.py`.

## Reconcile Current Contracts

- `tests/test_chinese_text_normalization_contract.py`: restored compatibility through the current text-quality helper.
- `tests/test_era_validator_integration.py`, `tests/test_era_validator_production_contract.py`, `tests/test_music_era_recommendation_contract.py`: restored validation context extraction and ancient-era music keyword priority together.
- `tests/test_sse_retry_contract.py`: added retry/backoff for streaming choice/custom/opening-story requests in `frontend/src/lib/sse.ts`.
- `tests/test_frontend_contract_alignment.py`: aligned the frontend character-setting type and runtime backend field-name references.
- `tests/test_harness_retry_loop.py`: restored the StoryGenerator temperature resolver used by retry policy tests.
- `tests/test_image_cache_contract.py`: restored public cache headers for immutable image file responses.
- `tests/test_music_router.py`: made router serialization tolerant of current and legacy recommendation/song objects.
- `tests/test_music_cache_contract.py`, `tests/test_music_cache_integration.py`, `tests/test_music_service_health_contract.py`, `tests/test_music_service_url_contract.py`: restored the current product requirement for short URL caching, health availability cache, and container default URL while preserving 503 fast degradation.

## Explicit Exclusions

No maintained-gate exclusions were added in this pass. The previous legacy backend failure inventory is now green locally; future exclusions from an existing maintained gate must include a reason in this file or a successor triage artifact.
