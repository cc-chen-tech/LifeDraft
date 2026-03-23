"""AI event models."""

import json
from typing import Any, Dict, List

from pydantic import BaseModel, Field, ValidationError


class EventOption(BaseModel):
    """Represents a single option in an event."""

    text: str = Field(..., max_length=200)  # Increased for longer option text
    effects: Dict[str, Any] = Field(...)
    likely_choice: bool = Field(
        default=False
    )  # Whether this is the character's likely choice


class GameEvent(BaseModel):
    """Represents a complete game event."""

    event_description: str = Field(
        ..., max_length=10000
    )  # Increased for multi-round long stories (1500-2000 chars each)
    options: List[EventOption] = Field(..., min_length=2, max_length=4)

    @classmethod
    def from_json(cls, json_str: str) -> "GameEvent":
        """Create GameEvent from JSON string."""
        try:
            data = json.loads(json_str)
            return cls(**data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise ValueError(f"Invalid event format: {e}")
