from src.game.narrative_manager import NarrativeManager
from src.game.state import PlayerState


def _storyline(description: str, importance: str, last_mentioned_week: int, **extra: object) -> dict[str, object]:
    return {
        "description": description,
        "importance": importance,
        "last_mentioned_week": last_mentioned_week,
        **extra,
    }


def _habit(character: str, habit: str, strength: str, last_seen_week: int = 1) -> dict[str, object]:
    return {
        "character": character,
        "habit": habit,
        "strength": strength,
        "last_seen_week": last_seen_week,
        "category": "behavioral",
    }


def test_overdue_storylines_escalate_at_urgent_and_ordinary_thresholds_once() -> None:
    player = PlayerState(
        week=20,
        pending_storylines=[
            _storyline("月底前完成画展约定", "high", 17),
            _storyline("主线调查持续推进", "high", 15),
            _storyline("下月讨论新合作", "high", 18),
            _storyline("普通支线已经搁置", "medium", 1),
            _storyline("已升级承诺", "high", 1, overdue=True, overdue_since_week=10),
        ],
    )

    assert NarrativeManager.escalate_overdue_storylines(player) == 2
    assert player.pending_storylines[0]["overdue"] is True
    assert player.pending_storylines[0]["overdue_since_week"] == 20
    assert player.pending_storylines[1]["overdue"] is True
    assert "overdue" not in player.pending_storylines[2]
    assert "overdue" not in player.pending_storylines[3]
    assert player.pending_storylines[4]["overdue_since_week"] == 10
    assert NarrativeManager.escalate_overdue_storylines(player) == 0


def test_habit_maintenance_weakens_removes_and_replaces_known_habits() -> None:
    player = PlayerState(week=20)
    player.character_habits = [
        _habit("Mina", "reviews notes", "moderate", 4),
        _habit("Kai", "morning run", "emerging", 5),
        _habit("Liu", "arrives late", "moderate", 6),
        _habit("Zhou", "brews tea", "strong", 7),
    ]

    NarrativeManager.process_habit_updates(
        player,
        [
            {"action": "weaken", "character": "Mina", "habit": "notes"},
            {"action": "weaken", "character": "Kai", "habit": "morning run"},
            {
                "action": "change",
                "character": "Liu",
                "old_habit": "arrives late",
                "new_habit": "arrives early",
                "category": "social",
                "strength": "strong",
            },
            {"action": "remove", "character": "Zhou", "habit": "tea"},
        ],
    )

    by_character = {habit["character"]: habit for habit in player.character_habits}
    assert by_character["Mina"]["strength"] == "emerging"
    assert by_character["Mina"]["last_seen_week"] == 20
    assert "Kai" not in by_character
    assert by_character["Liu"] == {
        "character": "Liu",
        "habit": "arrives early",
        "strength": "strong",
        "last_seen_week": 20,
        "category": "social",
    }
    assert "Zhou" not in by_character


def test_changing_a_missing_habit_creates_a_normalized_record() -> None:
    player = PlayerState(week=9)

    NarrativeManager.process_habit_updates(
        player,
        [
            {
                "action": "change",
                "character": "Avery",
                "old_habit": "old routine",
                "new_habit": "writes a daily plan",
                "category": "unsupported",
                "strength": "unsupported",
                "reason": "new job",
            }
        ],
    )

    assert player.character_habits == [
        {
            "character": "Avery",
            "habit": "writes a daily plan",
            "category": "behavioral",
            "established_week": 9,
            "last_seen_week": 9,
            "strength": "emerging",
            "origin": "new job",
        }
    ]
