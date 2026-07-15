"""Provider-free contracts for story analysis response parsing."""

import json

from src.ai.story_analyzer import DynamicFact, StoryAnalyzer


def test_analysis_parser_deduplicates_new_fact_ids_and_preserves_provenance() -> None:
    analyzer = StoryAnalyzer(client=None)
    existing = [DynamicFact(fact_id="f_Ada_secret_w6", subject="Ada", fact_type="secret")]
    response = json.dumps(
        {
            "facts": [
                {
                    "action": "new",
                    "fact_type": "secret",
                    "subject": "Ada",
                    "description": "Ada keeps the archive key.",
                    "constraint_text": "The archive key remains with Ada.",
                    "importance": "unsupported",
                    "expiry_week": "next week",
                    "source_excerpt": "Ada put the key away.",
                },
                {"action": "new", "fact_type": "secret", "subject": "", "description": "skip"},
            ]
        }
    )

    facts = analyzer._parse_analysis_response(response, 6, existing, story_hash="story-hash")

    assert len(facts) == 1
    fact = facts[0]
    assert fact.fact_id == "f_Ada_secret_w6_1"
    assert fact.importance == "normal"
    assert fact.expiry_week == -1
    assert fact.source_excerpt == "Ada put the key away."
    assert fact.source_story_hash == "story-hash"


def test_analysis_parser_replaces_and_invalidates_real_dynamic_facts() -> None:
    analyzer = StoryAnalyzer(client=None)
    existing = [
        DynamicFact(
            fact_id="old-location",
            fact_type="location",
            subject="林岚",
            description="住在北京",
        ),
        DynamicFact(
            fact_id="old-injury",
            fact_type="physical",
            subject="林岚",
            description="手臂受伤",
        ),
    ]
    response = json.dumps(
        {
            "facts": [
                {
                    "action": "update",
                    "fact_type": "location",
                    "subject": "林岚",
                    "description": "搬到上海",
                    "constraint_text": "林岚目前在上海。",
                    "related_entities": ["母亲"],
                    "importance": "important",
                },
                {
                    "action": "invalidate",
                    "target_fact_id": "old-injury",
                    "fact_type": "physical",
                    "subject": "林岚",
                    "description": "手臂已经恢复",
                },
            ]
        }
    )

    facts = analyzer._parse_analysis_response(response, 9, existing, story_hash="move-hash")

    assert len(facts) == 1
    assert facts[0].supersedes == "old-location"
    assert facts[0].source_week == 9
    assert facts[0].related_entities == ["母亲"]
    assert facts[0].source_story_hash == "move-hash"
    assert existing[0].active is True
    assert existing[1].active is False


def test_scheduled_commitment_parser_accepts_only_actionable_time_coordinates() -> None:
    analyzer = StoryAnalyzer(client=None)
    response = json.dumps(
        {
            "scheduled_commitments": [
                {
                    "description": "周末与母亲通话",
                    "parties": ["林岚", "母亲"],
                    "time_reference": "本周末",
                    "scheduled_week": 8,
                    "scheduled_round": 2,
                    "importance": "critical",
                    "event_hint": "确认检查结果",
                },
                {
                    "description": "无效轮次",
                    "scheduled_week": 8,
                    "scheduled_round": 5,
                },
                {
                    "description": "缺少时间",
                    "scheduled_week": -1,
                    "scheduled_round": 1,
                },
                {
                    "description": "普通约定",
                    "scheduled_week": 9,
                    "scheduled_round": 0,
                    "importance": "important",
                },
            ]
        }
    )

    commitments = analyzer._parse_scheduled_commitments_response(response)

    assert commitments == [
        {
            "description": "周末与母亲通话",
            "parties": ["林岚", "母亲"],
            "time_reference": "本周末",
            "scheduled_week": 8,
            "scheduled_round": 2,
            "importance": "critical",
            "event_hint": "确认检查结果",
        },
        {
            "description": "普通约定",
            "parties": [],
            "time_reference": "",
            "scheduled_week": 9,
            "scheduled_round": 0,
            "importance": "normal",
            "event_hint": "",
        },
    ]
