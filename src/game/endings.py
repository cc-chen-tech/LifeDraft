"""Ending evaluation and generation."""

import logging
from typing import Any, Dict, Optional

from src.ai.generator import EventGenerator
from src.ai.system_prompts import get_system_prompt
from src.game.state import PlayerState

logger = logging.getLogger(__name__)


class EndingEvaluator:
    """Evaluates final state and generates ending."""

    ENDING_TYPES = {
        "balanced": {"en": "Balanced Life", "zh": "平衡人生"},
        "wealthy": {"en": "Wealthy Success", "zh": "财富自由"},
        "scholar": {"en": "Intellectual Pursuit", "zh": "学术之路"},
        "social": {"en": "Social Butterfly", "zh": "社交达人"},
        "struggling": {"en": "Struggling Journey", "zh": "艰难前行"},
    }

    def __init__(self, ai_generator: Optional[EventGenerator] = None):
        """
        Initialize ending evaluator.

        Args:
            ai_generator: Optional AI generator for narrative summary
        """
        self.ai_generator = ai_generator

    def evaluate_ending(self, player_state: PlayerState, language: str = "en") -> Dict[str, Any]:
        """
        Evaluate final state and determine ending type.

        Args:
            player_state: Final player state
            language: Language code

        Returns:
            Dictionary with ending information
        """
        player_state.to_dict()

        # Calculate scores
        avg_attribute = (player_state.energy + player_state.mood + player_state.knowledge) / 3
        wealth_score = min(player_state.wealth / 10000, 10)  # Normalize wealth
        relationship_score = (
            sum(player_state.relationships.values()) / max(len(player_state.relationships), 1) / 100
        )

        # Determine ending type
        ending_type = self._determine_ending_type(
            avg_attribute, wealth_score, relationship_score, player_state
        )

        # Generate summary
        summary = self._generate_summary(player_state, ending_type, language)

        # Calculate achievements
        achievements = self._calculate_achievements(player_state, language)

        return {
            "ending_type": ending_type,
            "ending_name": self.ENDING_TYPES[ending_type][language],
            "summary": summary,
            "achievements": achievements,
            "final_stats": {
                "energy": player_state.energy,
                "mood": player_state.mood,
                "knowledge": player_state.knowledge,
                "wealth": player_state.wealth,
                "relationships": player_state.relationships.copy(),
            },
        }

    def _determine_ending_type(
        self,
        avg_attribute: float,
        wealth_score: float,
        relationship_score: float,
        player_state: PlayerState,
    ) -> str:
        """Determine ending type based on scores."""
        # Check for struggling (low overall)
        if avg_attribute < 40 or (player_state.wealth < 5000 and avg_attribute < 50):
            return "struggling"

        # Check for wealthy (high wealth, moderate others)
        if wealth_score > 7 and player_state.wealth > 50000:
            return "wealthy"

        # Check for scholar (high knowledge, moderate others)
        if player_state.knowledge > 80 and avg_attribute > 60:
            return "scholar"

        # Check for social (high relationships, moderate others)
        if relationship_score > 0.7 and len(player_state.relationships) >= 3:
            return "social"

        # Default to balanced
        return "balanced"

    def _generate_summary(self, player_state: PlayerState, ending_type: str, language: str) -> str:
        """Generate ending summary text."""
        if self.ai_generator:
            try:
                # Get character settings
                character_settings = player_state.character_settings
                character_context = ""
                if character_settings:
                    if language == "zh":
                        char_parts = []
                        if "era" in character_settings:
                            char_parts.append(
                                f"时代：{character_settings['era'].get('year', '')}年"
                            )
                        if "age" in character_settings:
                            char_parts.append(
                                f"起始年龄：{character_settings['age'].get('age', '')}岁"
                            )
                        if "gender" in character_settings:
                            char_parts.append(
                                f"性别：{character_settings['gender'].get('gender', '')}"
                            )
                        if "traits" in character_settings:
                            traits = character_settings["traits"]
                            char_parts.append(f"性格：{traits.get('personality', '')}")
                        character_context = "，".join(char_parts)
                    else:
                        char_parts = []
                        if "era" in character_settings:
                            char_parts.append(f"Era: {character_settings['era'].get('year', '')}")
                        if "age" in character_settings:
                            char_parts.append(
                                f"Starting age: {character_settings['age'].get('age', '')}"
                            )
                        if "gender" in character_settings:
                            char_parts.append(
                                f"Gender: {character_settings['gender'].get('gender', '')}"
                            )
                        if "traits" in character_settings:
                            traits = character_settings["traits"]
                            char_parts.append(f"Personality: {traits.get('personality', '')}")
                        character_context = ", ".join(char_parts)

                # Get four-week summaries (pure weekly system, no monthly summaries)
                four_week_summaries = player_state.four_week_summaries
                summary_texts = (
                    [s.get("summary", "") for s in four_week_summaries[-10:]]
                    if four_week_summaries
                    else []
                )

                decision_history = [
                    d.get("choice", "") for d in player_state.decision_history[-10:]
                ]

                if language == "zh":
                    prompt = f"""请为这个角色生成一段完整的人生总结（300-500字）。

角色设定：{character_context if character_context else "标准现代青年"}

人生历程：
- 从{player_state.character_settings.get('age', {}).get('age', 22) if player_state.character_settings else 22}岁开始，到{player_state.age}岁结束
- 经历了{player_state.week}周的人生旅程
- 最终状态：精力{player_state.energy}/100，情绪{player_state.mood}/100，学识{player_state.knowledge}/100，财富¥{player_state.wealth:,}

关键决策（最近10个）：{', '.join(decision_history) if decision_history else '无'}

阶段性总结（最近10条）：
{chr(10).join(summary_texts) if summary_texts else '无详细记录'}

请生成一段完整的人生总结，回顾这个角色的整个人生历程，包括：
1. 人生起点和背景
2. 主要的人生转折点和重要决策
3. 最终的成就和遗憾
4. 对这段人生的整体评价

要生动、具体，体现这个角色的独特性。"""
                else:
                    prompt = f"""Generate a complete life summary for this character (300-500 words).

Character Settings: {character_context if character_context else "Standard modern young adult"}

Life Journey:
- Started at age {player_state.character_settings.get('age', {}).get('age', 22) if player_state.character_settings else 22}, ended at {player_state.age}
- Experienced {player_state.week} weeks of life
- Final state: Energy {player_state.energy}/100, Mood {player_state.mood}/100, Knowledge {player_state.knowledge}/100, Wealth ¥{player_state.wealth:,}

Key Decisions (last 10): {', '.join(decision_history) if decision_history else 'None'}

Periodic Summaries (last 10):
{chr(10).join(summary_texts) if summary_texts else 'No detailed records'}

Generate a complete life summary reviewing the character's entire life journey, including:
1. Life starting point and background
2. Major turning points and important decisions
3. Final achievements and regrets
4. Overall evaluation of this life

Be vivid and specific, reflecting the character's uniqueness."""

                return self.ai_generator.generate_completion(
                    prompt=prompt,
                    system_prompt=get_system_prompt("narrative_summary", language),
                    temperature=0.8,
                    max_tokens=4096,
                )
            except Exception as e:
                logger.warning(f"Failed to generate AI summary: {e}")

        # Fallback to template summary
        return self._generate_template_summary(player_state, ending_type, language)

    def _generate_template_summary(
        self, player_state: PlayerState, ending_type: str, language: str
    ) -> str:
        """Generate template-based summary."""
        if language == "zh":
            summaries = {
                "balanced": f"在{player_state.age}岁时，你过上了平衡的生活。精力、情绪和学识都保持在良好水平，财富也足够支撑你的生活。",
                "wealthy": f"在{player_state.age}岁时，你积累了可观的财富。虽然可能在某些方面有所牺牲，但你在财务上取得了成功。",
                "scholar": f"在{player_state.age}岁时，你在学术和知识领域取得了卓越成就。你的学识达到了{player_state.knowledge}分的高水平。",
                "social": f"在{player_state.age}岁时，你建立了丰富的人际关系网络。你与{len(player_state.relationships)}个重要的人保持着良好的关系。",
                "struggling": f"在{player_state.age}岁时，你的人生充满挑战。虽然困难重重，但你坚持了下来，这段经历塑造了你的性格。",
            }
        else:
            summaries = {
                "balanced": f"At age {player_state.age}, you've achieved a balanced life. Your energy, mood, and knowledge are all at good levels, and your wealth is sufficient to support your lifestyle.",
                "wealthy": f"At age {player_state.age}, you've accumulated substantial wealth. While you may have sacrificed in some areas, you've achieved financial success.",
                "scholar": f"At age {player_state.age}, you've achieved excellence in academics and knowledge. Your knowledge has reached a high level of {player_state.knowledge}.",
                "social": f"At age {player_state.age}, you've built a rich network of relationships. You maintain good relationships with {len(player_state.relationships)} important people.",
                "struggling": f"At age {player_state.age}, your life has been full of challenges. Despite the difficulties, you persevered, and these experiences have shaped your character.",
            }

        return summaries.get(ending_type, summaries["balanced"])

    def _calculate_achievements(self, player_state: PlayerState, language: str) -> Dict[str, Any]:
        """Calculate achievements."""
        achievements = []

        # Wealth milestones
        if player_state.wealth >= 100000:
            achievements.append("百万富翁" if language == "zh" else "Millionaire")
        elif player_state.wealth >= 50000:
            achievements.append("财务自由" if language == "zh" else "Financial Freedom")

        # Knowledge milestones
        if player_state.knowledge >= 90:
            achievements.append("知识渊博" if language == "zh" else "Knowledgeable")

        # Relationship milestones
        if len(player_state.relationships) >= 5:
            achievements.append("社交达人" if language == "zh" else "Social Butterfly")

        # Decision milestones
        if len(player_state.decision_history) >= 50:
            achievements.append("经验丰富" if language == "zh" else "Experienced")

        # Perfect weeks (all attributes > 70)
        perfect_weeks = sum(
            1
            for _ in range(len(player_state.decision_history))
            if player_state.energy > 70 and player_state.mood > 70 and player_state.knowledge > 70
        )
        if perfect_weeks > 0:
            achievements.append(
                f"{perfect_weeks}个完美周" if language == "zh" else f"{perfect_weeks} Perfect Weeks"
            )

        return {"list": achievements, "count": len(achievements)}
