#!/usr/bin/env bash
set -euo pipefail

mode="${1:-test}"
coverage_xml_path="${COVERAGE_XML_PATH:-coverage.xml}"

maintained_tests=(
  tests/test_gate_preflight_no_mock.py
  tests/test_gate_gameplay_behavior_no_mock.py
  tests/test_gate_static_no_mock.py
  tests/test_imports.py
  tests/test_gate_imports_no_mock.py
  tests/test_api_contract.py
  tests/test_ai_retry_failure_contract_no_mock.py
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
)

case "$mode" in
  test)
    python -m pytest "${maintained_tests[@]}" -v --tb=short
    ;;
  coverage)
    python -m pytest "${maintained_tests[@]}" \
      --cov=src --cov-fail-under=34 \
      --cov-report="xml:${coverage_xml_path}" --cov-report=term
    ;;
  *)
    echo "usage: $0 [test|coverage]" >&2
    exit 2
    ;;
esac
