"""P1-7 authoritative continuity ledger contracts."""

from __future__ import annotations

from src.game.continuity_ledger import ContinuityLedger
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]


@pytest.mark.parametrize("reference", ["明年二月", "来年2月", "去年二月", "前年2月"])
def test_relative_year_reference_is_not_a_claim_about_today(reference):
    ledger = ContinuityLedger.from_player_state(_state())
    result = ledger.validate_story(
        f"八月的粮册已经送到。粮食只够支应到{reference}，必须重新核对。",
        date_info={"year": 1426, "month": 8, "age": 28}, week=0, round_number=0,
    )
    assert not any(issue.code == "date_mismatch" for issue in result.issues)


def test_future_reference_does_not_hide_a_separate_wrong_current_month():
    ledger = ContinuityLedger.from_player_state(_state())
    result = ledger.validate_story(
        "粮食只够支应到明年二月，但今天是二月，账本已经送到。",
        date_info={"year": 1426, "month": 8, "age": 28}, week=0, round_number=0,
    )
    dates = [issue for issue in result.issues if issue.code == "date_mismatch"]
    assert len(dates) == 1
    assert dates[0].observed == "二月"



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


@pytest.mark.parametrize('story', [
    '林见微那时十九岁，刚结束学业。此刻林见微二十八岁，正在整理卷册。',
    '当年十九岁的林见微还在求学，如今林见微二十八岁。',
    '林见微想起十九岁时的往事，此刻林见微二十八岁。',
])
def test_recalled_age_is_not_compared_to_current_age(story):
    ledger = ContinuityLedger.from_player_state(_state())
    issues = ledger.validate_story(story, date_info={'age': 28}, week=0, round_number=0).issues
    assert not any(issue.code == 'age_mismatch' for issue in issues)


@pytest.mark.parametrize('story', [
    '林见微那时十九岁，刚结束学业。此刻林见微三十岁。',
    '当年十九岁的林见微还在求学，如今林见微三十岁。',
    '林见微二十八岁。随后文书又写道，林见微三十岁。',
    '林见微想起十九岁时的往事，此刻林见微三十岁。',
    '林见微三十岁。她想起了童年的旧事。',
])
def test_memory_or_correct_age_cannot_hide_a_wrong_current_age(story):
    ledger = ContinuityLedger.from_player_state(_state())
    issues = ledger.validate_story(story, date_info={'age': 28}, week=0, round_number=0).issues
    ages = [issue for issue in issues if issue.code == 'age_mismatch']
    assert len(ages) == 1
    assert ages[0].observed == '30'


@pytest.mark.parametrize('story', [
    '林见微如今二十八岁。苏晚晴如今四十岁。',
    '林见微的母亲六十岁。',
    '林见微心想：假如林见微现在四十岁，事情会怎样？',
    '如果四十岁的林见微重回这里，她会如何看待此事？',
    '林见微不是四十岁，而是二十八岁。',
    '林见微还不到四十岁。',
    '也许林见微四十岁时会再来这里。',
])
def test_other_people_and_nonfactual_ages_are_not_current_protagonist_claims(story):
    ledger = ContinuityLedger.from_player_state(_state())
    assert ledger._validate_ages(story, {'age': 28}) == []


@pytest.mark.parametrize('prefix', [
    '假如林见微四十岁，事情会怎样？',
    '林见微不是四十岁。',
    '苏晚晴四十岁。',
    '如果林见微四十岁就好了，但事实上',
])
def test_nonfactual_or_npc_age_does_not_hide_real_current_age_conflict(prefix):
    ledger = ContinuityLedger.from_player_state(_state())
    issues = ledger._validate_ages(prefix + '林见微现在三十岁。', {'age': 28})
    assert [(i.subject, i.observed) for i in issues] == [('林见微', '30')]


@pytest.mark.parametrize('story', [
    '林见微想起了从前。十九岁的林见微刚结束学业。',
    '林见微陷入回忆。窗外下着雨。十九岁的林见微刚结束学业。',
    '林见微想起了从前。\n\n十九岁的林见微刚结束学业。',
    '林见微想起了从前。她说：“如今我过得很好。”十九岁的林见微刚结束学业。',
])
def test_flashback_age_context_survives_sentence_and_paragraph_boundaries(story):
    ledger = ContinuityLedger.from_player_state(_state())
    assert ledger._validate_ages(story, {'age': 28}) == []


@pytest.mark.parametrize('transition', ['如今', '此刻', '回到现实。', '她收回思绪。'])
def test_flashback_context_ends_before_wrong_current_age(transition):
    ledger = ContinuityLedger.from_player_state(_state())
    story = '林见微想起了从前。十九岁的林见微刚结束学业。' + transition + '林见微三十岁。'
    assert [(i.subject, i.observed) for i in ledger._validate_ages(story, {'age': 28})] == [('林见微', '30')]


@pytest.mark.parametrize('story', [
    '封皮上有一行小字，是父亲的笔迹——“宣德元年六月，北巡归途所见”。',
    '最后一页上写着：“宣德元年七月，过野狐岭。”',
    '卷宗上写着：“今天是六月初。城门已经打开。”',
    '旧信的落款是2025年6月。',
    '林见微想起了从前。六月的雨下了整夜。',
    '她准备在六月出发。',
])
def test_document_memory_and_planned_dates_are_not_current_date_claims(story):
    ledger = ContinuityLedger.from_player_state(_state())
    assert ledger._validate_dates(story, {'year': 1426, 'month': 8}) == []


@pytest.mark.parametrize('prefix', [
    '卷宗上写着：“今天是六月初。”',
    '林见微想起了从前。六月的雨下了整夜。回到现实。',
    '她准备在明年六月出发，但',
    '',
])
def test_reference_dates_cannot_hide_a_wrong_current_date(prefix):
    ledger = ContinuityLedger.from_player_state(_state())
    issues = ledger._validate_dates(prefix + '今天是七月，街市已经开门。', {'year': 1426, 'month': 8})
    assert [i.observed for i in issues] == ['七月']


def test_direct_dialogue_about_current_date_still_checked():
    ledger = ContinuityLedger.from_player_state(_state())
    issues = ledger._validate_dates('林见微说：“今天是七月。”', {'year': 1426, 'month': 8})
    assert [i.observed for i in issues] == ['七月']


def test_quoted_memory_marker_does_not_hide_current_age_conflict():
    ledger = ContinuityLedger.from_player_state(_state())
    issues = ledger._validate_ages('她读旧信：“想起了从前。”林见微三十岁。', {'age': 28})
    assert [i.observed for i in issues] == ['30']
