"""Weekly summary generation."""
import logging
from typing import Dict, Any, Optional
from src.game.state import PlayerState
from src.ai.generator import EventGenerator
from src.ai.system_prompts import get_system_prompt

logger = logging.getLogger(__name__)


class WeeklySummaryGenerator:
    """Generates weekly summaries."""
    
    def __init__(self, ai_generator: Optional[EventGenerator] = None, language: str = "zh"):
        """
        Initialize weekly summary generator.
        
        Args:
            ai_generator: AI event generator
            language: Language code
        """
        self.ai_generator = ai_generator or EventGenerator()
        self.language = language
    
    def generate_summary(
        self,
        week: int,
        previous_state: Dict[str, Any],
        current_state: PlayerState,
        decisions: list,
        language: str = "zh"
    ) -> Dict[str, Any]:
        """
        Generate weekly summary.
        
        Args:
            week: Week number
            previous_state: Previous week's state
            current_state: Current state
            decisions: Decisions made this week
            language: Language code
        
        Returns:
            Summary dictionary
        """
        # Calculate changes
        changes = {
            "energy": current_state.energy - previous_state.get("energy", current_state.energy),
            "mood": current_state.mood - previous_state.get("mood", current_state.mood),
            "knowledge": current_state.knowledge - previous_state.get("knowledge", current_state.knowledge),
            "wealth": current_state.wealth - previous_state.get("wealth", current_state.wealth)
        }
        
        # Generate AI summary
        summary_text = self._generate_ai_summary(week, previous_state, current_state, decisions, changes, language)
        
        return {
            "week": week,
            "age": current_state.age,
            "summary_text": summary_text,
            "changes": changes,
            "decisions_count": len(decisions),
            "final_state": current_state.to_dict()
        }
    
    def _generate_ai_summary(
        self,
        week: int,
        previous_state: Dict[str, Any],
        current_state: PlayerState,
        decisions: list,
        changes: Dict[str, int],
        language: str
    ) -> str:
        """Generate AI summary text."""
        try:
            if language == "zh":
                prompt = f"""请为第{week}周生成一段总结（50-100字）。

本周变化：
- 精力：{changes['energy']:+d}
- 情绪：{changes['mood']:+d}
- 学识：{changes['knowledge']:+d}
- 财富：{changes['wealth']:+,}

本周决策：{len(decisions)}个
当前状态：精力{current_state.energy}/100，情绪{current_state.mood}/100，学识{current_state.knowledge}/100

请生成一段生动的周总结，描述这周的主要变化和感受。"""
            else:
                prompt = f"""Generate a summary for week {week} (50-100 words).

Changes this week:
- Energy: {changes['energy']:+d}
- Mood: {changes['mood']:+d}
- Knowledge: {changes['knowledge']:+d}
- Wealth: {changes['wealth']:+,}

Decisions made: {len(decisions)}
Current state: Energy {current_state.energy}/100, Mood {current_state.mood}/100, Knowledge {current_state.knowledge}/100

Generate a vivid weekly summary describing the main changes and feelings."""
            
            return self.ai_generator.generate_completion(
                prompt=prompt,
                system_prompt=get_system_prompt("narrative_summary", self.language),
                temperature=0.7,
                max_tokens=4096,
            )
        except Exception as e:
            logger.warning(f"Failed to generate AI summary: {e}")
            return self._get_fallback_summary(week, changes, language)
    
    def _get_fallback_summary(self, week: int, changes: Dict[str, int], language: str) -> str:
        """Get fallback summary."""
        if language == "zh":
            return f"第{week}周过去了。精力变化{changes['energy']:+d}，情绪变化{changes['mood']:+d}，学识变化{changes['knowledge']:+d}，财富变化{changes['wealth']:+,}。"
        else:
            return f"Week {week} passed. Energy {changes['energy']:+d}, Mood {changes['mood']:+d}, Knowledge {changes['knowledge']:+d}, Wealth {changes['wealth']:+,}."
