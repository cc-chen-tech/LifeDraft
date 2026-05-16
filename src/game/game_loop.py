"""Core game loop implementation."""

import logging
import random
from typing import Any, Callable, Dict, Optional

from config.feature_flags import get_feature
from config.settings import settings
from src.ai.generator import EventGenerator
from src.ai.models import EventOption, GameEvent
from src.game.character_creation import CharacterCreator
from src.game.decisions import process_decision
from src.game.historical_summary_selector import HistoricalSummarySelector
from src.game.narrative_manager import NarrativeManager
from src.game.parallel_postprocessor import ParallelPostProcessor
from src.game.round.system_mixin import RoundSystemMixin
from src.game.state import PlayerState
from src.game.story_service import StoryService
from src.game.world_model_updater import WorldModelUpdater
from src.game.yearly_summary import YearlySummaryGenerator
from src.mcp.relationship_service import RelationshipMCPService

logger = logging.getLogger(__name__)


class GameLoop(RoundSystemMixin):
    """Manages the main game loop.

    Inherits Multi-Round System functionality from RoundSystemMixin.
    """

    def __init__(
        self,
        language: str = "en",
        ai_generator: Optional[EventGenerator] = None,
        event_callback: Optional[Callable] = None,
        result_callback: Optional[Callable] = None,
        quality_level=None,
    ):
        """
        Initialize the game loop.

        Args:
            language: Language code ('en' or 'zh')
            ai_generator: Optional EventGenerator instance
            event_callback: Optional callback for when events are generated
            result_callback: Optional callback for when decisions are processed
            quality_level: Story generation quality level (fast/expert/master)
        """
        self.language = language
        self.ai_generator = ai_generator or EventGenerator(quality_level=quality_level)
        self.quality_level = quality_level
        self.event_callback = event_callback
        self.result_callback = result_callback
        self.player_state: Optional[PlayerState] = None  # type: ignore[assignment]
        self.current_event: Optional[GameEvent] = None
        self._generating: bool = False  # Flag to prevent concurrent generation
        self._generating_start_time: Optional[float] = None  # Track when generation started
        self._GENERATION_TIMEOUT = settings.GENERATION_TIMEOUT  # Max seconds before auto-reset
        self.milestone_weeks = settings.MILESTONE_WEEKS  # Milestone events
        self.yearly_summary_gen = YearlySummaryGenerator(self.ai_generator, language)
        self.relationship_service = RelationshipMCPService()
        self.story_service = StoryService(self.ai_generator, language)
        self.character_creator = CharacterCreator(ai_generator=self.ai_generator, language=language)
        # Extracted sub-services (Phase 3 God Class decomposition)
        self.narrative_mgr = NarrativeManager()
        self.world_updater = WorldModelUpdater()
        self.summary_selector = HistoricalSummarySelector()
        self.last_year_start_week = 0  # Track year boundaries
        self.last_year_start_state: Optional[dict[str, Any]] = None  # Track state at year start
        self.last_event_week = -1  # Track when last event was generated
        # Parallel post-processor (lazy init, managed by feature flag)
        self._parallel_postprocessor: Optional[ParallelPostProcessor] = None

    def start_new_game(self, initial_state: Optional[Dict[str, Any]] = None) -> PlayerState:
        """
        Start a new game.

        Args:
            initial_state: Optional initial state dictionary

        Returns:
            Initialized PlayerState
        """
        if initial_state:
            self.player_state = PlayerState.from_dict(initial_state)
        else:
            self.player_state = PlayerState()
            # Relationships will be set from character settings, no default relationships

        # 从character_settings初始化角色系统
        if self.player_state.character_settings:
            self.player_state.initialize_characters_from_settings()
            logger.debug(
                f"Initialized {len(self.player_state.characters)} characters from settings"
            )

        # Initialize weekly event tracking
        # Set to -1 to ensure first event (week 0) can be generated
        self.last_event_week = -1
        # Clear current_event when starting new game
        self.current_event = None
        self.player_state.current_event_data = None

        logger.info(
            f"Started new game at age {self.player_state.age}, 第{self.player_state.week + 1}周"
        )
        return self.player_state

    def load_game(self, state_dict: Dict[str, Any]) -> PlayerState:
        """
        Load a game from saved state.

        Args:
            state_dict: Saved state dictionary

        Returns:
            Loaded PlayerState
        """
        self.player_state = PlayerState.from_dict(state_dict)

        # 如果characters为空但有character_settings，尝试初始化
        if not self.player_state.characters and self.player_state.character_settings:
            self.player_state.initialize_characters_from_settings()
            logger.debug(
                f"Initialized {len(self.player_state.characters)} characters from settings on load"
            )

        # Restore current_event if it was saved
        logger.info(
            f"[LoadGame] current_event_data exists: {self.player_state.current_event_data is not None}"
        )
        if self.player_state.current_event_data:
            # 检查 round_history 是否已有当前轮次条目
            current_week = self.player_state.week
            current_round = self.player_state.current_round
            round_history = self.player_state.round_history or []

            already_processed = any(
                entry.get("week") == current_week and entry.get("round") == current_round
                for entry in round_history
            )

            if already_processed:
                logger.info(
                    f"[LoadGame] current_event_data is stale "
                    f"(round {current_week}-{current_round} already in history), clearing"
                )
                self.player_state.current_event_data = None
                self.current_event = None
            else:
                try:
                    from src.ai.models import GameEvent

                    self.current_event = GameEvent(**self.player_state.current_event_data)
                    logger.info(
                        f"[LoadGame] Restored current event from saved state: "
                        f"{self.current_event.event_description[:50]}..."
                    )
                except Exception as e:
                    logger.warning(f"[LoadGame] Failed to restore current event: {e}")
                    self.current_event = None
        else:
            logger.info("[LoadGame] No current_event_data, setting current_event to None")
            self.current_event = None

        # Initialize year tracking based on loaded state
        if self.player_state.yearly_summaries:
            last_year = self.player_state.yearly_summaries[-1]
            self.last_year_start_week = last_year.get("end_week", 0) + 1
        else:
            self.last_year_start_week = 0

        self.last_year_start_state = self.player_state.to_dict()  # type: ignore[assignment]

        # Initialize weekly event tracking
        # Check if we've already made a decision this week
        current_week = self.player_state.week
        week_decisions = [
            d for d in self.player_state.decision_history if d.get("week", 0) == current_week
        ]

        if week_decisions:
            # We already had an event this week
            self.last_event_week = current_week
        else:
            # No event yet this week, but check if we have a saved current_event
            if self.current_event:
                # We have a saved event, mark as generated
                self.last_event_week = current_week
            else:
                # No event saved, allow generation
                self.last_event_week = current_week - 1

        # Restore narrative_style_id from saved state
        style_id = state_dict.get("narrative_style_id")
        if style_id:
            self.narrative_style_id = style_id
            logger.info(f"[LoadGame] Restored narrative_style_id={style_id}")

        logger.info(f"Loaded game at age {self.player_state.age}, 第{self.player_state.week + 1}周")
        return self.player_state

    def generate_weekly_event(
        self,
        stream_callback: Optional[Callable[[str], None]] = None,
        force: bool = False,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[GameEvent]:
        """
        Generate an event for the current week.
        Events are generated every week.

        Args:
            stream_callback: Optional callback function to receive streaming text chunks
            force: Whether to force generation even if already generated this week

        Returns:
            GameEvent object, or None if already generated this week

        Raises:
            ValueError: If generation fails
        """
        if not self.player_state:
            raise ValueError("Game not started.")

        current_week = self.player_state.week

        # ★ 显示用周数（人类可读，从1开始）
        week_display = f"第{current_week + 1}周" if current_week is not None else "未知周"
        logger.debug(
            f"Generating weekly event: {week_display}, last_event_week={self.last_event_week}, force={force}"
        )

        # Check if we've already generated event for this week (unless force is True)
        if self.last_event_week >= current_week and not force:
            logger.debug(
                f"Already generated event for 第{current_week + 1}周 (last_event_week={self.last_event_week}), skipping"
            )
            return None

        # Check for milestone events first (bypass for force)
        if self.player_state.week in self.milestone_weeks and not force:
            logger.debug(f"Checking for milestone event at 第{self.player_state.week + 1}周")
            event = self._generate_milestone_event()
            if event:
                logger.info(f"Generated milestone event for 第{self.player_state.week + 1}周")
                self.current_event = event
                self.last_event_week = current_week
                return event

        # Generate regular weekly event
        logger.debug(f"Generating regular event for 第{self.player_state.week + 1}周")
        try:
            state_dict = self.player_state.to_dict()
            character_settings = state_dict.get("character_settings", {})

            # Get the most recent 4-week summary if available
            four_week_summary = None
            if self.player_state.four_week_summaries:
                four_week_summary = self.player_state.four_week_summaries[-1].get("summary")

            # Randomly decide whether to include yearly summary (if available)
            yearly_summary = None
            if self.player_state.yearly_summaries and random.random() < 0.5:
                yearly_summary = self.player_state.yearly_summaries[-1].get("summary")
                logger.info("Including yearly summary in event generation context")

            event = self.ai_generator.generate_event(
                state_dict,
                self.language,
                week=self.player_state.week,
                character_settings=character_settings,
                stream_callback=stream_callback,
                force=force,
                four_week_summary=four_week_summary,
                yearly_summary=yearly_summary,
                game_date_info=self.player_state.get_game_date_info(),
                pending_storylines=self.player_state.pending_storylines,
                established_facts=self.player_state.established_facts,
                last_event_concluded=self.player_state.last_event_concluded,
                last_round_full_story=self.player_state.last_round_full_story,
                activated_foreshadowing=NarrativeManager.select_foreshadowing_seed(
                    self.player_state
                ),
                character_habits=self.player_state.character_habits,
                status_callback=status_callback,
            )

            if not event:
                logger.error("AI generator returned None - this should not happen!")
                logger.error(
                    f"Player state: week={self.player_state.week}, age={self.player_state.age}"
                )
                logger.error(f"Character settings present: {bool(character_settings)}")
                event = self._generate_fallback_event()

            self.current_event = event

            # Save current event to player state for persistence
            self.player_state.current_event_data = event.model_dump()

            # Mark that we've generated an event for this week
            self.last_event_week = current_week

            if self.event_callback:
                self.event_callback(event, self.player_state)

            logger.debug(f"Successfully generated event for 第{self.player_state.week + 1}周")
            return event

        except Exception as e:
            logger.error(f"Failed to generate event: {str(e)}", exc_info=True)
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Player week: {self.player_state.week if self.player_state else 'N/A'}")
            # Fallback to a simple event
            event = self._generate_fallback_event()
            self.current_event = event
            self.player_state.current_event_data = event.model_dump()
            self.last_event_week = current_week
            logger.error(f"Using fallback event due to error: {str(e)}")
            return event

    def make_choice(self, option_index: int) -> Dict[str, Any]:
        """
        Process a player's choice.

        Args:
            option_index: Index of the chosen option (0-based)

        Returns:
            Dictionary with result information
        """
        if not self.player_state:
            raise ValueError("Game not started.")

        if not self.current_event:
            raise ValueError("No current event. Generate an event first.")

        # Convert GameEvent options to dict format
        event_options = [
            {"text": opt.text, "effects": opt.effects} for opt in self.current_event.options
        ]

        result = process_decision(
            self.player_state,
            self.current_event.event_description,
            option_index,
            event_options,
            self.language,
            generate_result_text=True,
            ai_generator=self.ai_generator,
        )

        # Clear current event data after choice is made
        self.player_state.current_event_data = None

        if self.result_callback:
            self.result_callback(result, self.player_state)

        return result

    def advance_to_next_week(self) -> bool:
        """
        Advance to the next week.
        Also handles saving stories and generating summaries.

        Returns:
            True if game continues, False if game over
        """
        if not self.player_state:
            raise ValueError("Game not started.")

        current_week = self.player_state.week

        # Save current story to history before advancing
        if self.current_event:
            date_info = self.player_state.get_game_date_info()
            story_entry = {
                "week": current_week,
                "story": self.current_event.event_description,
                "date_info": date_info,
            }
            self.player_state.story_history.append(story_entry)

            # Parallel post-processing (feature-gated)
            if get_feature("parallel_postprocessing"):
                self._run_parallel_postprocessing(self.current_event.event_description)

        # Apply weekly decay if applicable
        self._apply_weekly_decay()

        # Advance week
        self.player_state.advance_week()
        new_week = self.player_state.week

        # Check if we need to generate 4-week summary (every 4 weeks, i.e., week 4, 8, 12...)
        if new_week > 0 and new_week % 4 == 0:
            self._generate_four_week_summary(new_week)

        # Check if we need to generate yearly summary (every 48 weeks, i.e., week 48, 96, 144...)
        if new_week > 0 and new_week % 48 == 0:
            self._generate_yearly_summary(new_week)

        # Clear current event
        self.current_event = None
        self.player_state.current_event_data = None

        # Check if game is over
        if self.player_state.is_game_over():
            logger.info(
                f"Game ended at age {self.player_state.age}, 第{self.player_state.week + 1}周"
            )
            return False

        return True

    def _generate_four_week_summary(self, current_week: int) -> None:
        """
        Generate a summary for the past 4 weeks.

        Args:
            current_week: Current week number (just advanced to)
        """
        if not self.player_state:
            return

        # Get stories from the past 4 weeks
        start_week = current_week - 4
        stories = [
            entry.get("story", "")
            for entry in self.player_state.story_history
            if start_week <= entry.get("week", -1) < current_week
        ]

        # Get decisions from the past 4 weeks
        decisions = [
            d
            for d in self.player_state.decision_history
            if start_week <= d.get("week", -1) < current_week
        ]

        if not stories:
            return

        try:
            character_settings = self.player_state.character_settings
            summary_text = self.ai_generator.generate_four_week_summary(
                stories,
                decisions,
                character_settings,
                self.language,
                game_date_info=self.player_state.get_game_date_info(),
            )

            summary_entry = {
                "start_week": start_week,
                "end_week": current_week - 1,
                "summary": summary_text,
                "date_info": (self.player_state.get_game_date_info() if self.player_state else {}),
            }
            self.player_state.four_week_summaries.append(summary_entry)
            logger.info(f"Generated 4-week summary for 第{start_week + 1}周-第{current_week}周")

        except Exception as e:
            logger.error(f"Failed to generate 4-week summary: {e}")

    def _generate_yearly_summary(self, current_week: int) -> None:
        """
        Generate a yearly summary (every 48 weeks).

        Args:
            current_week: Current week number (just advanced to)
        """
        if not self.player_state:
            return

        # Get 4-week summaries from the past 48 weeks (up to 12 summaries)
        start_week = current_week - 48
        relevant_summaries = [
            s
            for s in self.player_state.four_week_summaries
            if start_week <= s.get("start_week", -1) < current_week
        ]

        if not relevant_summaries:
            return

        try:
            character_settings = self.player_state.character_settings
            summary_text = self.ai_generator.generate_yearly_summary(
                relevant_summaries,
                character_settings,
                start_week,
                current_week - 1,
                self.language,
                game_date_info=self.player_state.get_game_date_info(),
            )

            summary_entry = {
                "start_week": start_week,
                "end_week": current_week - 1,
                "summary": summary_text,
                "date_info": (self.player_state.get_game_date_info() if self.player_state else {}),
            }
            self.player_state.yearly_summaries.append(summary_entry)
            logger.info(f"Generated yearly summary for 第{start_week + 1}周-第{current_week}周")

        except Exception as e:
            logger.error(f"Failed to generate yearly summary: {e}")

    def _apply_weekly_decay(self) -> None:
        """Apply weekly resource decay if conditions are met."""
        if not self.player_state:
            return

        # Decay energy if too low (no rest)
        if self.player_state.energy < 30:
            self.player_state.update(energy=-settings.ENERGY_DECAY)

        # Decay mood if too low (stressed)
        if self.player_state.mood < 30:
            self.player_state.update(mood=-settings.MOOD_DECAY)

    def generate_summary(self, weeks: int = 10) -> Dict[str, Any]:
        """
        Generate a summary for the past N weeks (user-triggered).

        Args:
            weeks: Number of weeks to summarize (default: 10)

        Returns:
            Summary dictionary
        """
        if not self.player_state:
            raise ValueError("Game not started.")

        current_week = self.player_state.week
        start_week = max(0, current_week - weeks)

        # Get decisions from the specified period
        period_decisions = [
            d
            for d in self.player_state.decision_history
            if start_week <= d.get("week", 0) <= current_week
        ]

        if not period_decisions:
            return {
                "start_week": start_week,
                "end_week": current_week,
                "summary": (
                    "这段时间没有做出任何决策。"
                    if self.language == "zh"
                    else "No decisions made during this period."
                ),
                "highlights": [],
            }

        # Get state from start of period (approximate)
        start_state = self.player_state.to_dict()
        # Rough estimate: reverse the effects

        # Use yearly summary generator for flexibility
        summary = self.yearly_summary_gen.generate_summary(
            year=1,  # ★ 修复：参数名从 period_number 改为 year
            start_week=start_week,
            end_week=current_week,
            start_state=start_state,
            end_state=self.player_state,
            monthly_summaries=[],  # No monthly summaries in pure weekly mode
            decisions=period_decisions,
            language=self.language,
        )

        return summary

    def _generate_milestone_event(self) -> Optional[GameEvent]:
        """Generate a special milestone event."""
        # For now, return None to use regular generation
        # This can be enhanced with preset milestone events
        return None

    def _generate_fallback_event(self, is_round: bool = False) -> GameEvent:
        """Generate a simple fallback event if AI generation fails.

        Args:
            is_round: If True, use round-specific wording (e.g. day name).
        """
        logger.warning(
            f"Using {'round ' if is_round else ''}fallback event - AI generation failed!"
        )

        character_settings = self.player_state.character_settings if self.player_state else {}

        if is_round:
            prefix = (
                self.player_state.get_round_name(self.language) if self.player_state else "周一"
            )
        else:
            prefix = ""

        if self.language == "zh":
            if is_round:
                desc = (
                    f"{prefix}，你度过了平静的一天。生活的节奏张弛有度，你有一些时间可以自由支配。"
                )
            else:
                desc = "你度过了一个平静的一周。"
                if character_settings and "era" in character_settings:
                    era = character_settings["era"].get("era_description", "")
                    if era:
                        desc = f"在{era}的时代背景下，你度过了一个平静的一周。"
                desc += "你有一些空闲时间，可以思考接下来该做什么。"

            return GameEvent(
                event_description=desc,
                options=[
                    EventOption(
                        text=("保持现状，继续前进" if not is_round else "继续保持现有节奏"),
                        effects={
                            "energy": 0 if is_round else 5,
                            "mood": 5,
                            "knowledge": 0,
                            "wealth": 0,
                        },
                    ),
                    EventOption(
                        text="思考人生方向" if not is_round else "尝试做点不一样的事",
                        effects={"energy": -5, "mood": 0, "knowledge": 5, "wealth": 0},
                    ),
                ],
            )
        else:
            if is_round:
                desc = f"{prefix}, you had a quiet day. Life flows at a steady pace, and you have some time for yourself."
            else:
                desc = (
                    "You had a quiet week. You have some free time to think about what to do next."
                )

            return GameEvent(
                event_description=desc,
                options=[
                    EventOption(
                        text=(
                            "Keep status quo and move forward"
                            if not is_round
                            else "Maintain the current rhythm"
                        ),
                        effects={
                            "energy": 0 if is_round else 5,
                            "mood": 5,
                            "knowledge": 0,
                            "wealth": 0,
                        },
                    ),
                    EventOption(
                        text=(
                            "Reflect on life direction"
                            if not is_round
                            else "Try something different"
                        ),
                        effects={"energy": -5, "mood": 0, "knowledge": 5, "wealth": 0},
                    ),
                ],
            )

    def _run_parallel_postprocessing(self, story_text: str) -> None:
        """Run parallel post-processing for the current story turn.

        Only called when feature flag 'parallel_postprocessing' is enabled.
        """
        if not self.player_state:
            return

        # Lazy-init the processor
        if self._parallel_postprocessor is None:
            self._parallel_postprocessor = ParallelPostProcessor()

        # Determine the last choice text (from most recent decision)
        choice = ""
        if self.player_state.decision_history:
            last_decision = self.player_state.decision_history[-1]
            choice = last_decision.get("choice_text", "")

        try:
            pp_result = self._parallel_postprocessor.process(
                player_state=self.player_state,
                story_text=story_text,
                choice=choice,
                language=self.language,
                summary_generator=self.ai_generator,
                world_model_updater=self.world_updater,
            )
            if pp_result.errors:
                logger.warning(
                    "Parallel post-processing completed with errors: %s",
                    pp_result.errors,
                )
            else:
                logger.debug("Parallel post-processing completed successfully")
        except Exception as e:
            logger.error("Parallel post-processing failed: %s", e, exc_info=True)

    def shutdown(self) -> None:
        """Shutdown managed resources (e.g. thread pool)."""
        if self._parallel_postprocessor is not None:
            self._parallel_postprocessor.shutdown()
            self._parallel_postprocessor = None

    def get_state(self) -> Optional[PlayerState]:
        """Get current player state."""
        return self.player_state

    def is_game_over(self) -> bool:
        """Check if game has ended."""
        if not self.player_state:
            return False
        return self.player_state.is_game_over()

    def get_progress(self) -> Dict[str, Any]:
        """Get game progress information."""
        if not self.player_state:
            return {}

        return {
            "week": self.player_state.week,
            "total_weeks": settings.TOTAL_WEEKS,
            "age": self.player_state.age,
            "progress_percent": (self.player_state.week / settings.TOTAL_WEEKS) * 100,
        }
