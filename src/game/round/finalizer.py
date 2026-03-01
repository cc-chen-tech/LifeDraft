"""Week finalization service for round system.

Handles weekly summaries, bonus effects, and periodic summaries.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional

from src.game.world_model_updater import WorldModelUpdater

logger = logging.getLogger(__name__)


class RoundFinalizer:
    """Service for week finalization in rounds.
    
    This service handles:
    - Weekly summary generation
    - Bonus effects application
    - Weekly decay
    - Periodic summaries (4-week, yearly)
    - Character profile synthesis
    """
    
    def __init__(
        self,
        player_state_getter: callable,
        ai_generator: Any,
        language_getter: callable,
        story_service: Any,
        character_creator: Any,
    ):
        """
        Args:
            player_state_getter: Function that returns current player state
            ai_generator: EventGenerator instance
            language_getter: Function that returns current language
            story_service: StoryService instance
            character_creator: CharacterCreator instance
        """
        self._get_player_state = player_state_getter
        self.ai_generator = ai_generator
        self._get_language = language_getter
        self.story_service = story_service
        self.character_creator = character_creator
    
    @property
    def player_state(self):
        return self._get_player_state()
    
    @property
    def language(self):
        return self._get_language()
    
    def finalize_week(
        self,
        result: Dict[str, Any],
        status_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        处理周结束的通用逻辑：生成周总结、应用奖励效果、推进周数。
        """
        player_state = self.player_state
        
        if status_callback:
            status_callback("weekly_summary")

        logger.info("Week complete, generating weekly summary...")
        weekly_result = self.generate_weekly_summary()
        result["weekly_summary"] = weekly_result.get("summary", "")
        
        # Apply bonus effects if any
        bonus_effects = weekly_result.get("bonus_effects", {})
        if bonus_effects:
            player_state.update(
                energy=bonus_effects.get("energy", 0),
                mood=bonus_effects.get("mood", 0),
                knowledge=bonus_effects.get("knowledge", 0),
                wealth=bonus_effects.get("wealth", 0)
            )
            result["bonus_effects"] = bonus_effects
            logger.info(f"Applied bonus effects: {bonus_effects}")
        
        # Save weekly summary
        date_info = player_state.get_game_date_info()
        weekly_summary_entry = {
            "week": player_state.week,
            "summary": weekly_result.get("summary", ""),
            "bonus_effects": bonus_effects,
            "date_info": date_info
        }
        player_state.weekly_summaries.append(weekly_summary_entry)
        
        # Apply weekly decay and advance week
        self._apply_weekly_decay()
        player_state.advance_week()
        logger.info(f"Advanced to 第{player_state.week + 1}周")
        
        # Synthesize character profiles + summaries in parallel
        new_week = player_state.week
        parallel_tasks = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Always run character profile synthesis
            parallel_tasks.append(executor.submit(
                WorldModelUpdater.synthesize_character_profiles,
                player_state, self.ai_generator.ai_client, self.language
            ))
            # 4-week summary (every 4 weeks)
            if new_week > 0 and new_week % 4 == 0:
                parallel_tasks.append(executor.submit(
                    self._generate_four_week_summary, new_week
                ))
            # Wait for all parallel tasks
            for future in as_completed(parallel_tasks):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Parallel finalize task failed: {e}")

        # Yearly summary must run after 4-week summary (depends on it)
        if new_week > 0 and new_week % 48 == 0:
            self._generate_yearly_summary(new_week)

    def generate_weekly_summary(self) -> Dict[str, Any]:
        """Generate weekly summary for the multi-round system."""
        player_state = self.player_state
        if not player_state:
            return {"summary": "", "bonus_effects": {}}
        
        # Check and fix missing attributes before generating summary
        self._check_and_fix_missing_attributes()
        
        # Get all rounds for the current week
        week_rounds = player_state.get_current_week_rounds()
        
        if not week_rounds:
            return {
                "summary": "本周平静地度过了。" if self.language == "zh" else "This week passed quietly.",
                "bonus_effects": {}
            }
        
        try:
            return self.ai_generator.generate_weekly_summary(
                rounds=week_rounds,
                character_settings=player_state.character_settings,
                language=self.language,
                game_date_info=player_state.get_game_date_info()
            )
        except Exception as e:
            logger.error(f"Failed to generate weekly summary: {e}")
            return {
                "summary": "本周充实而忙碌。" if self.language == "zh" else "This week was full and busy.",
                "bonus_effects": {}
            }

    def compress_round_story(self, story: str, choice: str) -> Dict[str, Any]:
        """Compress a story into a summary. Delegates to StoryService."""
        player_state = self.player_state
        pending_storylines = player_state.pending_storylines if player_state else []
        established_facts = player_state.established_facts if player_state else []
        character_habits = player_state.character_habits if player_state else []
        return self.story_service.compress_story(story, choice, pending_storylines, established_facts, character_habits)

    def get_round_info(self) -> Dict[str, Any]:
        """Get current round information."""
        player_state = self.player_state
        if not player_state:
            return {}
        
        return {
            "week": player_state.week,
            "current_round": player_state.current_round,
            "rounds_per_week": player_state.rounds_per_week,
            "round_name": player_state.get_round_name(self.language),
            "is_last_round": player_state.current_round == player_state.rounds_per_week - 1,
            "week_rounds_completed": len(player_state.get_current_week_rounds())
        }

    def _apply_weekly_decay(self) -> None:
        """Apply weekly attribute decay. Override in subclass if needed."""
        player_state = self.player_state
        if player_state:
            # Default: small mood decay each week
            player_state.update(mood=-2)

    def _check_and_fix_missing_attributes(self) -> None:
        """检测并修复角色设定中缺失的属性。委托给 CharacterCreator。"""
        player_state = self.player_state
        if player_state:
            self.character_creator.check_and_fix_missing_attributes(player_state)

    def _generate_family_members_details(self, old_format_members: list) -> list:
        """将旧格式的家庭成员列表升级为新格式。委托给 CharacterCreator。"""
        player_state = self.player_state
        if not player_state or not player_state.character_settings:
            return []
        return self.character_creator.generate_family_members_details(
            old_format_members,
            player_state.character_settings,
            player_state.player_name or "主角"
        )

    def _generate_four_week_summary(self, week: int) -> None:
        """Generate 4-week summary. Override in subclass if needed."""
        player_state = self.player_state
        if not player_state:
            return
        
        try:
            # Get last 4 weeks of summaries
            weekly_summaries = player_state.weekly_summaries[-4:]
            if len(weekly_summaries) < 4:
                return
            
            summary_text = "\n\n".join([
                f"Week {s['week']}: {s.get('summary', '')}"
                for s in weekly_summaries
            ])
            
            four_week_entry = {
                "week": week,
                "summaries": weekly_summaries,
                "combined_summary": summary_text,
            }
            
            if not hasattr(player_state, 'four_week_summaries'):
                player_state.four_week_summaries = []
            player_state.four_week_summaries.append(four_week_entry)
            logger.info(f"Generated 4-week summary for 第{week + 1}周")
            
        except Exception as e:
            logger.error(f"Failed to generate 4-week summary: {e}")

    def _generate_yearly_summary(self, week: int) -> None:
        """Generate yearly summary. Override in subclass if needed."""
        player_state = self.player_state
        if not player_state:
            return
        
        try:
            # Get all 4-week summaries for the year
            four_week_summaries = player_state.four_week_summaries[-12:]  # 48 weeks = 12 periods
            if len(four_week_summaries) < 12:
                return
            
            yearly_entry = {
                "week": week,
                "year": week // 48,
                "summaries": four_week_summaries,
            }
            
            if not hasattr(player_state, 'yearly_summaries'):
                player_state.yearly_summaries = []
            player_state.yearly_summaries.append(yearly_entry)
            logger.info(f"Generated yearly summary for 第{week + 1}周")
            
        except Exception as e:
            logger.error(f"Failed to generate yearly summary: {e}")
