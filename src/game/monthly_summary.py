"""Monthly summary generation."""

import logging
from typing import Any, Dict, List, Optional

from src.ai.generator import EventGenerator
from src.ai.system_prompts import get_system_prompt
from src.game.state import PlayerState

logger = logging.getLogger(__name__)


class MonthlySummaryGenerator:
    """Generates monthly summaries."""

    def __init__(self, ai_generator: Optional[EventGenerator] = None, language: str = "zh"):
        """
        Initialize monthly summary generator.

        Args:
            ai_generator: AI event generator
            language: Language code
        """
        self.ai_generator = ai_generator or EventGenerator()
        self.language = language

    def generate_summary(
        self,
        month: int,
        start_week: int,
        end_week: int,
        previous_state: Dict[str, Any],
        current_state: PlayerState,
        decisions: list,
        language: str = "zh",
    ) -> Dict[str, Any]:
        """
        Generate monthly summary.

        Args:
            month: Month number (1, 2, 3, etc.)
            start_week: Starting week of the month
            end_week: Ending week of the month
            previous_state: Previous month's state
            current_state: Current state
            decisions: Decisions made this month
            language: Language code

        Returns:
            Summary dictionary
        """
        # Calculate changes
        changes = {
            "energy": current_state.energy - previous_state.get("energy", current_state.energy),
            "mood": current_state.mood - previous_state.get("mood", current_state.mood),
            "knowledge": current_state.knowledge
            - previous_state.get("knowledge", current_state.knowledge),
            "wealth": current_state.wealth - previous_state.get("wealth", current_state.wealth),
        }

        # Generate AI summary
        summary_text = self._generate_ai_summary(
            month, start_week, end_week, previous_state, current_state, decisions, changes, language
        )

        return {
            "month": month,
            "start_week": start_week,
            "end_week": end_week,
            "age": current_state.age,
            "summary_text": summary_text,
            "changes": changes,
            "decisions_count": len(decisions),
            "final_state": current_state.to_dict(),
        }

    def _generate_ai_summary(
        self,
        month: int,
        start_week: int,
        end_week: int,
        previous_state: Dict[str, Any],
        current_state: PlayerState,
        decisions: List[Dict[str, Any]],
        changes: Dict[str, int],
        language: str,
    ) -> str:
        """Generate AI summary text."""
        try:
            # Get key decisions
            decision_texts = [d.get("choice", "") for d in decisions]

            if language == "zh":
                prompt = f"""请为第{month}个月生成一段月度总结（80-150字）。

这个月从第{start_week}周到第{end_week}周，年龄从{previous_state.get('age', current_state.age)}岁到{current_state.age}岁。

月度变化：
- 精力：{changes['energy']:+d}
- 情绪：{changes['mood']:+d}
- 学识：{changes['knowledge']:+d}
- 财富：{changes['wealth']:+,}

本月决策：{len(decisions)}个
关键决策：{', '.join(decision_texts[:3]) if decision_texts else '无'}

当前状态：精力{current_state.energy}/100，情绪{current_state.mood}/100，学识{current_state.knowledge}/100，财富¥{current_state.wealth:,}

请生成一段生动的月度总结，描述这个月的主要变化、重要事件和感受。"""
            else:
                prompt = f"""Generate a summary for month {month} (80-150 words).

This month spans from week {start_week} to week {end_week}, age from {previous_state.get('age', current_state.age)} to {current_state.age}.

Monthly changes:
- Energy: {changes['energy']:+d}
- Mood: {changes['mood']:+d}
- Knowledge: {changes['knowledge']:+d}
- Wealth: {changes['wealth']:+,}

Decisions made: {len(decisions)}
Key decisions: {', '.join(decision_texts[:3]) if decision_texts else 'None'}

Current state: Energy {current_state.energy}/100, Mood {current_state.mood}/100, Knowledge {current_state.knowledge}/100, Wealth ¥{current_state.wealth:,}

Generate a vivid monthly summary describing the main changes, important events, and feelings of this month."""

            return self.ai_generator.generate_completion(
                prompt=prompt,
                system_prompt=get_system_prompt("narrative_summary", self.language),
                temperature=0.7,
                max_tokens=4096,
            )
        except Exception as e:
            logger.warning(f"Failed to generate AI summary: {e}")
            return self._get_fallback_summary(month, changes, language)

    def _get_fallback_summary(self, month: int, changes: Dict[str, int], language: str) -> str:
        """Get fallback summary."""
        if language == "zh":
            return f"第{month}个月过去了。精力变化{changes['energy']:+d}，情绪变化{changes['mood']:+d}，学识变化{changes['knowledge']:+d}，财富变化{changes['wealth']:+,}。"
        else:
            return f"Month {month} passed. Energy {changes['energy']:+d}, Mood {changes['mood']:+d}, Knowledge {changes['knowledge']:+d}, Wealth {changes['wealth']:+,}."
