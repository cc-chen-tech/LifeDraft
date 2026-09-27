#!/usr/bin/env bash
set -euo pipefail

mode="${1:-test}"
coverage_xml_path="${COVERAGE_XML_PATH:-coverage.xml}"

maintained_tests=(
  tests/test_story_origin_generation.py
  tests/test_ai_client_thinking_contract.py
  tests/test_daily_recommended_prefetch.py
  tests/test_entity_collection_reliability_no_mock.py
  tests/test_entity_collection_reliability_db_no_mock.py
  tests/test_collection_entity_lifecycle_db_contracts.py
  tests/test_narration_plan_contract.py
  tests/test_story_voice_recovery.py
  tests/test_story_voice_shutdown.py
  tests/test_minimax_tts_shutdown.py
  tests/test_story_voice_io_isolation.py
  tests/test_minimax_tts_receive_deadlines.py
  tests/test_portrait_image_jobs.py
  tests/test_portrait_image_jobs_api.py
  tests/test_api_portrait_candidates.py
  tests/test_portrait_candidates.py
  tests/test_portrait_origin_fence.py
  tests/test_round_illustration_contracts.py
  tests/test_image_service_persistence_contracts.py
  tests/test_diagnostic_lifecycle.py
  tests/test_request_observability.py
  tests/test_model_telemetry.py
  tests/test_model_provider_telemetry.py
  tests/test_image_diagnostics.py
  tests/test_voice_diagnostics.py
  tests/test_voice_enqueue_trace.py
  tests/test_voice_audio_ownership.py
  tests/test_story_delivery_diagnostics.py
  tests/test_gate_preflight_no_mock.py
  tests/test_gate_gameplay_behavior_no_mock.py
  tests/test_gate_static_no_mock.py
  tests/test_imports.py
  tests/test_model_smoke_cli.py
  tests/test_model_smoke_contract.py
  tests/test_gate_imports_no_mock.py
  tests/test_api_contract.py
  tests/test_public_story_plaza.py
  tests/test_ai_retry_failure_contract_no_mock.py
  tests/test_daily_opening_delivery.py
  tests/test_era_context_regnal_dates.py
  tests/test_continuity_ledger.py
  tests/test_collection_field_db_contract_no_mock.py
  tests/test_gate_contracts_no_mock.py
  tests/test_shift_left_e2e_contract_no_mock.py
  tests/test_choice_sse_stream_contracts.py
  tests/test_session_store_replay_contracts.py
  tests/test_active_game_owner_recovery_db_no_mock.py
  tests/test_round_event_sse_terminal_contracts.py
  tests/test_image_service_db_failure_contracts.py
  tests/test_story_voice_reading_contract.py
  tests/test_story_voice_chapter_contract.py
  tests/test_story_voice_routes_v2.py
  tests/test_music_runtime_removed.py
  tests/test_integration_real_db.py
  tests/test_database.py
  tests/test_gate_real_db_no_mock.py
  tests/test_scene_image_sse_replay_contract_no_mock.py
  tests/test_session_recovery_db_contract_no_mock.py
  tests/test_story_voice_reading_db.py
  tests/test_story_voice_async_chapter.py
  tests/test_world_model_lifecycle_contracts.py
  tests/test_database_runner_isolation_no_mock.py
  tests/test_ci_workflow_governance_no_mock.py
  tests/test_daily_world_projection_repair_scan.py
  tests/test_daily_world_projection_backup.py
  tests/test_daily_world_projection_repair_audit.py
  tests/test_repair_daily_world_projections_cli.py
  tests/test_daily_world_projection_rebuild.py
  tests/test_daily_world_projection_observability.py
  tests/test_world_projection_repair_runbook.py
)

case "$mode" in
  test)
    pytest_command=(python -m pytest "${maintained_tests[@]}" -v --tb=short)
    ;;
  coverage)
    pytest_command=(python -m pytest "${maintained_tests[@]}" \
      --cov=src --cov-fail-under=34 \
      --cov-report="xml:${coverage_xml_path}" --cov-report=term)
    ;;
  *)
    echo "usage: $0 [test|coverage]" >&2
    exit 2
    ;;
esac

isolated_database_root="${TEST_RUN_DIR:-}"
if [ -n "$isolated_database_root" ]; then
  isolated_database_root="$isolated_database_root/data/maintained-backend"
else
  isolated_database_root="${TEST_RUN_ROOT:-${TMPDIR:-/tmp}/story2-test-runs}/maintained-backend"
fi

"$(dirname "$0")/run-with-isolated-test-database.sh" \
  "$isolated_database_root" \
  python \
  "${pytest_command[@]}"
