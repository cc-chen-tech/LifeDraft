"""Life review card generator.

Backend-generated comprehensive life review data.
"""

from typing import Any, Dict, List

from src.game.achievements import Achievement
from src.game.state import PlayerState


class LifeReviewGenerator:
    """Generates life review data from player state and achievements."""

    def __init__(self, language: str = "zh"):
        self.language = language

    def generate(self, player: PlayerState, achievements: List[Achievement]) -> Dict[str, Any]:
        """Generate complete life review data."""
        return {
            "personality_labels": self._generate_personality_labels(player, achievements),
            "key_turning_points": self._extract_turning_points(player),
            "resource_curves": self._build_resource_curves(player),
            "achievement_badge_wall": self._build_badge_wall(achievements),
            "relationship_network": self._build_relationship_network(player),
            "life_motto": self._generate_motto(player, achievements),
            "play_duration_minutes": self._estimate_duration(player),
            "total_decisions": len(player.decision_history),
            "favorite_choice_type": self._analyze_choice_type(player),
        }

    def _generate_personality_labels(
        self, player: PlayerState, achievements: List[Achievement]
    ) -> List[str]:
        """Generate 2-4 personality labels based on stats and achievements."""
        labels = []
        zh = self.language == "zh"

        # Resource-based labels
        if player.wealth > 50000:
            labels.append("财富追求者" if zh else "Wealth Seeker")
        if player.knowledge > 80:
            labels.append("知识探索者" if zh else "Knowledge Seeker")
        if len(player.relationships) >= 5:
            labels.append("社交达人" if zh else "Social Butterfly")
        if player.energy > 80:
            labels.append("精力充沛" if zh else "Energetic")
        if player.mood < 40:
            labels.append("忧郁深思者" if zh else "Brooding Thinker")

        # Achievement-based labels
        dim_counts: Dict[str, int] = {}
        for a in achievements:
            dim_counts[a.dimension] = dim_counts.get(a.dimension, 0) + 1
        top_dim = max(dim_counts, key=dim_counts.get) if dim_counts else ""
        if top_dim == "trajectory":
            labels.append("稳健派" if zh else "Steady")
        elif top_dim == "decision_style":
            labels.append("果断派" if zh else "Decisive")
        elif top_dim == "relationships":
            labels.append("情感丰富" if zh else "Emotionally Rich")
        elif top_dim == "collection":
            labels.append("探索者" if zh else "Explorer")

        if len(labels) < 2:
            labels.append("平凡而真实" if zh else "Genuine & Ordinary")

        return labels[:4]

    def _extract_turning_points(self, player: PlayerState) -> List[Dict[str, Any]]:
        """Extract key turning points from round history."""
        turning_points = []
        if not player.round_history:
            return turning_points

        for i, r in enumerate(player.round_history):
            effects = r.get("effects", {})
            impact = 0
            for key in ["energy", "mood", "knowledge", "wealth"]:
                delta = abs(effects.get(key, 0))
                if key == "wealth":
                    delta = delta / 100  # Scale wealth
                impact += delta

            if impact > 15:
                turning_points.append(
                    {
                        "week": r.get("week", i),
                        "description": r.get("summary", r.get("event_description", "重要时刻"))[:50],
                        "impact_score": min(impact / 50, 1.0),
                    }
                )

        # 最多返回 5 个
        turning_points.sort(key=lambda x: x["impact_score"], reverse=True)
        return turning_points[:5]

    def _build_resource_curves(self, player: PlayerState) -> Dict[str, List[int]]:
        """Build resource curves over time."""
        from config.settings import settings

        weeks = player.week + 1
        energy_curve = [settings.INITIAL_ENERGY]
        mood_curve = [settings.INITIAL_MOOD]
        knowledge_curve = [settings.INITIAL_KNOWLEDGE]
        wealth_curve = [settings.INITIAL_WEALTH]

        for r in player.round_history:
            effects = r.get("effects", {})
            energy_curve.append(max(0, min(100, energy_curve[-1] + effects.get("energy", 0))))
            mood_curve.append(max(0, min(100, mood_curve[-1] + effects.get("mood", 0))))
            knowledge_curve.append(
                max(0, min(100, knowledge_curve[-1] + effects.get("knowledge", 0)))
            )
            wealth_curve.append(max(0, wealth_curve[-1] + effects.get("wealth", 0)))

        # Pad to match week count
        while len(energy_curve) < weeks:
            energy_curve.append(energy_curve[-1])
            mood_curve.append(mood_curve[-1])
            knowledge_curve.append(knowledge_curve[-1])
            wealth_curve.append(wealth_curve[-1])

        return {
            "energy": energy_curve,
            "mood": mood_curve,
            "knowledge": knowledge_curve,
            "wealth": wealth_curve,
        }

    def _build_badge_wall(self, achievements: List[Achievement]) -> List[Dict[str, Any]]:
        """Build achievement badge wall data."""
        rarity_order = {"legendary": 0, "epic": 1, "rare": 2, "common": 3}
        sorted_achievements = sorted(achievements, key=lambda a: rarity_order.get(a.rarity, 99))
        return [
            {
                "id": a.id,
                "name": a.name,
                "rarity": a.rarity,
                "unlocked_at_week": a.unlocked_at_week,
            }
            for a in sorted_achievements
        ]

    def _build_relationship_network(self, player: PlayerState) -> Dict[str, Any]:
        """Build relationship network data."""
        nodes = [
            {"name": name, "affinity": affinity}
            for name, affinity in player.relationships.items()
        ]
        # Simple edges: connect everyone to everyone with moderate strength
        edges = []
        for i, n1 in enumerate(nodes):
            for n2 in nodes[i + 1 :]:
                edges.append(
                    {
                        "source": n1["name"],
                        "target": n2["name"],
                        "strength": round((n1["affinity"] + n2["affinity"]) / 200, 2),
                    }
                )
        return {"nodes": nodes, "edges": edges}

    def _generate_motto(self, player: PlayerState, achievements: List[Achievement]) -> str:
        """Generate a life motto based on player's journey."""
        zh = self.language == "zh"
        mottos_zh = [
            "在动荡中寻找平衡，在孤独中发现自我。",
            "每一个选择都塑造了今天的你。",
            "财富不是终点，经历才是财富。",
            "知识照亮前路，关系温暖人心。",
            "勇敢前行，无畏未来。",
        ]
        mottos_en = [
            "In chaos, find balance. In solitude, find yourself.",
            "Every choice has shaped who you are today.",
            "Wealth is not the destination; experience is.",
            "Knowledge lights the way; relationships warm the heart.",
            "Move forward bravely, fear not the future.",
        ]

        # 根据最高稀有度成就选择
        rarity_scores = {"common": 1, "rare": 2, "epic": 3, "legendary": 4}
        max_rarity = max((rarity_scores.get(a.rarity, 0) for a in achievements), default=0)

        idx = min(max_rarity, len(mottos_zh) - 1)
        return mottos_zh[idx] if zh else mottos_en[idx]

    def _estimate_duration(self, player: PlayerState) -> int:
        """Estimate play duration in minutes."""
        return max(5, len(player.decision_history) * 2)

    def _analyze_choice_type(self, player: PlayerState) -> str:
        """Analyze player's favorite choice type."""
        zh = self.language == "zh"
        if not player.decision_history:
            return "未知" if zh else "Unknown"

        # 简化分析
        risky = 0
        safe = 0
        risky_keywords = ["冒险", "赌", "risk", "bet", "大胆"]
        safe_keywords = ["稳妥", "保守", "安全", "safe", "steady"]

        for d in player.decision_history:
            choice = str(d.get("choice", "")).lower()
            if any(kw in choice for kw in risky_keywords):
                risky += 1
            elif any(kw in choice for kw in safe_keywords):
                safe += 1

        if risky > safe:
            return "冒险" if zh else "Adventure"
        elif safe > risky:
            return "稳健" if zh else "Steady"
        return "平衡" if zh else "Balanced"
