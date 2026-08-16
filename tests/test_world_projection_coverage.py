import pytest

from src.game.world_projection_coverage import detect_world_change_signals


def test_detects_tracked_movement_commitment_and_causal_signals() -> None:
    signals = detect_world_change_signals(
        "黑袍人抵达东海，并兑现了与孙悟空的约定。龙宫关闭的问题终于解决。",
        ["黑袍人进入龙宫", "黑袍人返回花果山"],
        {
            "character_locations": {"黑袍人": {"location": "花果山"}},
            "causal_chains": [{"cause": "龙宫关闭"}],
        },
    )

    assert signals.requires_nonempty_patch is True
    assert signals.categories == (
        "location_updates",
        "commitment_updates",
        "causal_updates",
    )
    assert "抵达" in signals.matched_spans
    assert "约定" in signals.matched_spans
    assert "解决" in signals.matched_spans


def test_ordinary_observation_does_not_require_world_patch() -> None:
    signals = detect_world_change_signals(
        "孙悟空倚在石边看潮水起落，暂时没有作出决定。",
        ["继续观察", "询问近况"],
        {"character_locations": {"孙悟空": {"location": "花果山"}}},
    )

    assert signals.requires_nonempty_patch is False
    assert signals.categories == ()
    assert signals.matched_spans == ()


def test_movement_and_completed_commitment_use_patch_category_names() -> None:
    signals = detect_world_change_signals(
        "黑袍人抵达东海，完成了与孙悟空同行的约定。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert signals.requires_nonempty_patch is True
    assert set(signals.categories) >= {"location_updates", "commitment_updates"}
    assert "抵达" in signals.matched_spans
    assert "完成" in signals.matched_spans


@pytest.mark.parametrize(
    "location_expression", ["现身", "身处", "位于", "落脚", "驻留", "当前位置改为"]
)
def test_tracked_character_location_expressions_require_a_location_patch(
    location_expression: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人{location_expression}东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories
    assert location_expression in signals.matched_spans


def test_unrelated_option_movement_does_not_upgrade_a_story_mention_to_location_evidence() -> (
    None
):
    signals = detect_world_change_signals(
        "黑袍人今天在花果山休息。",
        ["前往东海"],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert signals.requires_nonempty_patch is False


def test_completed_work_without_commitment_evidence_does_not_require_a_patch() -> None:
    signals = detect_world_change_signals(
        "小明完成了作业。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert signals.requires_nonempty_patch is False
