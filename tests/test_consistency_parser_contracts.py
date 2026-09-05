"""No-double contracts for local consistency-response parsing."""

import json

from config.prompts.validation_prompts import get_consistency_validation_prompt
from src.ai.consistency_validator import ConsistencyValidator
import pytest

pytestmark = [pytest.mark.unit]



def test_critical_issue_without_should_retry_falls_back_to_retry():
    response = json.dumps(
        {
            "issues": [
                {
                    "dimension": "geographic",
                    "severity": "CRITICAL",
                    "description": "角色跨城瞬移",
                    "fix_suggestion": "补充行程",
                    "reasoning": "与当前位置冲突",
                }
            ]
        },
        ensure_ascii=False,
    )

    result = ConsistencyValidator(None)._parse_validation_response(response, "zh")

    assert result.passed is False
    assert result.has_critical_issues is True
    assert "判断理由：与当前位置冲突" in result.issues[0].fix_suggestion
    assert "地理位置错误" in result.fix_instructions
    assert "存在严重问题" in result.fix_instructions


def test_critical_issue_preserves_exact_story_evidence_for_retry():
    evidence = "孙悟空已经离开东海，却又被写成出现在东海渊底。"
    response = json.dumps(
        {
            "issues": [
                {
                    "dimension": "geographic",
                    "severity": "CRITICAL",
                    "description": "孙悟空的位置与既有移动记录冲突",
                    "evidence": evidence,
                    "fix_suggestion": "先交代返回东海的过程，或删除东海渊底场景",
                }
            ],
            "should_retry": True,
        },
        ensure_ascii=False,
    )

    result = ConsistencyValidator(None)._parse_validation_response(response, "zh")

    assert result.issues[0].evidence == evidence
    assert evidence in result.fix_instructions


def test_english_consistency_prompt_requires_verbatim_evidence():
    prompt = get_consistency_validation_prompt(
        story_text="Sun Wukong left the East Sea.",
        constraints_text="Sun Wukong is currently away from the East Sea.",
        character_settings={},
        language="en",
    )

    assert '"evidence": "The smallest verbatim conflicting excerpt' in prompt


def test_explicit_should_retry_false_keeps_warning_nonblocking():
    response = json.dumps(
        {
            "should_retry": False,
            "issues": [
                {
                    "dimension": "style",
                    "severity": "unexpected",
                    "description": "节奏略平",
                    "fix_suggestion": "增加转折",
                }
            ],
        },
        ensure_ascii=False,
    )

    result = ConsistencyValidator(None)._parse_validation_response(response, "zh")

    assert result.passed is True
    assert result.warning_issues[0].severity == "WARNING"
    assert result.fix_instructions == ""


def test_invalid_json_is_a_hard_validation_failure():
    result = ConsistencyValidator(None)._parse_validation_response("not json", "en")

    assert result.passed is False
    assert result.has_critical_issues is True
    assert result.issues[0].dimension == "validation_response"
    assert "INVALID CONSISTENCY RESPONSE" in result.fix_instructions
