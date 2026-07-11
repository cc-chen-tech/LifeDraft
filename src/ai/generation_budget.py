"""Quality-aware execution budgets for round story generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class GenerationBudget:
    level: str
    min_length: int
    max_length: int
    max_tokens: int
    allow_quick_regeneration: bool
    allow_ai_consistency: bool
    expected_min_seconds: int
    expected_seconds: int

    def length_requirement(self, language: str) -> str:
        if language == "zh":
            return f"故事应该{self.min_length}-{self.max_length}字"
        return f"Story should be {self.min_length}-{self.max_length} words"

    def progress_expectation(self, language: str) -> str:
        if language == "zh":
            return f"通常 {self.expected_min_seconds}-{self.expected_seconds} 秒"
        return f"Usually {self.expected_min_seconds}-{self.expected_seconds} seconds"


_BUDGETS: Dict[str, GenerationBudget] = {
    "fast": GenerationBudget(
        level="fast",
        min_length=350,
        max_length=600,
        max_tokens=2048,
        allow_quick_regeneration=False,
        allow_ai_consistency=False,
        expected_min_seconds=20,
        expected_seconds=45,
    ),
    "expert": GenerationBudget(
        level="expert",
        min_length=800,
        max_length=1200,
        max_tokens=4096,
        allow_quick_regeneration=True,
        allow_ai_consistency=True,
        expected_min_seconds=45,
        expected_seconds=90,
    ),
    "master": GenerationBudget(
        level="master",
        min_length=1500,
        max_length=2000,
        max_tokens=8192,
        allow_quick_regeneration=True,
        allow_ai_consistency=True,
        expected_min_seconds=90,
        expected_seconds=180,
    ),
}


def get_generation_budget(level: str) -> GenerationBudget:
    """Return the requested budget, defaulting unknown values to expert."""
    return _BUDGETS.get(str(level).lower(), _BUDGETS["expert"])
