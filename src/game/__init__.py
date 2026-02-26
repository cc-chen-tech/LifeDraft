"""Core game logic package."""
from src.game.state import PlayerState, CharacterState
from src.game.game_loop import GameLoop
from src.game.decisions import process_decision, calculate_character_effects, apply_character_effects
from src.game.relationship_events import RELATIONSHIP_EVENTS, RelationshipEventDef, EventCategory
from src.game.character_creation import assign_sexual_orientation

__all__ = [
    'PlayerState',
    'CharacterState',
    'GameLoop',
    'process_decision',
    'calculate_character_effects',
    'apply_character_effects',
    'RELATIONSHIP_EVENTS',
    'RelationshipEventDef',
    'EventCategory',
    'assign_sexual_orientation',
]
