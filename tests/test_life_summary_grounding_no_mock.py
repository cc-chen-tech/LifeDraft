"""No-mock contracts for evidence-grounded life summaries."""

import pytest

from src.services.life_summary_grounding import (
    build_grounded_fallback,
    build_life_summary_prompt,
    validate_or_fallback_life_summary,
)


STORY_HISTORY = [
    {
        "week": 0,
        "round": 0,
        "story_text": "林晓开始调查教育产品的隐私风险。",
        "choice_text": "先核对用户授权记录",
    },
    {
        "week": 1,
        "round": 1,
        "story_text": "团队讨论是否以母亲名义注册公司来规避竞业限制，法律风险尚未确认。",
        "choice_text": "暂停注册并咨询专业人士",
    },
    {
        "week": 2,
        "round": 2,
        "story_text": "一份记录称陆一鸣是顾问，另一份记录仍把他的身份列为待核实。",
        "choice_text": "保留冲突记录",
    },
    {
        "week": 3,
        "round": 2,
        "story_text": "林晓决定暂缓招标，继续核对注册材料和父亲的诊疗信息。",
        "choice_text": "继续查证",
    },
]


def test_prompt_uses_exact_range_evidence_rules_and_no_resource_metrics() -> None:
    prompt = build_life_summary_prompt(STORY_HISTORY, start_week=1, end_week=4)

    assert "第1-4周" in prompt
    assert "只使用下方故事证据" in prompt
    assert "冲突" in prompt and "未决" in prompt
    assert "规避竞业" in prompt and "合规" in prompt
    for removed_metric in ("当前精力", "当前情绪", "当前学识", "当前财富"):
        assert removed_metric not in prompt


def test_prompt_bounds_long_history_while_retaining_timeline_endpoints() -> None:
    long_history = [
        {
            "week": week,
            "round": 0,
            "story_text": f"第{week + 1}周故事证据 " + "细节" * 1_000,
            "choice_text": f"第{week + 1}周选择",
        }
        for week in range(100)
    ]

    prompt = build_life_summary_prompt(long_history, start_week=1, end_week=100)

    assert len(prompt) <= 25_000
    assert "第1周故事证据" in prompt
    assert "第100周选择" in prompt


def test_unsafe_provider_summary_falls_back_to_grounded_exact_range() -> None:
    unsafe = (
        "半年不到，林晓通过母亲名义注册找到了合规路径。"
        "陆一鸣确定是导师，财富达到19.9万元，学识95。"
    )

    result = validate_or_fallback_life_summary(
        unsafe,
        STORY_HISTORY,
        start_week=1,
        end_week=4,
    )

    assert result.startswith("第1-4周：")
    assert "半年" not in result
    assert "合规路径" not in result
    assert "19.9" not in result
    assert "学识95" not in result
    assert "身份列为待核实" in result


def test_provider_history_dump_falls_back_to_a_compact_summary() -> None:
    """A life summary must aggregate history instead of replaying every round."""
    history = [
        {
            "week": week,
            "round": week % 3,
            "story_text": f"第{week + 1}周影院改造事件：" + ("现场细节" * 200),
            "choice_text": f"第{week + 1}周选择：确认本周安排",
        }
        for week in range(9)
    ]
    provider_dump = "\n".join(
        f"{entry['story_text']}\n{entry['choice_text']}" for entry in history
    )

    result = validate_or_fallback_life_summary(
        provider_dump,
        history,
        start_week=1,
        end_week=9,
    )

    assert result.startswith("第1-9周：")
    assert result != provider_dump
    assert len(result) <= len(provider_dump) // 4


def test_safe_grounded_provider_summary_is_preserved() -> None:
    safe = (
        "第1-4周，林晓围绕隐私风险、注册材料和招标安排持续查证。"
        "陆一鸣的身份记录仍有冲突，团队没有把相关法律风险视为已经解决。"
    )

    assert (
        validate_or_fallback_life_summary(
            safe,
            STORY_HISTORY,
            start_week=1,
            end_week=4,
        )
        == safe
    )


def test_tracked_wealth_or_exact_balance_summary_falls_back_even_when_evidenced() -> None:
    history = [
        {
            "week": 0,
            "round": 0,
            "story_text": "林晓的账户余额达到50000元。",
            "choice_text": "继续储蓄",
        }
    ]

    for tracked_summary in (
        "第1周，林晓的财富达到50000元。",
        "第1周，林晓的账户余额达到50000元。",
        "第1周，林晓的当前财富值有所提升。",
        "第1周，林晓的财富不再增长。",
        "第1周，Lin's wealth did not increase.",
        "第1周，林晓的月薪八千元。",
        "第1周，林晓获得奖金三万元。",
        "第1周，林晓的余额五万元。",
    ):
        result = validate_or_fallback_life_summary(
            tracked_summary,
            history,
            start_week=1,
            end_week=1,
        )
        assert result != tracked_summary


def test_qualitative_economic_summary_is_preserved() -> None:
    history = [
        {
            "week": 0,
            "round": 0,
            "story_text": "项目收入有所改善，但家庭仍面临经济压力，消费也更加谨慎。",
            "choice_text": "暂缓非必要开支",
        }
    ]
    summary = "第1周，项目收入有所改善，但家庭仍面临经济压力，消费更加谨慎。"

    assert (
        validate_or_fallback_life_summary(summary, history, start_week=1, end_week=1)
        == summary
    )


@pytest.mark.parametrize(
    "value_statement",
    (
        "财富不代表幸福",
        "财富不能定义成功",
        "wealth does not define success",
        "wealth cannot measure happiness",
    ),
)
def test_non_metric_wealth_value_summary_is_preserved(value_statement: str) -> None:
    history = [
        {
            "week": 0,
            "round": 0,
            "story_text": value_statement,
            "choice_text": "陪伴家人",
        }
    ]
    summary = f"第1周，{value_statement}。"

    assert (
        validate_or_fallback_life_summary(summary, history, start_week=1, end_week=1)
        == summary
    )


def test_deterministic_fallback_uses_source_excerpts_without_metrics_or_legal_endorsement() -> None:
    result = build_grounded_fallback(STORY_HISTORY, start_week=1, end_week=4)

    assert result.startswith("第1-4周：")
    assert "林晓开始调查教育产品的隐私风险" in result
    assert "相关做法存在争议与风险" in result
    assert "合规路径" not in result
    for removed_metric in ("精力", "情绪", "学识", "财富"):
        assert removed_metric not in result
