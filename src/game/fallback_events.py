"""Fallback event generation utilities.

Provides centralized fallback event generation for when AI generation fails.
Extracted from game_loop.py and round/event_generator.py to avoid duplication.
"""

from typing import Any, Dict, Optional

from src.ai.models import EventOption, GameEvent


def generate_fallback_event(
    language: str = "zh", is_round: bool = False, current_round: int = 0
) -> GameEvent:
    """Generate a simple fallback event when AI generation fails.

    Args:
        language: Language code ('zh' or 'en')
        is_round: If True, use round-specific wording (e.g. day name)
        current_round: Current round number (for round-specific naming)

    Returns:
        GameEvent with fallback description and options
    """
    player_state = None  # Not used in fallback

    if is_round:
        # Get round name based on language and round number
        round_names = (
            ["周一", "周中", "周末"]
            if language == "zh"
            else ["Monday", "Midweek", "Weekend"]
        )
        prefix = (
            round_names[current_round]
            if 0 <= current_round < len(round_names)
            else f"Round {current_round}"
        )
    else:
        prefix = ""

    if language == "zh":
        if is_round:
            description = f"{prefix}，你度过了平静的一天。生活的节奏张弛有度，你有一些时间可以自由支配。"
        else:
            description = (
                "你度过了一个平静的一周。你有一些空闲时间，可以思考接下来该做什么。"
            )

        options = [
            EventOption(
                text="保持现状，继续前进" if not is_round else "继续保持现有节奏",
                effects={
                    "energy": 0 if is_round else 5,
                    "mood": 5,
                    "knowledge": 0,
                    "wealth": 0,
                },
            ),
            EventOption(
                text="思考人生方向" if not is_round else "尝试做点不一样的事",
                effects={"energy": -5, "mood": 0, "knowledge": 5, "wealth": 0},
            ),
        ]
    else:
        if is_round:
            description = f"{prefix}, you had a quiet day. Life flows at a steady pace, and you have some time for yourself."
        else:
            description = "You had a quiet week. You have some free time to think about what to do next."

        options = [
            EventOption(
                text=(
                    "Keep status quo and move forward"
                    if not is_round
                    else "Maintain current rhythm"
                ),
                effects={
                    "energy": 0 if is_round else 5,
                    "mood": 5,
                    "knowledge": 0,
                    "wealth": 0,
                },
            ),
            EventOption(
                text=(
                    "Reflect on life direction"
                    if not is_round
                    else "Try something different"
                ),
                effects={"energy": -5, "mood": 0, "knowledge": 5, "wealth": 0},
            ),
        ]

    return GameEvent(
        event_description=description,
        options=options,
    )


def generate_simple_scheduled_event(
    language: str = "zh", scheduled_events: Optional[list] = None
) -> GameEvent:
    """Generate a simple fallback scheduled event when AI generation fails.

    Args:
        language: Language code ('zh' or 'en')
        scheduled_events: List of scheduled events (for description)

    Returns:
        GameEvent with simple scheduled event
    """
    if scheduled_events is None:
        scheduled_events = []

    # Merge descriptions
    descriptions = [se.get("description", "") for se in scheduled_events]
    combined_desc = "；".join(descriptions)

    if language == "zh":
        event_desc = f"到了兑现承诺的时候了。{combined_desc}。你需要做出选择。"
        options = [
            EventOption(text="认真兑现承诺", effects={"mood": 10, "energy": -10}),
            EventOption(text="敷衍了事", effects={"mood": -5}),
            EventOption(text="找借口推迟", effects={"mood": -15}),
        ]
    else:
        event_desc = f"It's time to fulfill your commitment. {combined_desc}. You need to make a choice."
        options = [
            EventOption(
                text="Fulfill commitment seriously", effects={"mood": 10, "energy": -10}
            ),
            EventOption(text="Do it half-heartedly", effects={"mood": -5}),
            EventOption(text="Make an excuse to delay", effects={"mood": -15}),
        ]

    return GameEvent(
        event_description=event_desc,
        options=options,
    )


def generate_simple_round_event(
    language: str = "zh", current_round: int = 0
) -> GameEvent:
    """Generate a simple round fallback event.

    Args:
        language: Language code ('zh' or 'en')
        current_round: Current round number

    Returns:
        GameEvent with simple round event
    """
    round_names = (
        ["周一", "周中", "周末"]
        if language == "zh"
        else ["Monday", "Midweek", "Weekend"]
    )
    round_name = (
        round_names[current_round]
        if 0 <= current_round < len(round_names)
        else f"Round {current_round}"
    )

    if language == "zh":
        description = "一个平静的日子，没有特别的事情发生。"
        options = [
            EventOption(text="安静地度过", effects={}),
            EventOption(text="主动寻找有趣的事", effects={"mood": 5}),
            EventOption(text="专注于工作/学习", effects={"knowledge": 5}),
        ]
    else:
        description = "A quiet day with nothing special happening."
        options = [
            EventOption(text="Spend quietly", effects={}),
            EventOption(text="Look for something interesting", effects={"mood": 5}),
            EventOption(text="Focus on work/study", effects={"knowledge": 5}),
        ]

    return GameEvent(
        event_description=description,
        options=options,
    )
