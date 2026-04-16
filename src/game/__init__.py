"""Core game logic package."""

from src.game.character_creation import assign_sexual_orientation
from src.game.decisions import (apply_character_effects,
                                calculate_character_effects, process_decision)
from src.game.game_loop import GameLoop
from src.game.relationship_events import (RELATIONSHIP_EVENTS, EventCategory,
                                          RelationshipEventDef)
from src.game.state import CharacterState, PlayerState

__all__ = [
    "PlayerState",
    "CharacterState",
    "GameLoop",
    "process_decision",
    "calculate_character_effects",
    "apply_character_effects",
    "RELATIONSHIP_EVENTS",
    "RelationshipEventDef",
    "EventCategory",
    "assign_sexual_orientation",
]
