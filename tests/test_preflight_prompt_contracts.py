"""Deterministic contracts for prompt preflight completeness checks."""

from src.ai.harness.constraint_registry import ConstraintRegistry
from src.ai.harness.preflight_checker import PreflightChecker


def _checker() -> PreflightChecker:
    return PreflightChecker(ConstraintRegistry())


def _complete_context() -> dict:
    return {
        "available_people": ["李逍遥"],
        "established_facts": [],
        "pending_storylines": ["寻找灵药"],
        "overdue_storylines": ["师门承诺"],
        "character_habits": ["晨练"],
        "world_model_state": {"week": 3},
        "last_location": "洛阳",
    }


def _complete_prompt() -> str:
    markers = "可用人物 世界事实 世界模型约束 剧情线 习惯 伏笔 [MUST]"
    return (markers + "\n") * 200


def test_complete_prompt_has_no_missing_constraints_or_warnings():
    result = _checker().check_prompt_completeness(_complete_prompt(), _complete_context())

    assert result.all_present is True
    assert result.missing_constraints == []
    assert result.warnings == []
    assert all(result.context_completeness.values())


def test_missing_markers_and_critical_context_are_reported():
    result = _checker().check_prompt_completeness("短提示词", {"established_facts": []})

    assert result.all_present is False
    assert "available_people" in result.missing_constraints
    assert "world_model" in result.missing_constraints
    assert "关键上下文数据缺失: available_people" in result.warnings
    assert "Prompt 中未检测到 [MUST] 约束标记" in result.warnings


def test_long_prompt_reports_token_warning_after_marker_check():
    prompt = _complete_prompt() + ("内容" * 11000)

    result = _checker().check_prompt_completeness(prompt, _complete_context())

    assert result.all_present is True
    assert result.prompt_token_estimate > 8000
    assert any("Prompt 过长" in warning for warning in result.warnings)


def test_optional_context_fields_are_reported_without_being_critical():
    context = {"available_people": ["李逍遥"], "established_facts": []}

    result = _checker().check_prompt_completeness(_complete_prompt(), context)

    assert result.context_completeness["available_people"] is True
    assert result.context_completeness["established_facts"] is True
    assert result.context_completeness["pending_storylines"] is False
    assert not any("关键上下文数据缺失" in warning for warning in result.warnings)
