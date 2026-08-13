"""Core game loop implementation."""

import logging
from threading import RLock
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from config.feature_flags import get_feature
from config.settings import settings
from src.ai.generator import EventGenerator
from src.ai.models import EventOption, GameEvent
from src.ai.story_exceptions import StoryGenerationFailure
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

    def _select_display_summary_context(self) -> tuple[Optional[str], Optional[str]]:
        """Return legacy prose memory only while structured memory is disabled."""
        if get_feature("structured_story_memory"):
            return None, None

        four_week_summary = None
        if self.player_state and self.player_state.four_week_summaries:
            latest = self.player_state.four_week_summaries[-1]
            four_week_summary = latest.get("summary") or latest.get("combined_summary")

        yearly_summary = None
        if (
            self.player_state
            and self.player_state.yearly_summaries
            and random.random() < 0.5
        ):
            latest = self.player_state.yearly_summaries[-1]
            yearly_summary = latest.get("summary") or latest.get("summary_text")
            logger.info("Including yearly summary in event generation context")
        return four_week_summary, yearly_summary

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
        self._daily_postprocessor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="daily-postproc"
        )
        self._daily_postprocess_persist_callback: Optional[Callable[[], bool]] = None
        # Choice settlement and current-day replacement share one commit lock so
        # a slow rewrite/regeneration cannot resurrect an already-settled day.
        self._daily_mutation_lock = RLock()

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
                    from src.ai.models import GameEvent, RecoverableGameEvent

                    self.current_event = GameEvent(**self.player_state.current_event_data)
                    logger.info(
                        f"[LoadGame] Restored current event from saved state: "
                        f"{self.current_event.event_description[:50]}..."
                    )
                except Exception as e:
                    event_description = self.player_state.current_event_data.get(
                        "event_description", ""
                    )
                    if event_description:
                        saved_options = self.player_state.current_event_data.get("options") or []
                        try:
                            self.current_event = RecoverableGameEvent(
                                event_description=event_description,
                                options=saved_options,
                            )
                        except Exception as recoverable_error:
                            logger.warning(
                                "[LoadGame] Dropping malformed partial event options: "
                                f"{recoverable_error}"
                            )
                            self.current_event = RecoverableGameEvent(
                                event_description=event_description,
                                options=[],
                            )
                        logger.info(
                            "[LoadGame] Restored partial current event without options: "
                            f"{event_description[:50]}..."
                        )
                    else:
                        logger.warning(f"[LoadGame] Failed to restore current event: {e}")
                        self.current_event = None
        else:
            logger.info("[LoadGame] No current_event_data, setting current_event to None")
            self.current_event = None

        # Daily settlement is never held hostage by enrichment. Preserve all
        # pending records and surface them to the normal background worker on
        # every restore.
        if self.player_state.timeline_version == 2:
            self._retry_pending_daily_postprocessing()

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

    def _retry_pending_daily_postprocessing(self) -> None:
        """Queue recoverable daily enrichment without blocking save restore."""
        pending = [
            record
            for record in self.player_state.day_history
            if isinstance(record, dict)
            and record.get("postprocessing_status") in {"pending", "failed"}
        ]
        if not pending:
            return
        logger.info("Daily post-processing retry pending for %d day(s)", len(pending))
        for record in pending:
            event_id = str(record.get("event_id") or "")
            if event_id:
                self._queue_daily_postprocessing(event_id)

    def _queue_daily_postprocessing(self, event_id: str) -> None:
        """Submit non-blocking summary/world extraction for one committed day."""
        self._daily_postprocessor.submit(self._process_daily_record, event_id)

    def _process_daily_record(self, event_id: str) -> None:
        state = self.player_state
        if state is None:
            return
        record = next(
            (
                item
                for item in state.day_history
                if isinstance(item, dict) and item.get("event_id") == event_id
            ),
            None,
        )
        if record is None or record.get("postprocessing_status") == "complete":
            return
        try:
            story = str(record.get("event_description") or "")
            choice = str(record.get("choice") or "")
            with ThreadPoolExecutor(max_workers=3) as executor:
                narrative_future = executor.submit(
                    self.story_service.compress_narrative,
                    story,
                    choice,
                    state.pending_storylines,
                )
                world_future = executor.submit(
                    self.story_service.extract_world_updates,
                    story,
                    choice,
                    state.established_facts,
                    state.character_habits,
                )
                entities_future = executor.submit(
                    self._recognize_daily_entities,
                    record,
                )
                narrative = narrative_future.result()
                world = world_future.result()
                entities = entities_future.result()
            NarrativeManager.process_storyline_updates(
                state, narrative.get("storyline_updates", [])
            )
            NarrativeManager.process_fact_updates(state, world.get("fact_updates", []))
            NarrativeManager.process_foreshadowing_seeds(
                state, world.get("foreshadowing_seeds", [])
            )
            NarrativeManager.process_habit_updates(state, world.get("habit_updates", []))
            WorldModelUpdater.process_location_updates(
                state, world.get("location_updates", [])
            )
            WorldModelUpdater.process_career_updates(
                state, world.get("career_updates", [])
            )
            WorldModelUpdater.process_commitment_updates(
                state, world.get("commitment_updates", [])
            )
            WorldModelUpdater.process_causal_updates(
                state, world.get("causal_updates", [])
            )
            record["summary"] = narrative.get("summary", "")
            record["postprocessing"] = {
                "narrative": narrative,
                "world": world,
                "entities": entities,
            }
            self._generate_daily_milestone_summaries(record)
            record["postprocessing_status"] = "complete"
            record.pop("postprocessing_error", None)
        except Exception as exc:
            record["postprocessing_status"] = "failed"
            record["postprocessing_error"] = str(exc)
            logger.warning("Daily post-processing failed for %s: %s", event_id, exc)
        finally:
            persist = getattr(self, "_daily_postprocess_persist_callback", None)
            if callable(persist):
                try:
                    persist()
                except Exception as exc:
                    logger.warning(
                        "Daily post-processing persistence failed for %s: %s",
                        event_id,
                        exc,
                    )

    def _recognize_daily_entities(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Recognize recurring entities off the choice path for later collection use."""
        state = self.player_state
        if state is None:
            return {"items": [], "characters": [], "landmarks": []}
        ai_client = getattr(self.ai_generator, "ai_client", None)
        if ai_client is None:
            return {"items": [], "characters": [], "landmarks": []}

        from src.services.entity_recognition_service import EntityRecognitionService

        settings = state.character_settings or {}
        protagonist = state.player_name or settings.get("player_name", "")
        existing_characters = list(state.characters.keys())
        if protagonist:
            existing_characters.append(protagonist)
        service = EntityRecognitionService(ai_client)
        return service.recognize_from_history(
            round_history=state.day_history,
            existing_items=list(state.items.keys()),
            existing_characters=existing_characters,
            existing_landmarks=list(state.landmarks.keys()),
            min_appearances=max(1, len(state.day_history) // 15),
            language=self.language,
        )

    def _generate_daily_milestone_summaries(self, record: Dict[str, Any]) -> None:
        """Generate 28-day and 365-day context summaries off the choice path."""
        milestones = record.get("summary_milestones") or []
        if not milestones or self.player_state is None:
            return

        state = self.player_state
        completed_days = int(record.get("day_index", -1)) + 1
        date_info = {
            "start_date": state.timeline.get("start_date"),
            "current_date": record.get("story_date"),
            "completed_days": completed_days,
        }
        if "long_term" in milestones:
            records = state.day_history[-28:]
            summary_text = self.ai_generator.generate_four_week_summary(
                [str(item.get("event_description") or "") for item in records],
                [
                    {
                        "choice": item.get("choice", ""),
                        "effects": item.get("effects_applied", {}),
                        "story_date": item.get("story_date"),
                    }
                    for item in records
                ],
                state.character_settings,
                self.language,
                game_date_info=date_info,
            )
            state.four_week_summaries.append(
                {
                    "start_day": completed_days - len(records),
                    "end_day": completed_days - 1,
                    "summary": summary_text,
                    "date_info": date_info,
                    "timeline_version": 2,
                }
            )

        if "yearly" in milestones:
            year_start = max(0, completed_days - 365)
            summaries = [
                item
                for item in state.four_week_summaries
                if int(item.get("end_day", -1)) >= year_start
            ]
            if not summaries:
                records = state.day_history[-365:]
                summaries = [
                    {
                        "start_day": year_start,
                        "end_day": completed_days - 1,
                        "summary": "\n".join(
                            str(item.get("summary") or item.get("event_description") or "")
                            for item in records
                        ),
                    }
                ]
            summary_text = self.ai_generator.generate_yearly_summary(
                summaries,
                state.character_settings,
                start_week=year_start // 7,
                end_week=(completed_days - 1) // 7,
                language=self.language,
                game_date_info=date_info,
            )
            state.yearly_summaries.append(
                {
                    "start_day": year_start,
                    "end_day": completed_days - 1,
                    "summary": summary_text,
                    "date_info": date_info,
                    "timeline_version": 2,
                }
            )

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

            four_week_summary, yearly_summary = self._select_display_summary_context()

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
                raise StoryGenerationFailure("AI generator returned no weekly event")

            self.current_event = event

            # Save current event to player state for persistence
            self.player_state.current_event_data = event.model_dump()

            # Mark that we've generated an event for this week
            self.last_event_week = current_week

            if self.event_callback:
                self.event_callback(event, self.player_state)

            logger.debug(f"Successfully generated event for 第{self.player_state.week + 1}周")
            return event

        except StoryGenerationFailure:
            raise
        except Exception as e:
            logger.error(f"Failed to generate event: {str(e)}", exc_info=True)
            raise StoryGenerationFailure(f"Weekly event generation failed: {e}") from e

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
                        },
                    ),
                    EventOption(
                        text="思考人生方向" if not is_round else "尝试做点不一样的事",
                        effects={"energy": -5, "mood": 0, "knowledge": 5},
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
                        },
                    ),
                    EventOption(
                        text=(
                            "Reflect on life direction"
                            if not is_round
                            else "Try something different"
                        ),
                        effects={"energy": -5, "mood": 0, "knowledge": 5},
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
        self._daily_postprocessor.shutdown(wait=False, cancel_futures=True)

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

        from src.game.daily_timeline import is_daily_timeline, normalize_daily_timeline

        if is_daily_timeline(self.player_state):
            timeline = normalize_daily_timeline(self.player_state.timeline)
            return {
                **timeline,
                "week": timeline["day_index"] // 7,
                "age": self.player_state.age,
                "progress_percent": (
                    timeline["completed_days"] / timeline["total_days"]
                )
                * 100,
            }
        return {
            "week": self.player_state.week,
            "total_weeks": settings.TOTAL_WEEKS,
            "age": self.player_state.age,
            "progress_percent": (self.player_state.week / settings.TOTAL_WEEKS) * 100,
        }
