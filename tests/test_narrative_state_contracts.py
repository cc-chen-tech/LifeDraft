"""Deterministic PlayerState contracts for NarrativeManager transitions."""

from src.game.narrative_manager import NarrativeManager
from src.game.state import PlayerState
import pytest

pytestmark = [pytest.mark.unit]



def _storyline(description, *, mentioned_week, importance="medium", characters=None):
    return {
        "description": description,
        "created_week": 1,
        "importance": importance,
        "status": "active",
        "related_characters": characters or [],
        "last_mentioned_week": mentioned_week,
    }


class TestNarrativeStateContracts:
    def test_storyline_updates_resolve_expire_demote_and_add_current_context(self):
        player = PlayerState(
            week=30,
            pending_storylines=[
                _storyline("已完成的旧承诺", mentioned_week=29),
                _storyline("长期搁置的普通线", mentioned_week=17),
                _storyline("需要继续推进的重要线", mentioned_week=21, importance="high"),
            ],
        )

        NarrativeManager.process_storyline_updates(
            player,
            [
                {"action": "resolved", "description": "旧承诺"},
                {
                    "action": "new",
                    "description": "本周新的合作机会",
                    "importance": "high",
                    "related_characters": ["林小鹿"],
                },
            ],
        )

        by_description = {item["description"]: item for item in player.pending_storylines}
        assert "已完成的旧承诺" not in by_description
        assert "长期搁置的普通线" not in by_description
        assert by_description["需要继续推进的重要线"]["importance"] == "medium"
        assert by_description["本周新的合作机会"] == {
            "description": "本周新的合作机会",
            "created_week": 30,
            "importance": "high",
            "status": "active",
            "related_characters": ["林小鹿"],
            "last_mentioned_week": 30,
        }

    def test_storyline_continuation_refreshes_last_mentioned_week(self):
        player = PlayerState(
            week=12,
            pending_storylines=[_storyline("导师约定", mentioned_week=4, importance="high")],
        )

        NarrativeManager.process_storyline_updates(
            player, [{"action": "continues", "description": "导师"}]
        )

        assert player.pending_storylines[0]["last_mentioned_week"] == 12
        assert player.pending_storylines[0]["importance"] == "high"

    def test_fact_updates_replace_same_subject_category_and_bound_history(self):
        player = PlayerState(
            week=20,
            established_facts=[
                {
                    "fact": f"历史事实{i}",
                    "subject": f"主体{i}",
                    "category": "situation",
                    "established_week": i,
                }
                for i in range(52)
            ]
            + [
                {
                    "fact": "旧职业",
                    "subject": "林小鹿",
                    "category": "career",
                    "established_week": 1,
                }
            ],
        )

        NarrativeManager.process_fact_updates(
            player,
            [
                {
                    "action": "new",
                    "subject": "林小鹿",
                    "category": "career",
                    "fact": "成为主策划",
                },
                {
                    "action": "update",
                    "subject": "周教授",
                    "category": "relationship",
                    "fact": "确认成为导师",
                },
            ],
        )

        assert len(player.established_facts) == 50
        career_facts = [
            fact
            for fact in player.established_facts
            if fact["subject"] == "林小鹿" and fact["category"] == "career"
        ]
        assert career_facts == [
            {
                "fact": "成为主策划",
                "subject": "林小鹿",
                "category": "career",
                "established_week": 20,
            }
        ]
        assert any(
            fact["subject"] == "周教授" and fact["category"] == "relationship"
            for fact in player.established_facts
        )
        assert min(fact["established_week"] for fact in player.established_facts) >= 4

    def test_seed_updates_normalize_metadata_link_storylines_and_clean_expired_state(self):
        player = PlayerState(
            week=70,
            pending_storylines=[_storyline("和林小鹿的合约", mentioned_week=69, characters=["林小鹿"])],
            foreshadowing_seeds=[
                {
                    "description": "过期线索",
                    "planted_week": 1,
                    "activated": False,
                },
                {
                    "description": "已激活旧线索",
                    "planted_week": 30,
                    "activated": True,
                    "activation_week": 60,
                },
            ],
        )

        NarrativeManager.process_foreshadowing_seeds(
            player,
            [
                {
                    "description": "林小鹿保留了一份旧合约",
                    "original_context": "x" * 100,
                    "related_characters": ["林小鹿"],
                    "seed_type": "opportunity",
                    "obfuscation_level": 3,
                    "narrative_weight": "unexpected",
                    "recycle_method": "unexpected",
                }
            ],
        )

        assert player.foreshadowing_metrics["total_planted"] == 1
        assert player.foreshadowing_metrics["total_expired"] == 1
        assert len(player.foreshadowing_seeds) == 1
        seed = player.foreshadowing_seeds[0]
        assert seed["maturity_weeks"] == 5
        assert seed["obfuscation_level"] == 1.0
        assert seed["narrative_weight"] == "supporting"
        assert seed["recycle_method"] == "echo"
        assert seed["original_context"] == "x" * 80
        assert seed["related_storylines"] == ["和林小鹿的合约"]

    def test_seed_limit_keeps_major_and_newer_active_entries(self):
        player = PlayerState(week=40)
        player.foreshadowing_seeds = [
            {
                "description": "最早的次要线索",
                "planted_week": 1,
                "activated": False,
                "narrative_weight": "minor",
            },
            {
                "description": "重要线索",
                "planted_week": 2,
                "activated": False,
                "narrative_weight": "major",
            },
        ] + [
            {
                "description": f"普通线索{i}",
                "planted_week": i + 3,
                "activated": False,
                "narrative_weight": "supporting",
            }
            for i in range(20)
        ]

        NarrativeManager.process_foreshadowing_seeds(player, [])

        descriptions = {seed["description"] for seed in player.foreshadowing_seeds}
        assert len(player.foreshadowing_seeds) == 20
        assert "重要线索" in descriptions
        assert "最早的次要线索" not in descriptions

    def test_habit_updates_normalize_strengthen_and_keep_top_ten_per_character(self):
        player = PlayerState(week=25)
        player.character_habits = [
            {
                "character": "林小鹿",
                "habit": "写作前先泡茶",
                "category": "behavioral",
                "strength": "emerging",
                "last_seen_week": 5,
            }
        ] + [
            {
                "character": "周教授",
                "habit": f"习惯{i}",
                "category": "behavioral",
                "strength": "strong" if i < 2 else "emerging",
                "last_seen_week": i,
            }
            for i in range(12)
        ]

        NarrativeManager.process_habit_updates(
            player,
            [
                {
                    "action": "new",
                    "character": "林小鹿",
                    "habit": "写作前先泡茶并整理笔记",
                },
                {
                    "action": "new",
                    "character": "陈晓雨",
                    "habit": "随身记录灵感",
                    "category": "invalid",
                    "strength": "invalid",
                },
            ],
        )

        lulu_habit = next(habit for habit in player.character_habits if habit["character"] == "林小鹿")
        assert lulu_habit["strength"] == "moderate"
        xiaoyu_habit = next(habit for habit in player.character_habits if habit["character"] == "陈晓雨")
        assert xiaoyu_habit["category"] == "behavioral"
        assert xiaoyu_habit["strength"] == "emerging"
        professor_habits = [habit for habit in player.character_habits if habit["character"] == "周教授"]
        assert len(professor_habits) == 10
        assert {habit["habit"] for habit in professor_habits}.issuperset({"习惯0", "习惯1"})
        assert "习惯2" not in {habit["habit"] for habit in professor_habits}
