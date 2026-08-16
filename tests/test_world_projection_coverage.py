import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Optional

import pytest

import src.game.world_projection_coverage as world_projection_coverage
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


@pytest.mark.parametrize(
    "noun_prefixed_clause",
    ["但孙悟空决定留守", "然而猪八戒说自己不走", "路人决定继续赶路", "小李决定留下"],
)
def test_nominal_prefixes_conservatively_reset_a_carried_subject(
    noun_prefixed_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{noun_prefixed_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" not in signals.categories


@pytest.mark.parametrize(
    "noun_prefixed_clause",
    [
        "向导决定留守",
        "对手说自己不走",
        "把手决定离开",
        "路人决定继续赶路",
        "小李决定留下",
    ],
)
def test_pos_noun_subjects_reset_a_carried_location_subject(
    noun_prefixed_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{noun_prefixed_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" not in signals.categories


@pytest.mark.parametrize(
    "subjectless_clause",
    [
        "但还是向朋友道别",
        "然而最终抵达东海",
        "最终抵达东海",
        "并且继续向东海前进",
        "继续向东海前进",
        "已抵达东海",
    ],
)
def test_pos_subjectless_clauses_preserve_a_carried_location_subject(
    subjectless_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{subjectless_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories


def test_missing_pos_dependency_fails_closed_without_inheriting_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        world_projection_coverage, "_JiebaTokenizer", None, raising=False
    )
    monkeypatch.setattr(
        world_projection_coverage, "_JiebaPOSTokenizer", None, raising=False
    )
    monkeypatch.setattr(
        world_projection_coverage, "_pos_tokenizer", None, raising=False
    )
    monkeypatch.setattr(world_projection_coverage, "_pos_tagger", None, raising=False)

    signals = detect_world_change_signals(
        "黑袍人收拾行囊，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" not in signals.categories


def test_jieba_token_sequence_distinguishes_noun_like_prefixes_from_prepositions() -> (
    None
):
    noun_signals = detect_world_change_signals(
        "黑袍人收拾行囊，向导决定留守，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )
    preposition_signals = detect_world_change_signals(
        "黑袍人收拾行囊，向朋友道别，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" not in noun_signals.categories
    assert "location_updates" in preposition_signals.categories


def test_jieba_pos_singleton_initializes_once_and_serializes_concurrent_cuts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initialized = 0
    active_cuts = 0
    max_active_cuts = 0
    counter_lock = threading.Lock()

    class FakeTokenizer:
        def __init__(self) -> None:
            nonlocal initialized
            with counter_lock:
                initialized += 1
            time.sleep(0.01)

    class FakePOSTokenizer:
        def __init__(self, tokenizer: FakeTokenizer) -> None:
            del tokenizer

        def cut(self, _text: str):  # type: ignore[no-untyped-def]
            nonlocal active_cuts, max_active_cuts
            with counter_lock:
                active_cuts += 1
                max_active_cuts = max(max_active_cuts, active_cuts)
            time.sleep(0.01)
            with counter_lock:
                active_cuts -= 1
            return [
                SimpleNamespace(word="抵达", flag="v"),
                SimpleNamespace(word="东海", flag="ns"),
            ]

    monkeypatch.setattr(
        world_projection_coverage, "_JiebaTokenizer", FakeTokenizer, raising=False
    )
    monkeypatch.setattr(
        world_projection_coverage,
        "_JiebaPOSTokenizer",
        FakePOSTokenizer,
        raising=False,
    )
    monkeypatch.setattr(
        world_projection_coverage, "_pos_tokenizer", None, raising=False
    )
    monkeypatch.setattr(world_projection_coverage, "_pos_tagger", None, raising=False)

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(
            executor.map(world_projection_coverage._pos_tokens, ["抵达东海"] * 12)
        )

    expected = (("抵达", "v"), ("东海", "ns"))
    serial_result = world_projection_coverage._pos_tokens("抵达东海")
    assert serial_result == expected
    assert results == [serial_result] * 12
    assert initialized == 1
    assert max_active_cuts == 1


@pytest.mark.parametrize("prepositional_clause", ["在东海落脚", "向朋友道别"])
def test_full_prepositional_action_sequences_preserve_a_carried_subject(
    prepositional_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{prepositional_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories


def test_relative_prepositional_phrase_resets_before_a_new_person_subject() -> None:
    signals = detect_world_change_signals(
        "黑袍人收拾行囊，在东海的孙悟空决定留守，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" not in signals.categories


@pytest.mark.parametrize(
    ("candidate", "tracked_names", "expected_subject"),
    [
        ("那个黑袍人抵达东海", ("黑袍人",), "黑袍人"),
        ("那个孙悟空决定留守", ("黑袍人", "孙悟空"), "孙悟空"),
        ("那个猪八戒抵达东海", ("黑袍人", "孙悟空"), None),
    ],
)
def test_determiner_prefixed_token_spans_bind_only_exact_known_names(
    candidate: str,
    tracked_names: tuple[str, ...],
    expected_subject: Optional[str],
) -> None:
    assert (
        world_projection_coverage._leading_tracked_name(candidate, tracked_names)
        == expected_subject
    )


@pytest.mark.parametrize(
    "relative_location_clause",
    ["向朋友的住所前进", "在东海的街道前进", "在码头的客栈落脚"],
)
def test_relative_location_or_object_phrases_keep_a_subjectless_movement(
    relative_location_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{relative_location_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories


@pytest.mark.parametrize(
    "relative_person_clause",
    ["在东海的路人决定留守", "在东海的路人抵达东海"],
)
def test_relative_person_subjects_reset_before_subject_or_movement_predicates(
    relative_person_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{relative_person_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" not in signals.categories


@pytest.mark.parametrize(
    "unknown_person_clause",
    [
        "在东海的猪八戒前进",
        "在东海的游客前进",
        "在东海的导游前进",
        "在东海的路人落脚",
    ],
)
def test_unknown_relative_nouns_fail_closed_without_a_person_role_list(
    unknown_person_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{unknown_person_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" not in signals.categories


@pytest.mark.parametrize(
    "relative_tracked_clause", ["在东海的黑袍人等待", "在东海的孙悟空等待"]
)
def test_relative_exact_tracked_names_rebind_the_active_subject(
    relative_tracked_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{relative_tracked_clause}，抵达东海。",
        [],
        {
            "character_locations": {
                "黑袍人": {"location": "花果山"},
                "孙悟空": {"location": "东海"},
            }
        },
    )

    assert "location_updates" in signals.categories


@pytest.mark.parametrize(
    "relative_place_clause",
    ["向朋友的住所赶路", "在东海的街道等待", "在码头的客栈落脚"],
)
def test_proven_relative_locations_or_objects_carry_through_any_predicate(
    relative_place_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{relative_place_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories


def test_tracked_state_landmarks_prove_relative_location_objects() -> None:
    signals = detect_world_change_signals(
        "黑袍人收拾行囊，在云梦泽的石桥等待，抵达东海。",
        [],
        {
            "character_locations": {"黑袍人": {"location": "花果山"}},
            "landmarks": {"石桥": {"location": "云梦泽"}},
        },
    )

    assert "location_updates" in signals.categories


@pytest.mark.parametrize(
    "relative_place_clause",
    ["在东海的花园等待", "在东海的山洞赶路", "在东海的竹林小屋等待"],
)
def test_location_object_suffixes_prove_unlisted_relative_places(
    relative_place_clause: str,
) -> None:
    signals = detect_world_change_signals(
        f"黑袍人收拾行囊，{relative_place_clause}，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "花果山"}}},
    )

    assert "location_updates" in signals.categories


def test_legacy_character_location_string_proves_a_relative_place() -> None:
    signals = detect_world_change_signals(
        "黑袍人收拾行囊，在东海的甲地等待，抵达东海。",
        [],
        {"character_locations": {"黑袍人": "甲地"}},
    )

    assert "location_updates" in signals.categories


def test_known_location_before_a_relative_unknown_person_does_not_allow_carry() -> None:
    signals = detect_world_change_signals(
        "黑袍人收拾行囊，在东海的游客等待，抵达东海。",
        [],
        {"character_locations": {"黑袍人": {"location": "东海"}}},
    )

    assert "location_updates" not in signals.categories
