"""Rejected model evidence is recoverable without exposing private text in logs."""
import json
import logging

import pytest

from config.logging_config import JsonLogFormatter
from src.observability.diagnostics import diagnostic_context
from src.observability.validation_evidence import emit_validation_evidence, decrypt_validation_evidence

pytestmark = pytest.mark.unit


def test_rejection_can_be_investigated_and_keeps_relative_date_context(monkeypatch, caplog):
    monkeypatch.setenv("JWT_SECRET", "test-evidence-key-a")
    caplog.set_level(logging.INFO)
    with diagnostic_context(user_id=7, game_id=31, operation_id="story:31", attempt_id="story:31:2"):
        payload = emit_validation_evidence("consistency_repair", [{
            "code": "date_mismatch", "description": "当前八月，正文写成二月",
            "evidence": "二月", "repair_instruction": "修正日期", "severity": "CRITICAL",
        }], story_text="粮食只够支应到明年二月，但今天仍是八月。")
    rendered = json.dumps([json.loads(JsonLogFormatter().format(r)) for r in caplog.records], ensure_ascii=False)
    assert "明年二月" not in rendered and "修正日期" not in rendered
    recovered = decrypt_validation_evidence(payload, user_id=7, operation_id="story:31")
    assert recovered["issues"][0]["description"] == "当前八月，正文写成二月"
    assert "明年二月" in recovered["issues"][0]["evidence_context"]
    assert recovered["attempt_id"] == "story:31:2"
    assert recovered["game_id"] == 31
    assert payload["encrypted_evidence"] in rendered


def test_owner_and_request_must_match_authenticated_encrypted_record(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-evidence-key-a")
    with diagnostic_context(user_id=7, operation_id="story:31"):
        payload = emit_validation_evidence("quick", [{"description": "私密拒稿"}])
    for uid, operation in [(8, "story:31"), (7, "story:32")]:
        with pytest.raises(ValueError, match="identity"):
            decrypt_validation_evidence(payload, user_id=uid, operation_id=operation)
    tampered = {**payload, "user_id": 8}
    with pytest.raises(ValueError, match="identity"):
        decrypt_validation_evidence(tampered, user_id=8, operation_id="story:31")


def test_wrong_key_cannot_decrypt(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-evidence-key-a")
    with diagnostic_context(user_id=7, operation_id="story:31"):
        payload = emit_validation_evidence("quick", [{"description": "私密拒稿"}])
    monkeypatch.setenv("JWT_SECRET", "test-evidence-key-b")
    with pytest.raises(ValueError, match="key"):
        decrypt_validation_evidence(payload, user_id=7, operation_id="story:31")


def test_evidence_is_bounded_and_credentials_redacted_before_encryption(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-evidence-key-a")
    monkeypatch.setenv("OPENAI_API_KEY", "test-live-credential-value")
    with diagnostic_context(user_id=7, operation_id="story:31"):
        payload = emit_validation_evidence("quick", [{
            "description": "Authorization: Bearer abc-secret sk-secret test-live-credential-value " + "秘" * 2000,
            "prompt": "must not be retained", "evidence": "秘" * 2000,
        }] * 100, story_text="秘" * 100000)
    recovered = decrypt_validation_evidence(payload, user_id=7, operation_id="story:31")
    serialized = json.dumps(recovered, ensure_ascii=False)
    assert all(s not in serialized for s in ["abc-secret", "sk-secret", "test-live-credential-value", "must not be retained"])
    assert len(payload["encrypted_evidence"]) < 32768
    assert recovered["truncated_issue_count"] > 0


def test_missing_key_is_observable_without_losing_generation(monkeypatch, caplog):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("DIAGNOSTIC_EVIDENCE_KEY", raising=False)
    caplog.set_level(logging.INFO)
    payload = emit_validation_evidence("quick", [{"description": "private rejected story"}])
    assert payload["outcome"] == "failed"
    assert payload["error_code"] == "validation_evidence_unavailable"
    assert "private rejected story" not in caplog.text


def test_operator_reader_filters_two_users_and_rotated_duplicates(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from scripts.read_validation_evidence import read_evidence
    monkeypatch.setenv("JWT_SECRET", "test-evidence-key-a")
    def record(user):
        with diagnostic_context(user_id=user, operation_id=f"story:{user}"):
            return emit_validation_evidence("quick", [{"description": f"user {user} rejected"}])
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(record, [7, 8]))
    path = tmp_path / "app.log"
    path.write_text("legacy line\n" + "\n".join(json.dumps(row) for row in rows))
    recovered = list(read_evidence([path, path], user_id=7, operation_id="story:7"))
    assert len(recovered) == 1
    assert recovered[0]["issues"][0]["description"] == "user 7 rejected"


def test_encryption_failure_has_a_terminal_diagnostic(monkeypatch, caplog):
    import src.observability.validation_evidence as module
    def fail():
        raise OSError("private backend failure")
    monkeypatch.setattr(module, "_cipher", fail)
    caplog.set_level(logging.INFO)
    payload = emit_validation_evidence("repair", [{"description": "private story"}])
    assert payload["error_code"] == "validation_evidence_unavailable"
    assert payload["exception_type"] == "OSError"
    assert "private" not in caplog.text
