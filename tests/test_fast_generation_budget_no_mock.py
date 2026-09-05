"""No-mock contracts for quality-aware generation budgets."""

from config.prompts.story_prompts import get_round_event_prompt
from src.ai.generation_budget import get_generation_budget
import pytest

pytestmark = [pytest.mark.unit]



def test_fast_budget_is_materially_smaller_and_has_no_secondary_story_calls() -> None:
    fast = get_generation_budget("fast")
    expert = get_generation_budget("expert")
    master = get_generation_budget("master")

    assert fast.min_length == 350
    assert fast.max_length == 600
    # fast 档 max_tokens 2048 → 4096：与 expert 拉齐，避免 500 字符目标长度
    # 被截断（PR #342 已在主干统一过 max_tokens）。
    assert fast.max_tokens == 4096
    assert fast.allow_quick_regeneration is False
    assert fast.allow_ai_consistency is False
    assert fast.expected_seconds < expert.expected_seconds < master.expected_seconds
    # fast / expert 现在都是 4096；master 更大。三档仍按档位递增。
    assert fast.max_tokens <= expert.max_tokens <= master.max_tokens


def test_fast_round_prompt_uses_fast_length_instead_of_master_length() -> None:
    prompt = get_round_event_prompt(
        player_state={
            "age": 28,
            "week": 1,
            "current_round": 0,
            "rounds_per_week": 3,
            "relationships": {},
        },
        language="zh",
        round_number=0,
        round_context="",
        character_settings={
            "era": {"year": 2026, "era_description": "当代中国"},
            "world": {"world_description": "现实主义产品团队"},
        },
        quality_level="fast",
    )

    assert "350-600字" in prompt
    assert "1500-2000字" not in prompt
    assert "快速模式" in prompt


def test_expert_and_master_prompts_keep_distinct_length_targets() -> None:
    settings = {"era": {"year": 2026, "era_description": "当代"}}
    state = {"age": 28, "week": 1, "current_round": 0, "relationships": {}}

    expert = get_round_event_prompt(state, "zh", 0, "", settings, quality_level="expert")
    master = get_round_event_prompt(state, "zh", 0, "", settings, quality_level="master")

    assert "800-1200字" in expert
    assert "1500-2000字" in master

