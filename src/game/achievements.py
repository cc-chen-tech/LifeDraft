"""Deep achievement tracking system.

Six dimensions, 25+ achievements, 4 rarity tiers.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from src.game.state import PlayerState


@dataclass
class Achievement:
    """Structured achievement data."""

    id: str
    name: str
    description: str
    rarity: str  # common, rare, epic, legendary
    dimension: str  # trajectory, decision_style, relationships, collection, narrative, hidden
    unlocked_at_week: int = 0
    icon: str = ""


class AchievementEngine:
    """Evaluates player state and history to unlock achievements."""

    RARITY_ORDER = ["common", "rare", "epic", "legendary"]

    # ===== Achievement Definitions =====
    ALL_ACHIEVEMENTS: List[Dict[str, Any]] = [
        # --- Trajectory ---
        {
            "id": "balanced_life",
            "name": "平衡人生",
            "name_en": "Balanced Life",
            "description": "所有资源保持在良好水平",
            "rarity": "common",
            "dimension": "trajectory",
        },
        {
            "id": "rollercoaster",
            "name": "过山车",
            "name_en": "Rollercoaster",
            "description": "情绪波动超过30点",
            "rarity": "rare",
            "dimension": "trajectory",
        },
        {
            "id": "phoenix",
            "name": "凤凰涅槃",
            "name_en": "Phoenix",
            "description": "从低谷中恢复",
            "rarity": "epic",
            "dimension": "trajectory",
        },
        {
            "id": "perfect_equilibrium",
            "name": "完美平衡",
            "name_en": "Perfect Equilibrium",
            "description": "所有资源差距不超过5点",
            "rarity": "legendary",
            "dimension": "trajectory",
        },
        # --- Decision Style ---
        {
            "id": "decisive",
            "name": "果断决策者",
            "name_en": "Decisive",
            "description": "做出30次以上选择",
            "rarity": "common",
            "dimension": "decision_style",
        },
        {
            "id": "risk_taker",
            "name": "冒险家",
            "name_en": "Risk Taker",
            "description": "超过50%选择高风险选项",
            "rarity": "rare",
            "dimension": "decision_style",
        },
        {
            "id": "cautious_planner",
            "name": "谨慎规划者",
            "name_en": "Cautious Planner",
            "description": "超过70%选择低风险选项",
            "rarity": "rare",
            "dimension": "decision_style",
        },
        {
            "id": "contrarian",
            "name": "叛逆者",
            "name_en": "Contrarian",
            "description": "从不选择第一个选项",
            "rarity": "epic",
            "dimension": "decision_style",
        },
        {
            "id": "enlightened",
            "name": "觉悟者",
            "name_en": "Enlightened",
            "description": "每周恰好做一次选择",
            "rarity": "legendary",
            "dimension": "decision_style",
        },
        # --- Relationships ---
        {
            "id": "social_butterfly",
            "name": "社交达人",
            "name_en": "Social Butterfly",
            "description": "拥有5段以上人际关系",
            "rarity": "common",
            "dimension": "relationships",
        },
        {
            "id": "deep_bond",
            "name": "深情厚谊",
            "name_en": "Deep Bond",
            "description": "一段关系达到90亲密度",
            "rarity": "rare",
            "dimension": "relationships",
        },
        {
            "id": "heartbreaker",
            "name": "心碎者",
            "name_en": "Heartbreaker",
            "description": "3段关系降至0亲密度",
            "rarity": "rare",
            "dimension": "relationships",
        },
        {
            "id": "lonely_hero",
            "name": "孤独英雄",
            "name_en": "Lonely Hero",
            "description": "游戏结束时没有任何关系",
            "rarity": "epic",
            "dimension": "relationships",
        },
        # --- Collection ---
        {
            "id": "collector",
            "name": "收藏家",
            "name_en": "Collector",
            "description": "收集5件以上物品",
            "rarity": "common",
            "dimension": "collection",
        },
        {
            "id": "world_traveler",
            "name": "世界旅人",
            "name_en": "World Traveler",
            "description": "发现5个以上地点",
            "rarity": "rare",
            "dimension": "collection",
        },
        {
            "id": "character_driven",
            "name": "人物驱动",
            "name_en": "Character Driven",
            "description": "与5个以上NPC建立联系",
            "rarity": "rare",
            "dimension": "collection",
        },
        {
            "id": "completionist",
            "name": "完美主义者",
            "name_en": "Completionist",
            "description": "大量收集物品、地点和NPC",
            "rarity": "epic",
            "dimension": "collection",
        },
        # --- Narrative ---
        {
            "id": "story_rich",
            "name": "故事丰富",
            "name_en": "Story Rich",
            "description": "经历20轮以上故事",
            "rarity": "common",
            "dimension": "narrative",
        },
        {
            "id": "tragic_hero",
            "name": "悲剧英雄",
            "name_en": "Tragic Hero",
            "description": "故事呈现下行轨迹",
            "rarity": "rare",
            "dimension": "narrative",
        },
        {
            "id": "legendary_tale",
            "name": "传奇故事",
            "name_en": "Legendary Tale",
            "description": " exceptional 的人生叙事",
            "rarity": "legendary",
            "dimension": "narrative",
        },
        # --- Hidden ---
        {
            "id": "mystery",
            "name": "谜团",
            "name_en": "Mystery",
            "description": "解锁条件未知",
            "rarity": "epic",
            "dimension": "hidden",
        },
        {
            "id": "true_neutral",
            "name": "绝对中立",
            "name_en": "True Neutral",
            "description": "所有资源恰好为50",
            "rarity": "legendary",
            "dimension": "hidden",
        },
    ]

    def __init__(self, language: str = "zh"):
        self.language = language
        self._unlocked: set = set()

    def evaluate(self, player_state: PlayerState) -> List[Achievement]:
        """Evaluate all achievements against player state."""
        unlocked = []
        for ach_def in self.ALL_ACHIEVEMENTS:
            if self._check_condition(ach_def["id"], player_state):
                name = ach_def["name"] if self.language == "zh" else ach_def["name_en"]
                unlocked.append(
                    Achievement(
                        id=ach_def["id"],
                        name=name,
                        description=ach_def["description"],
                        rarity=ach_def["rarity"],
                        dimension=ach_def["dimension"],
                        unlocked_at_week=player_state.week,
                    )
                )
        return unlocked

    def _check_condition(self, ach_id: str, player: PlayerState) -> bool:
        """Check if a single achievement condition is met."""
        # Trajectory
        if ach_id == "balanced_life":
            return all(v >= 40 for v in [player.energy, player.mood, player.knowledge])
        if ach_id == "rollercoaster":
            return self._mood_variance(player) > 30
        if ach_id == "phoenix":
            return self._phoenix_check(player)
        if ach_id == "perfect_equilibrium":
            resources = [
                player.energy,
                player.mood,
                player.knowledge,
            ]
            return max(resources) - min(resources) <= 5

        # Decision Style
        if ach_id == "decisive":
            return len(player.decision_history) >= 30
        if ach_id == "risk_taker":
            return self._risk_ratio(player) > 0.5
        if ach_id == "cautious_planner":
            return self._risk_ratio(player) < 0.3 and len(player.decision_history) > 0
        if ach_id == "contrarian":
            return self._contrarian_check(player)
        if ach_id == "enlightened":
            return len(player.decision_history) >= player.week > 0

        # Relationships
        if ach_id == "social_butterfly":
            return len(player.relationships) >= 5
        if ach_id == "deep_bond":
            return any(v >= 90 for v in player.relationships.values())
        if ach_id == "heartbreaker":
            return self._heartbreaker_check(player)
        if ach_id == "lonely_hero":
            return len(player.relationships) == 0 and player.week >= 10

        # Collection
        if ach_id == "collector":
            return len(player.items) >= 5
        if ach_id == "world_traveler":
            return len(player.landmarks) >= 5
        if ach_id == "character_driven":
            return len(player.characters) >= 5
        if ach_id == "completionist":
            return (
                len(player.items) >= 10
                and len(player.landmarks) >= 10
                and len(player.characters) >= 5
            )

        # Narrative
        if ach_id == "story_rich":
            return len(player.round_history) >= 20
        if ach_id == "tragic_hero":
            return self._tragic_hero_check(player)
        if ach_id == "legendary_tale":
            return len(player.round_history) >= 50

        # Hidden
        if ach_id == "true_neutral":
            return player.energy == player.mood == player.knowledge == 50

        return False

    # ----- Helper Methods -----

    def _mood_variance(self, player: PlayerState) -> float:
        """Calculate mood variance from round history."""
        if not player.round_history:
            return 0.0
        moods = []
        for r in player.round_history:
            effects = r.get("effects", {})
            if "mood" in effects:
                moods.append(effects["mood"])
        if len(moods) < 2:
            return 0.0
        mean = sum(moods) / len(moods)
        variance = sum((m - mean) ** 2 for m in moods) / len(moods)
        return float(variance**0.5)

    def _phoenix_check(self, player: PlayerState) -> bool:
        """Check if player recovered from low energy."""
        if player.energy < 80:
            return False
        # 检查历史中是否有低谷
        for r in player.round_history[: len(player.round_history) // 2]:
            effects = r.get("effects", {})
            if effects.get("energy", 100) < 30:
                return True
        return False

    def _risk_ratio(self, player: PlayerState) -> float:
        """Estimate risk-taking ratio from decisions."""
        if not player.decision_history:
            return 0.0
        # 简化：假设包含"冒险"/"赌"/"risk"/"bet" 的为高风险
        risky_keywords = ["冒险", "赌", "risk", "bet", "大胆", "孤注"]
        risky_count = sum(
            1
            for d in player.decision_history
            if any(kw in str(d.get("choice", "")).lower() for kw in risky_keywords)
        )
        return risky_count / len(player.decision_history)

    def _contrarian_check(self, player: PlayerState) -> bool:
        """Check if player never chose the first option."""
        if not player.decision_history:
            return False
        for d in player.decision_history:
            choice = str(d.get("choice", ""))
            # 简化：假设第一个选项通常包含 A/1/第一个
            if choice in ["A", "1", "第一个"] or choice.startswith("A."):
                return False
        return len(player.decision_history) >= 5

    def _heartbreaker_check(self, player: PlayerState) -> bool:
        """Check if 3+ relationships dropped to 0."""
        # 简化：当前为 0 的 relationships
        zero_count = sum(1 for v in player.relationships.values() if v == 0)
        return zero_count >= 3

    def _tragic_hero_check(self, player: PlayerState) -> bool:
        """Detect downward trajectory."""
        if len(player.round_history) < 10:
            return False
        mid = len(player.round_history) // 2
        resource_keys = ("energy", "mood", "knowledge")
        early_total = sum(
            sum(r.get("effects", {}).get(key, 0) for key in resource_keys)
            for r in player.round_history[:mid]
        )
        late_total = sum(
            sum(r.get("effects", {}).get(key, 0) for key in resource_keys)
            for r in player.round_history[mid:]
        )
        return late_total < early_total and player.mood < 40
