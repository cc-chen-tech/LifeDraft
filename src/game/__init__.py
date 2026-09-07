"""Core game logic package."""

from importlib import import_module

# Lightweight submodules (for example effects) are imported by AI models.
# Loading the entire game runtime here would import the AI generator again.
_EXPORT_MODULES = {
    "assign_sexual_orientation": "character_creation",
    "apply_character_effects": "decisions",
    "calculate_character_effects": "decisions",
    "process_decision": "decisions",
    "GameLoop": "game_loop",
    "RELATIONSHIP_EVENTS": "relationship_events",
    "EventCategory": "relationship_events",
    "RelationshipEventDef": "relationship_events",
    "CharacterState": "state",
    "PlayerState": "state",
}


def __getattr__(name):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value
    return value

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
