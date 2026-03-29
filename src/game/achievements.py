"""Achievement tracking system."""

from typing import Any, Dict, List

from src.game.state import PlayerState


class AchievementTracker:
    """Tracks player achievements."""

    def __init__(self):
        """Initialize achievement tracker."""
        self.achievements: List[str] = []
        self.milestones: Dict[str, Any] = {}

    def check_achievements(
        self, player_state: PlayerState, language: str = "en"
    ) -> List[str]:
        """
        Check and return newly unlocked achievements.

        Args:
            player_state: Current player state
            language: Language code

        Returns:
            List of newly unlocked achievement names
        """
        new_achievements = []

        # Wealth achievements
        if "wealth_100k" not in self.achievements and player_state.wealth >= 100000:
            new_achievements.append("百万富翁" if language == "zh" else "Millionaire")
            self.achievements.append("wealth_100k")

        if "wealth_50k" not in self.achievements and player_state.wealth >= 50000:
            new_achievements.append(
                "财务自由" if language == "zh" else "Financial Freedom"
            )
            self.achievements.append("wealth_50k")

        # Knowledge achievements
        if "knowledge_90" not in self.achievements and player_state.knowledge >= 90:
            new_achievements.append("知识渊博" if language == "zh" else "Knowledgeable")
            self.achievements.append("knowledge_90")

        if "knowledge_80" not in self.achievements and player_state.knowledge >= 80:
            new_achievements.append("博学多才" if language == "zh" else "Well-Read")
            self.achievements.append("knowledge_80")

        # Relationship achievements
        if (
            "relationships_5" not in self.achievements
            and len(player_state.relationships) >= 5
        ):
            new_achievements.append(
                "社交达人" if language == "zh" else "Social Butterfly"
            )
            self.achievements.append("relationships_5")

        # Decision milestones
        decision_count = len(player_state.decision_history)
        if "decisions_50" not in self.achievements and decision_count >= 50:
            new_achievements.append("经验丰富" if language == "zh" else "Experienced")
            self.achievements.append("decisions_50")

        if "decisions_25" not in self.achievements and decision_count >= 25:
            new_achievements.append("决策者" if language == "zh" else "Decision Maker")
            self.achievements.append("decisions_25")

        # Perfect state achievements
        if all(
            [
                player_state.energy >= 80,
                player_state.mood >= 80,
                player_state.knowledge >= 80,
            ]
        ):
            if "perfect_state" not in self.achievements:
                new_achievements.append(
                    "完美状态" if language == "zh" else "Perfect State"
                )
                self.achievements.append("perfect_state")

        # Week milestones
        if "week_50" not in self.achievements and player_state.week >= 50:
            new_achievements.append("半程英雄" if language == "zh" else "Halfway Hero")
            self.achievements.append("week_50")

        return new_achievements

    def get_all_achievements(self) -> List[str]:
        """Get all unlocked achievements."""
        return self.achievements.copy()

    def reset(self) -> None:
        """Reset achievement tracker."""
        self.achievements = []
        self.milestones = {}
