"""Yearly summary generation."""
import logging
from typing import Dict, Any, Optional, List
from src.game.state import PlayerState
from src.ai.generator import EventGenerator
from src.ai.system_prompts import get_system_prompt

logger = logging.getLogger(__name__)


class YearlySummaryGenerator:
    """Generates yearly summaries."""
    
    def __init__(self, ai_generator: Optional[EventGenerator] = None, language: str = "zh"):
        """
        Initialize yearly summary generator.
        
        Args:
            ai_generator: AI event generator
            language: Language code
        """
        self.ai_generator = ai_generator or EventGenerator()
        self.language = language
    
    def generate_summary(
        self,
        year: int,
        start_week: int,
        end_week: int,
        start_state: Dict[str, Any],
        end_state: PlayerState,
        monthly_summaries: List[Dict[str, Any]],
        decisions: List[Dict[str, Any]],
        language: str = "zh"
    ) -> Dict[str, Any]:
        """
        Generate yearly summary.
        
        Args:
            year: Year number (1, 2, 3, etc.)
            start_week: Starting week of the year
            end_week: Ending week of the year
            start_state: State at the beginning of the year
            end_state: State at the end of the year
            monthly_summaries: Monthly summaries from this year
            decisions: All decisions made this year
            language: Language code
        
        Returns:
            Summary dictionary
        """
        # Calculate changes over the year
        changes = {
            "energy": end_state.energy - start_state.get("energy", end_state.energy),
            "mood": end_state.mood - start_state.get("mood", end_state.mood),
            "knowledge": end_state.knowledge - start_state.get("knowledge", end_state.knowledge),
            "wealth": end_state.wealth - start_state.get("wealth", end_state.wealth),
            "age": end_state.age - start_state.get("age", end_state.age)
        }
        
        # Generate AI summary
        summary_text = self._generate_ai_summary(
            year,
            start_week,
            end_week,
            start_state,
            end_state,
            changes,
            monthly_summaries,
            decisions,
            language
        )
        
        return {
            "year": year,
            "start_week": start_week,
            "end_week": end_week,
            "age": end_state.age,
            "summary_text": summary_text,
            "changes": changes,
            "decisions_count": len(decisions),
            "final_state": end_state.to_dict()
        }
    
    def _generate_ai_summary(
        self,
        year: int,
        start_week: int,
        end_week: int,
        start_state: Dict[str, Any],
        end_state: PlayerState,
        changes: Dict[str, int],
        weekly_summaries: List[Dict[str, Any]],
        decisions: List[Dict[str, Any]],
        language: str
    ) -> str:
        """Generate AI summary text."""
        try:
            # Get key decisions and events
            key_decisions = decisions[-10:] if len(decisions) > 10 else decisions
            decision_texts = [d.get("choice", "") for d in key_decisions]
            
            # Get monthly summary highlights
            summary_highlights = []
            if monthly_summaries:
                # Take a few representative summaries
                if len(monthly_summaries) > 5:
                    summary_highlights = [s.get("summary_text", "") for s in monthly_summaries[::len(monthly_summaries)//5]]
                else:
                    summary_highlights = [s.get("summary_text", "") for s in monthly_summaries]
            
            if language == "zh":
                prompt = f"""请为第{year}年生成一段年度总结（150-250字）。

这一年从第{start_week}周到第{end_week}周，年龄从{start_state.get('age', end_state.age)}岁到{end_state.age}岁。

年度变化：
- 精力：{changes['energy']:+d}
- 情绪：{changes['mood']:+d}
- 学识：{changes['knowledge']:+d}
- 财富：{changes['wealth']:+,}
- 年龄增长：{changes['age']}岁

年度决策：{len(decisions)}个
关键决策：{', '.join(decision_texts[:5]) if decision_texts else '无'}

当前状态：精力{end_state.energy}/100，情绪{end_state.mood}/100，学识{end_state.knowledge}/100，财富¥{end_state.wealth:,}

月度总结片段：
{chr(10).join(summary_highlights[:3]) if summary_highlights else '无详细记录'}

请生成一段生动的年度总结，描述这一年的主要变化、重要事件、成长和挑战。要体现这一年的整体轨迹和转折点。"""
            else:
                prompt = f"""Generate a summary for year {year} (150-250 words).

This year spans from week {start_week} to week {end_week}, age from {start_state.get('age', end_state.age)} to {end_state.age}.

Annual changes:
- Energy: {changes['energy']:+d}
- Mood: {changes['mood']:+d}
- Knowledge: {changes['knowledge']:+d}
- Wealth: {changes['wealth']:+,}
- Age increase: {changes['age']} years

Annual decisions: {len(decisions)}
Key decisions: {', '.join(decision_texts[:5]) if decision_texts else 'None'}

Current state: Energy {end_state.energy}/100, Mood {end_state.mood}/100, Knowledge {end_state.knowledge}/100, Wealth ¥{end_state.wealth:,}

Monthly summary highlights:
{chr(10).join(summary_highlights[:3]) if summary_highlights else 'No detailed records'}

Generate a vivid annual summary describing the main changes, important events, growth, and challenges of this year. Reflect the overall trajectory and turning points."""
            
            return self.ai_generator.generate_completion(
                prompt=prompt,
                system_prompt=get_system_prompt("narrative_summary", self.language),
                temperature=0.8,
                max_tokens=4096,
            )
        except Exception as e:
            logger.warning(f"Failed to generate AI summary: {e}")
            return self._get_fallback_summary(year, changes, language)
    
    def _get_fallback_summary(self, year: int, changes: Dict[str, int], language: str) -> str:
        """Get fallback summary."""
        if language == "zh":
            return f"第{year}年过去了。精力变化{changes['energy']:+d}，情绪变化{changes['mood']:+d}，学识变化{changes['knowledge']:+d}，财富变化{changes['wealth']:+,}，年龄增长了{changes['age']}岁。"
        else:
            return f"Year {year} passed. Energy {changes['energy']:+d}, Mood {changes['mood']:+d}, Knowledge {changes['knowledge']:+d}, Wealth {changes['wealth']:+,}, Age increased by {changes['age']} years."
