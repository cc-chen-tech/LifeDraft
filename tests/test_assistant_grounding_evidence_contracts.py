from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.game.assistant_grounding import (
    MAX_EVIDENCE_RECORDS,
    AssistantEvidence,
    AssistantGroundingService,
    EvidenceRecord,
)


class _PayloadProvider:
    def __init__(self, payloads: list[Any]):
        self._payloads = list(payloads)
        self.calls: list[dict[str, Any]] = []

    def generate_completion_json(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._payloads.pop(0)


def _player_state(
    *, character_settings: dict[str, Any] | None = None
) -> SimpleNamespace:
    return SimpleNamespace(
        character_settings=character_settings
        or {"profile": {"occupation": "architect"}},
        continuity_ledger={
            "immutable_identities": {
                "Alex River": {
                    "canonical_name": "Alex River",
                    "roles": ["architect"],
                    "relationships": ["player"],
                    "aliases": ["A. River"],
                    "source": {"kind": "character_settings"},
                }
            },
            "timeline": [],
            "completed_events": {},
            "mutable_states": {},
        },
    )


def test_evidence_cap_bounds_verbose_character_settings() -> None:
    settings = {f"detail_{index}": f"value-{index}" for index in range(180)}

    evidence = AssistantEvidence.from_player_state(
        _player_state(character_settings=settings)
    )

    assert len(evidence.records) == MAX_EVIDENCE_RECORDS
    assert all(key.startswith("setting:") for key in evidence.records)


def test_evidence_record_omits_unset_optional_fields_from_serialization() -> None:
    record = EvidenceRecord(
        evidence_id="setting:profile.occupation",
        kind="character_setting",
        subject="profile.occupation",
        fact="architect",
    )

    assert record.to_dict() == {
        "kind": "character_setting",
        "subject": "profile.occupation",
        "fact": "architect",
    }


def test_valid_english_answer_returns_retained_identity_citation() -> None:
    provider = _PayloadProvider(
        [
            {
                "reply": "Alex River is an architect.",
                "citations": ["identity:Alex River"],
                "uncertain": False,
            }
        ]
    )

    result = AssistantGroundingService(provider).answer(
        "Who is Alex River?", _player_state(), language="en"
    )

    assert result.reply == "Alex River is an architect."
    assert result.citations == ["identity:Alex River"]
    assert result.uncertain is False
    assert "Authoritative structured evidence" in provider.calls[0]["system_prompt"]


def test_missing_citations_are_retried_before_a_valid_answer_is_returned() -> None:
    provider = _PayloadProvider(
        [
            {
                "reply": "Alex River is an architect.",
                "citations": [],
                "uncertain": False,
            },
            {
                "reply": "Alex River is an architect.",
                "citations": ["identity:Alex River"],
                "uncertain": False,
            },
        ]
    )

    result = AssistantGroundingService(provider).answer(
        "Who is Alex River?", _player_state(), language="en"
    )

    assert result.uncertain is False
    assert len(provider.calls) == 2
    assert "factual answer had no citations" in provider.calls[1]["prompt"]


def test_invalid_payloads_fall_back_after_all_attempts() -> None:
    provider = _PayloadProvider(
        [
            "not a JSON object",
            {
                "reply": "Alex River earned 900 dollars.",
                "citations": ["identity:Alex River"],
                "uncertain": False,
            },
        ]
    )

    result = AssistantGroundingService(provider).answer(
        "Who is Alex River?", _player_state(), language="en"
    )

    assert result.uncertain is True
    assert result.citations == []
    assert result.reply == (
        "I cannot confirm that from the current authoritative game records."
    )
    assert len(provider.calls) == 2


def test_unknown_english_person_returns_uncertainty_without_provider_call() -> None:
    provider = _PayloadProvider([])

    result = AssistantGroundingService(provider).answer(
        "Who is Jordan Blake?", _player_state(), language="en"
    )

    assert result.uncertain is True
    assert result.citations == []
    assert 'could not find "Jordan Blake"' in result.reply
    assert provider.calls == []


def test_uncertain_payload_is_returned_without_citations() -> None:
    provider = _PayloadProvider(
        [
            {
                "reply": "I cannot verify that from the records.",
                "citations": ["identity:Alex River"],
                "uncertain": True,
            }
        ]
    )

    result = AssistantGroundingService(provider).answer(
        "Who is Alex River?", _player_state(), language="en"
    )

    assert result.reply == "I cannot verify that from the records."
    assert result.citations == []
    assert result.uncertain is True
