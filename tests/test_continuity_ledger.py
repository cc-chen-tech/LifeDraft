"""P1-7 authoritative continuity ledger contracts."""

from __future__ import annotations

from src.game.continuity_ledger import ContinuityLedger
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



def _settings() -> dict:
    return {
        "era": {"year": 2026, "era_description": "2026年的上海"},
        "age": {"age": 28, "stage": "青年"},
        "occupation": {"occupation": "纪录片剪辑师", "employer": "自由职业"},
        "family": {
            "family_members": [
                {
                    "name": "林建国",
                    "role": "父亲",
                    "relationship": "父亲",
                    "description": "已经去世的父亲，只能在回忆中出现。",
                },
                {
                    "name": "陈秀兰",
                    "role": "母亲",
                    "relationship": "母亲",
                    "description": "仍在广州生活。",
                },
            ]
        },
        "relationships": {
            "key_people": [
                {
                    "name": "苏晚晴",
                    "role": "摄影师",
                    "relationship": "合作伙伴",
                    "description": "公益纪录片项目的摄影师。",
                },
                {
                    "name": "何志远",
                    "role": "社区协调员",
                    "relationship": "合作伙伴",
                    "description": "负责社区沟通。",
                },
            ]
        },
    }


def _state(*, week: int = 0, current_round: int = 0) -> PlayerState:
    return PlayerState(
        player_name="林见微",
        age=28,
        week=week,
        current_round=current_round,
        character_settings=_settings(),
    )


def test_player_state_round_trips_versioned_continuity_ledger() -> None:
    state = _state()
    ledger = ContinuityLedger.from_player_state(state)
    ledger.persist(state)

    loaded = PlayerState.from_dict(state.to_dict())

    assert loaded.continuity_ledger["version"] == 1
    assert (
        loaded.continuity_ledger["immutable_identities"]["林见微"]["age_baseline"] == 28
    )
    assert (
        loaded.continuity_ledger["immutable_identities"]["林建国"]["life_status"]
        == "deceased"
    )


def test_ledger_seeds_canonical_people_roles_relationships_and_sources() -> None:
    ledger = ContinuityLedger.from_player_state(_state())

    assert set(ledger.immutable_identities) >= {
        "林见微",
        "林建国",
        "陈秀兰",
        "苏晚晴",
        "何志远",
    }
    assert ledger.immutable_identities["苏晚晴"]["roles"] == ["摄影师"]
    assert ledger.immutable_identities["何志远"]["relationships"] == ["合作伙伴"]
    assert (
        ledger.immutable_identities["林建国"]["source"]["kind"] == "character_settings"
    )


def test_snapshot_is_prompt_ready_and_source_aware() -> None:
    ledger = ContinuityLedger.from_player_state(_state())
    ledger.record_committed_event(
        event_id="w0-r0",
        week=0,
        round_number=0,
        date_info={"year": 2026, "month": 1, "week_in_month": 1},
        summary="已经完成社区拍摄许可备案",
        choice="提交备案材料",
        story_text="林见微和何志远提交材料，备案已经完成。",
        fact_updates=[
            {
                "action": "new",
                "subject": "社区拍摄许可备案",
                "category": "completed_event",
                "fact": "备案已经完成",
            }
        ],
    )

    snapshot = ledger.build_constraints_text("zh")

    assert "权威连续性事实账本" in snapshot
    assert "苏晚晴" in snapshot and "摄影师" in snapshot
    assert "2026年1月第1周" in snapshot
    assert "备案已经完成" in snapshot
    assert "w0-r0" in snapshot


def test_deterministic_validation_rejects_wrong_date_and_age() -> None:
    ledger = ContinuityLedger.from_player_state(_state(week=1))

    result = ledger.validate_story(
        "2026年2月初，三十五岁的林见微准备出门。",
        date_info={"year": 2026, "month": 1, "week_in_month": 2, "age": 28},
        week=1,
        round_number=0,
    )

    assert not result.passed
    assert {issue.code for issue in result.issues} >= {"date_mismatch", "age_mismatch"}


def test_deterministic_validation_rejects_active_deceased_character_but_allows_memory() -> (
    None
):
    ledger = ContinuityLedger.from_player_state(_state())

    active = ledger.validate_story(
        "林建国走进会议室，拍了拍林见微的肩膀说他会参加拍摄。",
        date_info={"year": 2026, "month": 1, "week_in_month": 1, "age": 28},
        week=0,
        round_number=0,
    )
    memory = ledger.validate_story(
        "林见微想起已经去世的父亲林建国，回忆中他曾拍着她的肩膀鼓励她。",
        date_info={"year": 2026, "month": 1, "week_in_month": 1, "age": 28},
        week=0,
        round_number=0,
    )

    assert not active.passed
    assert any(issue.code == "deceased_active" for issue in active.issues)
    assert memory.passed


def test_role_drift_requires_an_explicit_transition() -> None:
    ledger = ContinuityLedger.from_player_state(_state())

    drift = ledger.validate_story(
        "苏晚晴作为浦东公立小学副校长主持全校大会。",
        date_info={"year": 2026, "month": 1, "week_in_month": 1, "age": 28},
        week=0,
        round_number=1,
    )
    transition = ledger.validate_story(
        "苏晚晴宣布离开摄影工作，经过公开竞聘后正式转任学校副校长。",
        date_info={"year": 2026, "month": 1, "week_in_month": 1, "age": 28},
        week=0,
        round_number=1,
    )

    assert not drift.passed
    assert any(issue.code == "identity_role_conflict" for issue in drift.issues)
    assert transition.passed


def test_canonical_role_cannot_be_transferred_to_a_renamed_character() -> None:
    ledger = ContinuityLedger.from_player_state(_state())

    result = ledger.validate_story(
        "摄影师苏敏、社区协调员陈志远与林见微确认了拍摄日程。",
        date_info={"year": 2026, "month": 1, "week_in_month": 1, "age": 28},
        week=0,
        round_number=1,
    )

    assert not result.passed
    name_conflicts = [
        issue for issue in result.issues if issue.code == "canonical_name_conflict"
    ]
    assert {issue.subject for issue in name_conflicts} >= {"苏晚晴", "何志远"}
    assert {issue.observed for issue in name_conflicts} >= {"苏敏", "陈志远"}


def test_source_backed_career_transition_becomes_current_role() -> None:
    ledger = ContinuityLedger.from_player_state(_state())
    ledger.record_committed_event(
        event_id="w0-r1",
        week=0,
        round_number=1,
        date_info={"year": 2026, "month": 1, "week_in_month": 1},
        summary="苏晚晴公开竞聘后转任学校副校长",
        choice="支持她的职业转型",
        story_text="苏晚晴宣布离开摄影工作，公开竞聘后正式转任学校副校长。",
        fact_updates=[
            {
                "action": "update",
                "subject": "苏晚晴",
                "category": "career",
                "fact": "学校副校长",
            }
        ],
    )

    result = ledger.validate_story(
        "苏晚晴作为学校副校长主持家长会。",
        date_info={"year": 2026, "month": 1, "week_in_month": 2, "age": 28},
        week=1,
        round_number=0,
    )

    assert result.passed
    assert ledger.mutable_states["facts"]["career:苏晚晴"]["source_event_id"] == "w0-r1"


def test_completed_fact_cannot_silently_roll_back() -> None:
    ledger = ContinuityLedger.from_player_state(_state())
    ledger.record_committed_event(
        event_id="w0-r0",
        week=0,
        round_number=0,
        date_info={"year": 2026, "month": 1, "week_in_month": 1},
        summary="公司注册已经完成",
        choice="领取营业执照",
        story_text="林见微领取营业执照，公司注册已经完成。",
        fact_updates=[
            {
                "action": "new",
                "subject": "公司注册",
                "category": "completed_event",
                "fact": "公司注册已经完成",
            }
        ],
    )

    result = ledger.validate_story(
        "母亲提醒林见微，公司注册还没有办理，下午再去提交申请。",
        date_info={"year": 2026, "month": 1, "week_in_month": 2, "age": 28},
        week=1,
        round_number=0,
    )

    assert not result.passed
    assert any(issue.code == "completed_event_rollback" for issue in result.issues)


def test_committed_events_are_idempotent_and_source_link_mutable_state() -> None:
    state = _state()
    ledger = ContinuityLedger.from_player_state(state)
    kwargs = dict(
        event_id="w0-r0",
        week=0,
        round_number=0,
        date_info={"year": 2026, "month": 1, "week_in_month": 1},
        summary="苏晚晴在拍摄中扭伤脚踝",
        choice="陪她去医院",
        story_text="医生确认苏晚晴轻度扭伤，需要休息。",
        fact_updates=[
            {
                "action": "new",
                "subject": "苏晚晴",
                "category": "health",
                "fact": "轻度脚踝扭伤",
            },
            {
                "action": "new",
                "subject": "苏晚晴",
                "category": "relationship",
                "fact": "与林见微的合作信任加深",
            },
        ],
    )

    ledger.record_committed_event(**kwargs)
    ledger.record_committed_event(**kwargs)

    assert len(ledger.timeline) == 1
    assert ledger.mutable_states["health"]["苏晚晴"]["source_event_id"] == "w0-r0"
    assert (
        ledger.mutable_states["relationships"]["苏晚晴"]["source_event_id"] == "w0-r0"
    )


def test_conflicting_candidate_does_not_overwrite_identity_and_is_audited() -> None:
    ledger = ContinuityLedger.from_player_state(_state())

    accepted = ledger.commit_fact_updates(
        event_id="w0-r1",
        week=0,
        round_number=1,
        story_text="苏晚晴仍负责摄影。",
        fact_updates=[
            {
                "action": "update",
                "subject": "苏晚晴",
                "category": "identity",
                "fact": "浦东公立小学副校长",
            }
        ],
    )

    assert accepted == []
    assert ledger.immutable_identities["苏晚晴"]["roles"] == ["摄影师"]
    assert ledger.conflicts[-1]["code"] == "immutable_identity_update"
    assert ledger.conflicts[-1]["source_event_id"] == "w0-r1"


def test_twelve_round_ledger_keeps_monotonic_dates_and_canonical_identity() -> None:
    ledger = ContinuityLedger.from_player_state(_state())

    for absolute_round in range(12):
        week = absolute_round // 3
        round_number = absolute_round % 3
        event_id = f"w{week}-r{round_number}"
        ledger.record_committed_event(
            event_id=event_id,
            week=week,
            round_number=round_number,
            date_info={"year": 2026, "month": 1, "week_in_month": week + 1},
            summary=f"第{week + 1}周第{round_number + 1}轮完成拍摄筹备",
            choice="继续推进纪录片",
            story_text="林见微与摄影师苏晚晴、社区协调员何志远继续推进纪录片。",
            fact_updates=[],
        )

    assert len(ledger.timeline) == 12
    assert [entry["sequence"] for entry in ledger.timeline] == list(range(12))
    assert ledger.timeline[-1]["week"] == 3
    assert ledger.immutable_identities["苏晚晴"]["roles"] == ["摄影师"]
    assert ledger.conflicts == []
