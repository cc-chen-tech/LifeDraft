"""P1-6 regression tests for the read-only, evidence-grounded assistant."""

from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.game.assistant_grounding import AssistantEvidence, AssistantGroundingService


def _player_state() -> SimpleNamespace:
    return SimpleNamespace(
        player_name="林岚",
        age=31,
        week=4,
        current_round=1,
        character_settings={
            "occupation": {"occupation": "建筑师", "employer": "青禾事务所"},
            "relationships": {
                "key_people": [
                    {"name": "苏敏", "role": "摄影师", "relationship": "好友"}
                ]
            },
        },
        current_event_data={"event_description": "未提交草稿称林岚中了五百万元。"},
        round_history=[{"summary": "自由文本声称林岚已经搬到火星。"}],
        continuity_ledger={
            "version": 1,
            "immutable_identities": {
                "林岚": {
                    "canonical_name": "林岚",
                    "roles": ["建筑师"],
                    "relationships": ["主角"],
                    "life_status": "alive",
                    "age_baseline": 31,
                    "source": {"kind": "character_settings", "path": "player_state"},
                },
                "苏敏": {
                    "canonical_name": "苏敏",
                    "roles": ["摄影师"],
                    "relationships": ["好友"],
                    "life_status": "alive",
                    "source": {
                        "kind": "character_settings",
                        "path": "relationships.key_people",
                    },
                },
            },
            "timeline": [
                {
                    "event_id": "w2-r1",
                    "week": 2,
                    "round": 1,
                    "status": "committed",
                    "date_info": {"year": 2026, "month": 3, "day": 12},
                    "summary": "林岚提交了社区图书馆方案。",
                    "choice": "按时提交",
                },
                {
                    "event_id": "candidate-w5-r1",
                    "week": 5,
                    "round": 1,
                    "status": "pending",
                    "summary": "未来将获得奖金。",
                },
            ],
            "completed_events": {
                "社区图书馆方案": {
                    "subject": "社区图书馆方案",
                    "fact": "已提交并通过初审",
                    "source_event_id": "w2-r1",
                    "effective_week": 2,
                    "effective_round": 1,
                }
            },
            "mutable_states": {
                "health": {},
                "relationships": {
                    "林岚与苏敏": {
                        "subject": "林岚与苏敏",
                        "fact": "互相信任的好友",
                        "source_event_id": "w3-r2",
                        "effective_week": 3,
                        "effective_round": 2,
                    }
                },
                "facts": {
                    "career:林岚": {
                        "subject": "林岚",
                        "category": "career",
                        "fact": "青禾事务所建筑师",
                        "source_event_id": "w1-r1",
                        "effective_week": 1,
                        "effective_round": 1,
                    }
                },
            },
            "corrections": [{"text": "不应暴露给助手"}],
            "conflicts": [{"observed": "林岚搬到火星"}],
        },
    )


def test_evidence_uses_only_allowlisted_structured_authority() -> None:
    evidence = AssistantEvidence.from_player_state(_player_state())
    rendered = evidence.render("zh")

    assert "identity:林岚" in evidence.records
    assert "event:w2-r1" in evidence.records
    assert "completed:社区图书馆方案" in evidence.records
    assert "state:career:林岚" in evidence.records
    assert "自由文本声称" not in rendered
    assert "未提交草稿" not in rendered
    assert "未来将获得奖金" not in rendered
    assert "不应暴露给助手" not in rendered
    assert "搬到火星" not in rendered


def test_supported_answer_must_cite_authoritative_record() -> None:
    ai = MagicMock()
    ai.generate_completion_json.return_value = {
        "reply": "社区图书馆方案已提交并通过初审。",
        "citations": ["completed:社区图书馆方案"],
        "uncertain": False,
    }

    result = AssistantGroundingService(ai).answer(
        "社区图书馆方案怎么样了？", _player_state(), language="zh"
    )

    assert result.reply == "社区图书馆方案已提交并通过初审。"
    assert result.citations == ["completed:社区图书馆方案"]
    assert result.uncertain is False


def test_initial_life_vision_is_available_for_family_location_answers() -> None:
    """Initial player facts must remain answerable after later story prose omits them."""
    player = _player_state()
    player.life_vision = "父母住在宁波，弟弟林涛在杭州读大学。"
    ai = MagicMock()
    ai.generate_completion_json.return_value = {
        "reply": "父母住在宁波。",
        "citations": ["initial:life_vision"],
        "uncertain": False,
    }

    result = AssistantGroundingService(ai, max_attempts=1).answer(
        "父母住在哪里？", player, language="zh"
    )

    assert result.reply == "父母住在宁波。"
    assert result.citations == ["initial:life_vision"]
    assert result.uncertain is False


def test_unknown_person_returns_uncertainty_without_calling_model() -> None:
    ai = MagicMock()

    result = AssistantGroundingService(ai).answer(
        "李华是谁？", _player_state(), language="zh"
    )

    assert result.uncertain is True
    assert "没有找到" in result.reply
    ai.generate_completion_json.assert_not_called()


def test_invalid_citation_retries_once_then_degrades() -> None:
    ai = MagicMock()
    ai.generate_completion_json.side_effect = [
        {"reply": "李华已经结婚。", "citations": ["identity:李华"], "uncertain": False},
        {"reply": "李华住在上海。", "citations": ["event:w99-r1"], "uncertain": False},
    ]

    result = AssistantGroundingService(ai).answer(
        "最近发生了什么？", _player_state(), language="zh"
    )

    assert result.uncertain is True
    assert "权威记录" in result.reply
    assert ai.generate_completion_json.call_count == 2


def test_unsupported_number_is_rejected_even_with_valid_citation() -> None:
    ai = MagicMock()
    ai.generate_completion_json.return_value = {
        "reply": "方案在2028年完成，并获得500万元。",
        "citations": ["completed:社区图书馆方案"],
        "uncertain": False,
    }

    result = AssistantGroundingService(ai, max_attempts=1).answer(
        "方案何时完成？", _player_state(), language="zh"
    )

    assert result.uncertain is True
    assert "无法确认" in result.reply


def test_answer_does_not_mutate_player_state() -> None:
    player = _player_state()
    before = copy.deepcopy(player.__dict__)
    ai = MagicMock()
    ai.generate_completion_json.return_value = {
        "reply": "林岚是建筑师。",
        "citations": ["identity:林岚"],
        "uncertain": False,
    }

    AssistantGroundingService(ai).answer("林岚的职业是什么？", player, language="zh")

    assert player.__dict__ == before


def test_prompt_requires_structured_citations_and_contains_no_story_prose() -> None:
    ai = MagicMock()
    ai.generate_completion_json.return_value = {
        "reply": "林岚是建筑师。",
        "citations": ["identity:林岚"],
        "uncertain": False,
    }

    AssistantGroundingService(ai).answer("林岚的职业是什么？", _player_state())

    call = ai.generate_completion_json.call_args
    prompt = call.kwargs["prompt"]
    system_prompt = call.kwargs["system_prompt"]
    assert "identity:林岚" in system_prompt
    assert "citations" in system_prompt
    assert "未提交草稿" not in system_prompt
    assert "自由文本声称" not in system_prompt
    assert prompt == "林岚的职业是什么？"
