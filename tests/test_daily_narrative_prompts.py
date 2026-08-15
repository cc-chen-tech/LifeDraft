"""Contracts for daily option transitions and first-day narrative framing."""

from config.prompts.story_prompts import (
    build_daily_story_mode_constraint,
    get_options_only_prompt,
    get_round_event_prompt,
)
from src.ai.daily_opening import validate_daily_first_opening


def _daily_state(day_index: int = 0) -> dict:
    return {
        "age": 28,
        "week": 0,
        "current_round": 0,
        "rounds_per_week": 3,
        "player_name": "林岚",
        "life_vision": "建立一间让普通人安心阅读的社区书店",
        "relationships": {},
        "timeline": {
            "version": 2,
            "day_index": day_index,
            "day_number": day_index + 1,
            "current_date": f"2026-08-{13 + day_index:02d}",
        },
        "day_history": [],
    }


def _settings() -> dict:
    return {
        "name": "林岚",
        "era": {"year": 2026, "era_description": "当代中国"},
        "world": {"world_description": "现实主义社区生活"},
        "traits": {"traits_description": "谨慎，却不愿放弃理想"},
    }


def test_daily_option_prompt_requests_hidden_transition_for_every_option() -> None:
    state = _daily_state(day_index=2)
    state["day_history"] = [
        {"transition_text": "那份迟疑没有散去，天色已慢慢转向明日。"}
    ]

    prompt = get_options_only_prompt(
        "故事结尾需要林岚作出决定。", state, _settings(), "zh"
    )

    assert '"transition_text"' in prompt
    assert "12-28个汉字" in prompt
    assert "那份迟疑没有散去" in prompt
    assert "不预言未发生的结果" in prompt


def test_legacy_option_prompt_keeps_old_schema() -> None:
    state = _daily_state()
    state["timeline"] = {"version": 1}

    prompt = get_options_only_prompt("故事结尾需要决定。", state, _settings(), "zh")

    assert '"transition_text"' not in prompt


def test_daily_round_prompt_does_not_require_week_or_round_titles() -> None:
    prompt = get_round_event_prompt(
        _daily_state(), "zh", 0, "", _settings(), quality_level="fast"
    )

    assert "时间线标题约束" not in prompt
    assert "第1周的周一" not in prompt
    assert "第1周 - 周一" not in prompt
    assert "现在请开始写周一的故事" not in prompt
    assert "日期由界面统一展示" in prompt


def test_first_day_constraint_is_personalized_and_only_applies_once() -> None:
    first = build_daily_story_mode_constraint(_daily_state(), _settings(), "zh")
    second = build_daily_story_mode_constraint(
        _daily_state(day_index=1), _settings(), "zh"
    )

    assert "林岚" in first
    assert "社区书店" in first
    assert "第一段只能有一句" in first
    assert "第二段" in first
    assert "命运的齿轮" in first
    assert "第一段只能有一句" not in second


def test_first_day_opening_validator_enforces_name_sentence_paragraph_and_cliches() -> (
    None
):
    state = _daily_state()
    valid = "林岚把开一间社区书店的愿望，压进眼前这份难以签字的租约里。\n\n清晨的旧街刚刚醒来，她站在落灰的门面前重新核对条款。"

    assert validate_daily_first_opening(valid, state, _settings(), "zh") == []
    assert "daily_opening_missing_protagonist" in validate_daily_first_opening(
        "她仍想把书店开起来。\n\n清晨，她来到门面前。",
        state,
        _settings(),
        "zh",
    )
    assert "daily_opening_not_single_sentence" in validate_daily_first_opening(
        "林岚想开书店。她仍有疑虑。\n\n清晨，她来到门面前。",
        state,
        _settings(),
        "zh",
    )
    assert "daily_opening_cliche" in validate_daily_first_opening(
        "命运的齿轮推动林岚走向书店。\n\n清晨，她来到门面前。",
        state,
        _settings(),
        "zh",
    )
    assert "daily_opening_missing_second_paragraph" in validate_daily_first_opening(
        "林岚把开书店的愿望放进今天的抉择里。",
        state,
        _settings(),
        "zh",
    )


def test_first_day_validator_is_inactive_after_day_zero() -> None:
    assert (
        validate_daily_first_opening(
            "第二天不再强制首句结构。", _daily_state(day_index=1), _settings(), "zh"
        )
        == []
    )


def test_daily_validator_rejects_legacy_week_or_chapter_heading_on_later_days() -> None:
    issues = validate_daily_first_opening(
        "第1周·周中 河边仓库\n\n林岚沿着河岸继续调查。",
        _daily_state(day_index=1),
        _settings(),
        "zh",
    )

    assert "daily_story_heading_forbidden" in issues
