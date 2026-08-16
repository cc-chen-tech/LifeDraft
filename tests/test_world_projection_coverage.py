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


def test_adjacent_chinese_clauses_keep_a_tracked_subject_for_location_evidence() -> (
    None
):
    signals = detect_world_change_signals(
        "黑袍人一路奔波，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories
    assert "抵达" in signals.matched_spans


def test_known_record_people_metadata_is_not_commitment_or_causal_evidence() -> None:
    commitment_signals = detect_world_change_signals(
        "孙悟空完成了作业。",
        [],
        {"commitments": [{"description": "明日在东海会面", "parties": ["孙悟空"]}]},
    )
    causal_signals = detect_world_change_signals(
        "孙悟空解决了作业问题。",
        [],
        {"causal_chains": [{"cause": "龙宫关闭", "characters": ["孙悟空"]}]},
    )

    assert "commitment_updates" not in commitment_signals.categories
    assert "causal_updates" not in causal_signals.categories


def test_tracked_subject_stays_bound_across_short_same_sentence_clauses() -> None:
    signals = detect_world_change_signals(
        "黑袍人收拾行囊，向朋友道别，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories
    assert "抵达" in signals.matched_spans


def test_explicit_new_subject_resets_same_sentence_location_binding() -> None:
    signals = detect_world_change_signals(
        "黑袍人收拾行囊，孙悟空向朋友道别，抵达东海。",
        [],
        {
            "character_locations": {"黑袍人": {"location": "花果山"}},
            "commitments": [{"description": "明日在东海会面", "parties": ["孙悟空"]}],
        },
    )

    assert "location_updates" not in signals.categories


@pytest.mark.parametrize(
    "new_subject_clause", ["孙悟空决定留守花果山", "孙悟空说自己不走"]
)
def test_known_person_boundaries_reset_subject_without_a_verb_whitelist(
    new_subject_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{new_subject_clause}，抵达东海。",
        [],
        {
            "character_locations": {"黑袍人": {"location": "花果山"}},
            "commitments": [{"description": "明日在东海会面", "parties": ["孙悟空"]}],
        },
    )

    assert "location_updates" not in signals.categories


def test_time_connector_does_not_displace_the_carried_tracked_subject() -> None:
    signals = detect_world_change_signals(
        "黑袍人收拾行囊，随后向朋友道别，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories


def test_time_connector_before_known_person_resets_the_carried_subject() -> None:
    signals = detect_world_change_signals(
        "黑袍人收拾行囊，此时孙悟空向朋友道别，抵达东海。",
        [],
        {
            "character_locations": {"黑袍人": {"location": "花果山"}},
            "commitments": [{"description": "明日在东海会面", "parties": ["孙悟空"]}],
        },
    )

    assert "location_updates" not in signals.categories
