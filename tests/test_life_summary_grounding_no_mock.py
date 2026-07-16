"""No-mock contracts for evidence-grounded life summaries."""

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


def test_deterministic_fallback_uses_source_excerpts_without_metrics_or_legal_endorsement() -> None:
    result = build_grounded_fallback(STORY_HISTORY, start_week=1, end_week=4)

    assert result.startswith("第1-4周：")
    assert "林晓开始调查教育产品的隐私风险" in result
    assert "相关做法存在争议与风险" in result
    assert "合规路径" not in result
    for removed_metric in ("精力", "情绪", "学识", "财富"):
        assert removed_metric not in result
