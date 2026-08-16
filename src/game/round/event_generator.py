"""Round event generation service.

Handles the generation of events for each round in the game.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional, cast

from config.feature_flags import get_feature
from config.prompts._helpers import (
    _build_available_people_constraint,
    _build_era_anachronism_constraints,
    _build_full_character_context,
    _collect_available_people,
    build_realistic_modern_world_boundary,
)
from config.prompts.story_prompts import (
    _build_protagonist_identity_instruction,
    _build_zh_chapter_constraint,
    _extract_gender_text,
    build_daily_story_mode_constraint,
    resolve_protagonist_name,
)
from src.ai.budgets import (
    GenerationCallTracker,
    GenerationOperation,
    NarrativeKind,
    resolve_narrative_budget,
)
from src.ai.generation_budget import get_generation_budget
from src.ai.models import EventOption, GameEvent
from src.ai.option_generator import OptionGenerator
from src.ai.story_exceptions import StoryGenerationFailure
from src.game.narrative_manager import NarrativeManager
from src.game.relationship_authority import (
    build_required_cast_constraints,
    extract_required_key_people,
)

logger = logging.getLogger(__name__)


def apply_daily_event_metadata(
    event: GameEvent, player_state: Any, *, language: str = "zh"
) -> GameEvent:
    """Stamp every daily event path, including scheduled-event fast paths."""
    from src.game.daily_timeline import is_daily_timeline
    from src.game.daily_transition import prepare_daily_option_transitions

    if is_daily_timeline(player_state):
        timeline = player_state.timeline
        event.options = prepare_daily_option_transitions(
            event.options, player_state, language=language
        )
        event.event_id = f"day-{timeline['day_index']}-{uuid.uuid4().hex}"
        event.revision = 1
        event.story_date = timeline["current_date"]
    return event


class RoundEventGenerator:
    """Service for generating round events.

    This service handles:
    - Event generation with context building
    - Timeout handling and concurrency control
    - Fallback event generation
    """

    def __init__(
        self,
        player_state_getter: Callable[[], Any],
        ai_generator: Any,
        language_getter: Callable[[], str],
        character_introduction_service: Any,
        summary_selector: Any,
        relationship_service: Any,
        event_callback: Optional[Callable[[GameEvent, Any], None]] = None,
    ):
        """
        Args:
            player_state_getter: Function that returns current player state
            ai_generator: EventGenerator instance
            language_getter: Function that returns current language
            character_introduction_service: CharacterIntroductionService instance
            summary_selector: HistoricalSummarySelector instance
            relationship_service: RelationshipMCPService instance
            event_callback: Optional callback when event is generated
        """
        self._get_player_state = player_state_getter
        self.ai_generator = ai_generator
        self._get_language = language_getter
        self.character_introduction_service = character_introduction_service
        self.summary_selector = summary_selector
        self.relationship_service = relationship_service
        self.event_callback = event_callback

        # Generation state
        self._generating: bool = False
        self._generating_start_time: Optional[float] = None
        # P0-并发修复：check-then-set 生成标志改为原子操作，防止两个线程
        # 同时通过检查并都开始生成（重复计费/状态竞态）。
        self._generation_guard = threading.Lock()
        self._GENERATION_TIMEOUT: float = 120.0  # seconds
        self._OPTIONS_ONLY_TIMEOUT: float = 75.0  # seconds
        self._current_event: Optional[GameEvent] = None
        self._player_state_override: Optional[Any] = None

    @staticmethod
    def _persist_long_context_snapshots(
        player_state: Any, generated_state: Dict[str, Any]
    ) -> None:
        """Copy derived snapshots from the generation dict back into saved state."""
        snapshots = generated_state.get("long_context_snapshots")
        if isinstance(snapshots, list):
            player_state.long_context_snapshots = snapshots

    @staticmethod
    def _prompt_context(player_state: Any) -> Dict[str, Any]:
        """Use the projected state when available, preserving legacy state adapters."""
        prompt_context = getattr(player_state, "to_prompt_context", None)
        if callable(prompt_context):
            return cast(Dict[str, Any], prompt_context())
        return cast(Dict[str, Any], player_state.to_dict())

    @property
    def player_state(self) -> Any:
        if self._player_state_override is not None:
            return self._player_state_override
        return self._get_player_state()

    @property
    def language(self) -> str:
        return self._get_language()

    @property
    def current_event(self) -> Optional[GameEvent]:
        return self._current_event

    @current_event.setter
    def current_event(self, value: Optional[GameEvent]) -> None:
        self._current_event = value

    def _clear_generating_flag(self) -> None:
        """原子化清除生成标志（P0-并发修复：避免与置位竞态）。"""
        with self._generation_guard:
            self._generating = False
            self._generating_start_time = None

    def generate_round_event(
        self,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[Any], None]] = None,
        session: Optional[Any] = None,
        force_regenerate: bool = False,
        operation_id: Optional[str] = None,
    ) -> Optional[GameEvent]:
        """Generate one event, isolating all daily candidate side effects."""
        live_state = self.player_state
        from src.game.daily_timeline import is_daily_timeline

        def discard_candidate_chunk(_chunk: str) -> None:
            """Keep generator output private until the returned event is accepted."""

        if not is_daily_timeline(live_state) or not callable(
            getattr(live_state, "model_copy", None)
        ):
            event = self._generate_round_event_impl(
                stream_callback=discard_candidate_chunk,
                status_callback=status_callback,
                session=session,
                operation_id=operation_id,
            )
            if event is not None and stream_callback is not None:
                stream_callback(event.event_description)
            return event

        operation_id = operation_id or uuid.uuid4().hex
        original_state = live_state.model_copy(deep=True)
        staged_state = original_state.model_copy(deep=True)
        original_event = (
            self._current_event.model_copy(deep=True)
            if self._current_event is not None
            else None
        )
        original_timeline = deepcopy(getattr(live_state, "timeline", None))
        original_callback = self.event_callback
        before_people = self._relationship_people_names(live_state)

        if force_regenerate:
            staged_state.current_event_data = None
            self._current_event = None

        logger.info(
            "Daily generation transaction started operation_id=%s game_id=%s day_index=%s",
            operation_id,
            getattr(staged_state, "game_id", None),
            (getattr(staged_state, "timeline", {}) or {}).get("day_index"),
        )
        self._player_state_override = staged_state
        self.event_callback = None
        live_commit_started = False
        try:
            with self.character_introduction_service.use_player_state(staged_state):
                event = self._generate_round_event_impl(
                    stream_callback=discard_candidate_chunk,
                    status_callback=status_callback,
                    session=session,
                    operation_id=operation_id,
                )
            if event is None:
                raise StoryGenerationFailure("AI generator returned no round event")

            introduced_people = (
                self._relationship_people_names(staged_state) - before_people
            )
            missing_people = sorted(
                name
                for name in introduced_people
                if name and name not in event.event_description
            )
            if missing_people:
                raise StoryGenerationFailure(
                    "introduced character missing from accepted story: "
                    + ", ".join(missing_people)
                )

            if getattr(live_state, "timeline", None) != original_timeline:
                raise StoryGenerationFailure("stale daily generation transaction")

            live_commit_started = True
            self._replace_player_state(live_state, staged_state)
            self._current_event = event.model_copy(deep=True)
            if original_callback:
                original_callback(self._current_event, live_state)
            logger.info(
                "Daily generation transaction committed operation_id=%s game_id=%s "
                "event_id=%s revision=%s introduced=%s",
                operation_id,
                getattr(live_state, "game_id", None),
                getattr(self._current_event, "event_id", None),
                getattr(self._current_event, "revision", None),
                sorted(introduced_people),
            )
            if stream_callback is not None:
                stream_callback(self._current_event.event_description)
            return self._current_event
        except Exception:
            if live_commit_started:
                self._replace_player_state(live_state, original_state)
            self._current_event = original_event
            logger.info(
                "Daily generation transaction rolled back operation_id=%s game_id=%s",
                operation_id,
                getattr(live_state, "game_id", None),
            )
            raise
        finally:
            self.event_callback = original_callback
            self._player_state_override = None

    @staticmethod
    def _replace_player_state(target: Any, source: Any) -> None:
        """Commit a staged Pydantic state while preserving live object identity."""
        for field_name in type(target).model_fields:
            setattr(target, field_name, deepcopy(getattr(source, field_name)))

    @staticmethod
    def _relationship_people_names(player_state: Any) -> set[str]:
        settings = getattr(player_state, "character_settings", {}) or {}
        relationships = settings.get("relationships") or {}
        people = relationships.get("key_people") or []
        return {
            str(person.get("name") or "").strip()
            for person in people
            if isinstance(person, dict) and str(person.get("name") or "").strip()
        }

    def _generate_round_event_impl(
        self,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[Any], None]] = None,
        session: Optional[Any] = None,
        operation_id: Optional[str] = None,
    ) -> Optional[GameEvent]:
        """
        Generate an event for the current round within the week.
        Uses multi-round system: each week has multiple rounds.

        Args:
            stream_callback: Optional callback for streaming story text
            status_callback: Optional callback for reporting processing status

        Returns:
            GameEvent object for the current round
        """
        player_state = self.player_state
        if not player_state:
            raise ValueError("Game not started.")

        # ★ CRITICAL: Check if we already have a valid event with options
        if self._current_event and self._current_event.options:
            logger.info(
                f"Returning existing event (options count: {len(self._current_event.options)})"
            )
            return self._current_event

        # ★ CRITICAL: Resume from round_history if current_event is empty but story exists
        # This handles the "save & load" scenario where current_event_data is cleared after choice
        # but round_history contains the story for current round
        if not self._current_event or not self._current_event.options:
            current_week = player_state.week
            current_round = player_state.current_round
            round_history = player_state.round_history
            last_round_full_story = player_state.last_round_full_story

            logger.info(
                f"[Resume Check] current_week={current_week}, current_round={current_round}, "
                f"round_history_count={len(round_history) if round_history else 0}, "
                f"has_last_round_full_story={bool(last_round_full_story)}, "
                f"has_session={session is not None}"
            )

            # Check if we can resume from existing story
            # Case 1: round_history has current round's story
            # Case 2: last_round_full_story exists and matches current round (after choice, before next round)
            existing_story = None
            resume_source = None

            if self._current_event and not self._current_event.options:
                existing_story = self._current_event.event_description
                resume_source = "partial_current_event"
                logger.info(
                    "[Resume Check] Found partial current_event story without options"
                )
            elif round_history:
                last_entry = round_history[-1]
                entry_week = last_entry.get("week")
                entry_round = last_entry.get("round")

                logger.info(
                    f"[Resume Check] last_entry: week={entry_week}, round={entry_round}, "
                    f"has_event_desc={bool(last_entry.get('event_description'))}"
                )

                # Case 1: Current round story exists in round_history
                if entry_week == current_week and entry_round == current_round:
                    event_desc = last_entry.get("event_description", "")
                    story_continuation = last_entry.get("story_continuation", "")
                    existing_story = event_desc + (
                        f"\n\n{story_continuation}" if story_continuation else ""
                    )
                    resume_source = "round_history"
                    logger.info(
                        "[Resume Check] Found current round story in round_history"
                    )

                # Case 2: Last round is current_round - 1, and last_round_full_story exists
                # This means story was generated but choice not made yet
                # ★ CRITICAL: Only use last_round_full_story if current_event_data exists
                # This ensures the story was actually generated for the current round
                elif (
                    entry_week == current_week
                    and entry_round == current_round - 1
                    and last_round_full_story
                    and player_state.current_event_data
                ):
                    existing_story = last_round_full_story
                    resume_source = "last_round_full_story"
                    logger.info(
                        f"[Resume Check] Found story in last_round_full_story (current_round={current_round}, last_entry_round={entry_round})"
                    )

            # Also check last_round_full_story if no round_history match
            # ★ CRITICAL: Only use last_round_full_story for round 0 if current_event_data exists
            elif (
                last_round_full_story
                and current_round == 0
                and player_state.current_event_data
            ):
                existing_story = last_round_full_story
                resume_source = "last_round_full_story_only"
                logger.info(
                    "[Resume Check] Using last_round_full_story (no round_history match, round 0 with current_event)"
                )

            if existing_story and len(existing_story) > 100:
                if not self._existing_story_satisfies_quick_constraints(
                    existing_story=existing_story,
                    player_state=self._prompt_context(player_state),
                    character_settings=player_state.character_settings,
                    language=self.language,
                    resume_source=resume_source or "unknown",
                ):
                    existing_story = None
                    resume_source = None

            if existing_story and len(existing_story) > 100:
                # ★ Check options cache first
                cached_options = None
                if session:
                    cached_options = session.get_cached_options(
                        current_week, current_round, existing_story
                    )

                if cached_options:
                    # Use cached options - instant response!
                    logger.info(
                        f"★ Resume mode (cached options): Using {len(cached_options)} cached options "
                        f"for 第{current_week + 1}周 round {current_round}"
                    )

                    # Create event with cached options
                    options = [EventOption(**opt) for opt in cached_options]
                    event = GameEvent(
                        event_description=existing_story,
                        options=options,
                    )
                    apply_daily_event_metadata(
                        event, player_state, language=self.language
                    )

                    self._current_event = event
                    player_state.current_event_data = event.model_dump()

                    if self.event_callback:
                        self.event_callback(event, player_state)

                    logger.info(
                        f"★ Resume mode complete (cached): Returned {len(options)} options instantly"
                    )
                    return event

                # No cache - generate options
                logger.info(
                    f"★ Resume mode detected ({resume_source}): Found existing story for 第{current_week + 1}周 "
                    f"round {current_round} ({len(existing_story)} chars), generating options only"
                )

                with self._generation_guard:
                    self._generating = True
                    self._generating_start_time = time.time()

                try:
                    if status_callback:
                        status_callback("generating_options")

                    generated_event: GameEvent = (
                        self._generate_options_only_with_timeout(
                            existing_story=existing_story,
                            player_state=player_state,
                        )
                    )
                    apply_daily_event_metadata(
                        generated_event, player_state, language=self.language
                    )

                    # ★ Cache the generated options
                    if session and generated_event.options:
                        session.set_cached_options(
                            current_week,
                            current_round,
                            [opt.model_dump() for opt in generated_event.options],
                            existing_story,
                        )

                    self._current_event = generated_event
                    player_state.current_event_data = generated_event.model_dump()

                    if self.event_callback:
                        self.event_callback(generated_event, player_state)

                    logger.info(
                        f"★ Resume mode complete: Generated {len(generated_event.options)} options for existing story"
                    )
                    self._clear_generating_flag()
                    return generated_event

                except Exception as e:
                    logger.error(
                        f"Failed to generate options for existing story: {e}",
                        exc_info=True,
                    )
                    # Fall through to normal generation
                    self._clear_generating_flag()

        # The session-level durable operation owns normal request concurrency.
        # Keep this guard for direct callers, but never infer stale ownership
        # from elapsed wall time: a valid model call can exceed two minutes.
        with self._generation_guard:
            if self._generating:
                raise ValueError("Event generation in progress, please wait")
            # 设置生成标志（原子化，路由层另有 per-game 锁兜底）
            self._generating = True
            self._generating_start_time = time.time()

        # current_week and current_round already defined above in resume mode check
        # Re-fetch here to ensure consistency
        current_week = player_state.week
        current_round = player_state.current_round

        # ★ 显示用周数（人类可读，从1开始）
        week_display = (
            f"第{current_week + 1}周" if current_week is not None else "未知周"
        )
        logger.info(f"Generating round event: {week_display}, round={current_round}")

        # ★ 步骤0: 检查是否有预定事件需要触发
        from src.game.daily_timeline import is_daily_timeline

        scheduled_events = (
            player_state.get_pending_scheduled_events()
            if is_daily_timeline(player_state)
            else player_state.get_pending_scheduled_events(current_week, current_round)
        )
        if scheduled_events:
            logger.info(f"检测到 {len(scheduled_events)} 个预定事件需要触发")
            try:
                scheduled_event = self._generate_scheduled_event(
                    scheduled_events, player_state, stream_callback, status_callback
                )
                if scheduled_event:
                    apply_daily_event_metadata(
                        scheduled_event, player_state, language=self.language
                    )
                    self._current_event = scheduled_event
                    player_state.current_event_data = scheduled_event.model_dump()
                    # 标记预定事件已触发
                    for se in scheduled_events:
                        player_state.mark_scheduled_event_triggered(se.get("event_id"))
                    if self.event_callback:
                        self.event_callback(scheduled_event, player_state)
                    self._clear_generating_flag()
                    return scheduled_event
            except Exception:
                # This branch precedes the normal generation cleanup scope.
                # Always release the direct-call guard on terminal failure.
                self._clear_generating_flag()
                raise

        # Get round context from player state
        round_context = player_state.get_round_context()
        opening_story = (getattr(player_state, "character_settings", {}) or {}).get(
            "opening_story"
        )
        if (
            current_week == 0
            and current_round == 0
            and isinstance(opening_story, str)
            and opening_story.strip()
        ):
            round_context = (
                "【开场已呈现的经历 - 仅作连续性依据，不得复述其中的场景、对话或开场】\n"
                f"{opening_story.strip()}\n\n"
                f"{round_context}"
            ).strip()

        try:
            # 发送初始化状态
            if status_callback:
                status_callback("initializing")

            # 步骤1: 尝试生成新人物（存入待引入队列，不立即引入）
            self.character_introduction_service.maybe_generate_new_character(
                probability=0.08
            )

            # 步骤2: 检查是否有合适的引入机会
            new_character = None
            pending_entry = (
                self.character_introduction_service.check_introduction_opportunity()
            )
            if pending_entry:
                new_character = (
                    self.character_introduction_service.introduce_pending_character(
                        pending_entry
                    )
                )
                if new_character:
                    intro_ctx = pending_entry.get("introduction_context", "random")
                    logger.info(
                        f"本轮引入待引入人物: {new_character.get('name')} - {new_character.get('role')} (场景: {intro_ctx})"
                    )

            # 获取最新的状态（可能已包含新引入的人物）
            # P2-性能优化：生成 prompt 只需近期上下文，使用字段投影避免全量序列化。
            state_dict = self._prompt_context(player_state)
            character_settings = state_dict.get("character_settings", {})

            # Reviews keep their summaries, while story generation receives the
            # append-only event log as its cache-stable historical context.
            if status_callback:
                status_callback("loading_context")
            historical_weekly, historical_yearly = None, None

            # 检测关系事件触发
            relationship_events = []
            try:
                era_info = character_settings.get("era", {})
                era = era_info.get("era_description", "modern")
                relationship_events = self.relationship_service.get_triggered_events(
                    player_state, era=era, max_events=2
                )
                if relationship_events:
                    logger.info(
                        f"检测到{len(relationship_events)}个关系事件: {[e['event_type'] for e in relationship_events]}"
                    )
            except Exception as e:
                logger.warning(f"关系事件检测失败: {e}")

            # 构建世界模型用于约束和校验
            if status_callback:
                status_callback("building_world")
            world_model = None
            try:
                if is_daily_timeline(player_state):
                    from src.game.world_constraint_freshness import (
                        build_validation_world_model,
                    )

                    validation_view = build_validation_world_model(player_state)
                    world_model = validation_view.world_model
                    resolved_prompt_context = "\n\n".join(
                        value
                        for value in (
                            getattr(world_model, "canonical_tail", ""),
                            validation_view.soft_context,
                        )
                        if value
                    )
                    if resolved_prompt_context:
                        round_context = (
                            f"{round_context}\n\n{resolved_prompt_context}"
                        ).strip()
                    if not validation_view.freshness.world_derivations_are_fresh:
                        for category in (
                            "location",
                            "commitment",
                            "causal",
                            "career",
                            "habit",
                        ):
                            logger.warning(
                                "stale_world_constraint_downgraded "
                                "game_id=%s day_index=%s category=%s reason=%s",
                                getattr(player_state, "game_id", None),
                                (getattr(player_state, "timeline", {}) or {}).get(
                                    "day_index"
                                ),
                                category,
                                validation_view.freshness.reason,
                            )
                else:
                    from src.game.world_model import WorldModel

                    world_model = WorldModel.from_player_state(player_state)
                logger.info(
                    f"WorldModel built: {len(world_model.character_locations)} locations, "
                    f"{len(world_model.career_records)} careers, "
                    f"{len(world_model.active_commitments)} commitments, "
                    f"{len(world_model.causal_chains)} causal chains"
                )
            except Exception as e:
                logger.warning(f"WorldModel 构建失败，将跳过一致性校验: {e}")

            # 发送开始生成故事的状态
            if status_callback:
                status_callback("generating_story")

            foreshadowing_state = player_state
            if is_daily_timeline(player_state) and get_feature(
                "daily_world_projection_v1"
            ):
                foreshadowing_state = SimpleNamespace(
                    foreshadowing_seeds=getattr(
                        world_model,
                        "hard_foreshadowing_seeds",
                        [],
                    ),
                    week=player_state.week,
                    pending_storylines=player_state.pending_storylines,
                    foreshadowing_metrics=player_state.foreshadowing_metrics,
                )

            ai_event = cast(
                Optional[GameEvent],
                self.ai_generator.generate_round_event(
                    player_state=state_dict,
                    language=self.language,
                    round_number=current_round,
                    round_context=round_context,
                    character_settings=character_settings,
                    stream_callback=stream_callback,
                    relationship_events=relationship_events,
                    historical_weekly_summary=historical_weekly,
                    historical_yearly_summary=historical_yearly,
                    game_date_info=player_state.get_game_date_info(),
                    pending_storylines=player_state.pending_storylines,
                    established_facts=getattr(
                        world_model,
                        "hard_established_facts",
                        player_state.established_facts,
                    ),
                    last_event_concluded=player_state.last_event_concluded,
                    last_round_full_story=player_state.last_round_full_story,
                    activated_foreshadowing=NarrativeManager.select_foreshadowing_seed(
                        foreshadowing_state
                    ),
                    character_habits=getattr(
                        world_model,
                        "hard_character_habits",
                        player_state.character_habits,
                    ),
                    world_model=world_model,
                    new_character=new_character,
                    status_callback=status_callback,
                    operation_id=operation_id,
                ),
            )
            self._persist_long_context_snapshots(player_state, state_dict)

            # 如果有关系事件被触发，标记为已触发
            if relationship_events and ai_event:
                for rel_event in relationship_events:
                    try:
                        self.relationship_service.mark_event_triggered(
                            player_state,
                            rel_event["character_name"],
                            rel_event["event_type"],
                        )
                        logger.info(
                            f"标记事件已触发: {rel_event['event_type']} for {rel_event['character_name']}"
                        )
                    except Exception as e:
                        logger.warning(f"标记事件触发失败: {e}")

            if not ai_event:
                raise StoryGenerationFailure("AI generator returned no round event")

            apply_daily_event_metadata(ai_event, player_state, language=self.language)

            self._current_event = ai_event

            # Save current event to player state for persistence
            player_state.current_event_data = ai_event.model_dump()

            if self.event_callback:
                self.event_callback(ai_event, player_state)

            logger.info(
                f"Successfully generated round event for 第{current_week + 1}周, round {current_round}"
            )
            self._clear_generating_flag()
            return ai_event

        except StoryGenerationFailure:
            self._clear_generating_flag()
            raise
        except Exception as e:
            logger.error(f"Failed to generate round event: {str(e)}", exc_info=True)
            self._clear_generating_flag()
            raise StoryGenerationFailure(f"Round event generation failed: {e}") from e

    def _generate_options_only_with_timeout(
        self,
        *,
        existing_story: str,
        player_state: Any,
    ) -> GameEvent:
        """Bound resume-only option generation so recovery never strands the player."""

        def call_options_generator() -> GameEvent:
            return cast(
                GameEvent,
                self.ai_generator.generate_options_only(
                    story_description=existing_story,
                    player_state=self._prompt_context(player_state),
                    character_settings=player_state.character_settings,
                    language=self.language,
                ),
            )

        executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="options-resume"
        )
        future = executor.submit(call_options_generator)
        try:
            return future.result(timeout=self._OPTIONS_ONLY_TIMEOUT)
        except FutureTimeoutError:
            future.cancel()
            logger.warning(
                "Options-only generation timed out after %.1fs; using contextual fallback options",
                self._OPTIONS_ONLY_TIMEOUT,
            )
            fallback_options = OptionGenerator.build_contextual_fallback_options(
                story_description=existing_story,
                language=self.language,
            )
            return GameEvent(event_description=existing_story, options=fallback_options)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _existing_story_satisfies_quick_constraints(
        self,
        *,
        existing_story: str,
        player_state: dict[str, Any],
        character_settings: dict[str, Any],
        language: str,
        resume_source: str,
    ) -> bool:
        """Do not resume a persisted story that already violates hard story constraints."""
        if not existing_story:
            return True

        from src.ai.quick_validator import quick_validate_story

        available_people_names = [
            p.get("name", "")
            for p in _collect_available_people(character_settings)
            if p.get("name")
        ]
        quick_result = quick_validate_story(
            story_text=existing_story,
            character_settings=character_settings,
            available_people=available_people_names,
            language=language,
        )
        from src.ai.daily_opening import validate_daily_first_opening

        daily_issues = validate_daily_first_opening(
            existing_story,
            player_state,
            character_settings,
            language,
        )
        if daily_issues:
            quick_result.issues.extend(daily_issues)
            quick_result.passed = False
        if quick_result.passed:
            if quick_result.warnings:
                logger.info(
                    "[Resume Check] Existing story warnings from %s: %s",
                    resume_source,
                    quick_result.warnings,
                )
            return True

        logger.warning(
            "[Resume Check] Rejecting existing story from %s because it violates quick constraints: %s",
            resume_source,
            quick_result.issues,
        )
        return False

    def _generate_fallback_event(self, is_round: bool = True) -> GameEvent:
        """Generate a fallback event when AI generation fails."""
        from src.ai.models import EventOption

        player_state = self.player_state
        language = self.language
        character_settings = getattr(player_state, "character_settings", {}) or {}
        player_dict = self._prompt_context(player_state)
        protagonist_name = (
            resolve_protagonist_name(player_dict, character_settings, None)
            or getattr(player_state, "player_name", "")
            or ("你" if language == "zh" else "You")
        )
        key_people = extract_required_key_people(character_settings)
        anchor_person = key_people[0] if key_people else {}
        occupation = self._extract_setting_text(
            character_settings,
            ["occupation", "job_title", "career", "profession", "identity"],
        )
        era = self._extract_setting_text(
            character_settings,
            ["era_description", "era_name", "world_context", "period", "year"],
        )
        role = anchor_person.get("role") or anchor_person.get("relationship") or ""

        if language == "zh":
            if anchor_person.get("name") or occupation or era:
                era_clause = f"在{era}的背景下，" if era else ""
                occupation_clause = f"作为{occupation}，" if occupation else ""
                anchor_clause = ""
                if anchor_person.get("name"):
                    role_clause = f"这位{role}" if role else "这位预设关键人物"
                    anchor_clause = (
                        f"{anchor_person['name']}{role_clause}仍在{protagonist_name}的关系网里，"
                        "提醒她先守住已确定的人物关系和现实处境。"
                    )
                description = (
                    f"{era_clause}第{getattr(player_state, 'week', 0) + 1}周，"
                    f"{protagonist_name}没有被新的陌生人物带离主线。"
                    f"{occupation_clause}她把眼前的线索和上一轮选择重新整理，"
                    f"{anchor_clause}"
                    "这一次保底事件只推进一个小决策：是先稳住当前关系，"
                    "还是把精力投入到下一步行动准备中。"
                )
            else:
                description = "一个平静的日子，没有特别的事情发生。"
            options = [
                EventOption(text="安静地度过", effects={}),
                EventOption(text="主动寻找有趣的事", effects={"mood": 5}),
                EventOption(text="专注于工作/学习", effects={"knowledge": 5}),
            ]
            if anchor_person.get("name"):
                options = [
                    EventOption(
                        text=f"联系{anchor_person['name']}确认下一步",
                        effects={
                            "knowledge": 3,
                            "relationships": {anchor_person["name"]: 2},
                        },
                    ),
                    EventOption(
                        text="先独自整理当前线索",
                        effects={"energy": -3, "knowledge": 2},
                    ),
                    EventOption(
                        text="放慢节奏恢复状态", effects={"mood": 3, "energy": 2}
                    ),
                ]
        else:
            if anchor_person.get("name") or occupation or era:
                era_clause = f"In the context of {era}, " if era else ""
                occupation_clause = f"as {occupation}, " if occupation else ""
                anchor_clause = ""
                if anchor_person.get("name"):
                    role_clause = f" as {role}" if role else ""
                    anchor_clause = (
                        f"{anchor_person['name']}{role_clause} remains part of "
                        f"{protagonist_name}'s preset relationship network. "
                    )
                description = (
                    f"{era_clause}week {getattr(player_state, 'week', 0) + 1} gives "
                    f"{protagonist_name} a quieter fallback moment. {occupation_clause}"
                    f"{anchor_clause}The scene stays inside the established character setup "
                    "and asks only one small decision: preserve the current relationship thread "
                    "or prepare the next concrete action."
                )
            else:
                description = "A quiet day with nothing special happening."
            options = [
                EventOption(text="Spend quietly", effects={}),
                EventOption(text="Look for something interesting", effects={"mood": 5}),
                EventOption(text="Focus on work/study", effects={"knowledge": 5}),
            ]
            if anchor_person.get("name"):
                options = [
                    EventOption(
                        text=f"Check in with {anchor_person['name']}",
                        effects={
                            "knowledge": 3,
                            "relationships": {anchor_person["name"]: 2},
                        },
                    ),
                    EventOption(
                        text="Organize the current clues",
                        effects={"energy": -3, "knowledge": 2},
                    ),
                    EventOption(
                        text="Slow down and recover", effects={"mood": 3, "energy": 2}
                    ),
                ]

        return GameEvent(
            event_description=description,
            options=options,
        )

    @staticmethod
    def _extract_setting_text(
        character_settings: dict[str, Any], keys: list[str]
    ) -> str:
        """Extract a concise setting value from nested character settings."""
        if not character_settings:
            return ""

        def walk(value: Any) -> str:
            if isinstance(value, dict):
                for key in keys:
                    item = value.get(key)
                    if item is not None and str(item).strip():
                        return str(item).strip()
                for item in value.values():
                    found = walk(item)
                    if found:
                        return found
            elif isinstance(value, list):
                for item in value:
                    found = walk(item)
                    if found:
                        return found
            elif value is not None and str(value).strip():
                return str(value).strip()
            return ""

        return walk(character_settings)

    def _generate_scheduled_event(
        self,
        scheduled_events: list[Dict[str, Any]],
        player_state: Any,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[Any], None]] = None,
    ) -> Optional[GameEvent]:
        """根据预定事件生成强制事件。

        当检测到有预定事件需要触发时，调用此方法生成事件。
        事件内容必须围绕兑现承诺展开。

        Args:
            scheduled_events: 预定事件列表
            player_state: PlayerState 实例
            stream_callback: 流式回调
            status_callback: 状态回调

        Returns:
            GameEvent 实例
        """
        if status_callback:
            status_callback("generating_scheduled_event")

        from src.game.daily_timeline import is_daily_timeline

        daily_mode = is_daily_timeline(player_state)
        attempts_used = 0

        # 合并多个预定事件的信息（如果有多个）
        descriptions = []
        all_parties = set()
        event_hints = []
        max_importance = "normal"
        from src.game.constants import IMPORTANCE_ORDER

        for se in scheduled_events:
            descriptions.append(se.get("description", ""))
            parties = se.get("parties")
            if isinstance(parties, list):
                all_parties.update(item for item in parties if isinstance(item, str))
            if se.get("event_hint"):
                event_hints.append(str(se.get("event_hint")))
            # 取最高重要程度
            se_importance = se.get("importance", "normal")
            if IMPORTANCE_ORDER.get(se_importance, 2) < IMPORTANCE_ORDER.get(
                max_importance, 2
            ):
                max_importance = se_importance

        # 构建强制事件的提示
        combined_description = "；".join(descriptions)
        parties_str = "、".join(all_parties) if all_parties else ""

        logger.info(
            f"生成预定事件: {combined_description[:60]}... (涉及: {parties_str})"
        )

        try:
            # 使用AI生成事件内容，但必须包含承诺的核心元素
            # P2-性能优化：投影近期上下文即可；duck-typed 状态回退到全量序列化。
            state_dict = self._prompt_context(player_state)
            character_settings = state_dict.get("character_settings", {})

            # 构建强制事件提示词
            prompt = self._build_scheduled_event_prompt(
                scheduled_events=scheduled_events,
                player_state=state_dict,
                character_settings=character_settings,
                language=self.language,
            )

            from src.ai.system_prompts import get_system_prompt

            sys_prompt = get_system_prompt("story_novelist", self.language)

            from src.ai.quick_validator import quick_validate_story
            from src.ai.utils import extract_json

            available_people_names = [
                p.get("name", "")
                for p in _collect_available_people(character_settings)
                if p.get("name")
            ]
            last_validation_error = ""
            last_rejected_story = ""
            last_validation_findings = []
            raw_quality_level = (
                getattr(self.ai_generator, "quality_level", None) or "expert"
            )
            quality_level = str(getattr(raw_quality_level, "value", raw_quality_level))
            narrative_budget = (
                resolve_narrative_budget(
                    NarrativeKind.ROUND,
                    GenerationOperation.GENERATE,
                    quality_level,
                    self.language,
                )
                if is_daily_timeline(player_state)
                or get_feature("unified_narrative_budgets")
                else None
            )
            generation_tracker = (
                GenerationCallTracker(narrative_budget)
                if narrative_budget is not None
                else None
            )
            max_attempts = (
                narrative_budget.prose_call_limit if narrative_budget is not None else 2
            )

            for attempt in range(max_attempts):
                attempts_used = attempt + 1
                prompt_for_attempt = prompt
                if attempt > 0 and last_validation_error:
                    if self.language == "zh":
                        prompt_for_attempt += (
                            "\n\n【快速一致性修正 - 必须重写】\n"
                            f"{last_validation_error}\n"
                            f"【上一稿全文】\n{last_rejected_story}\n【上一稿结束】\n"
                            "请重新生成这个预定事件，严格使用可用人物列表、预设关键人物和既有人设。"
                        )
                    else:
                        prompt_for_attempt += (
                            "\n\n[Quick Consistency Fix - Regenerate Required]\n"
                            f"{last_validation_error}\n"
                            "Regenerate this scheduled event using the available people, preset cast, and existing setting."
                        )
                    if status_callback:
                        status_callback(
                            {
                                "phase": "retry",
                                "attempt": attempt + 1,
                                "max_attempts": max_attempts,
                                "quality_level": quality_level,
                            }
                        )

                if generation_tracker is not None:
                    generation_tracker.consume("prose")
                response = self.ai_generator.ai_client.call(
                    system_prompt=sys_prompt,
                    user_prompt=prompt_for_attempt,
                    temperature=0.85 if attempt == 0 else 0.65,
                    max_tokens=(
                        narrative_budget.max_output_tokens
                        if narrative_budget is not None
                        else get_generation_budget(quality_level).max_tokens
                    ),
                    stream_callback=stream_callback,
                    thinking=False,
                    request_timeout=(
                        generation_tracker.cap_timeout()
                        if generation_tracker is not None
                        else None
                    ),
                    generation_tracker=generation_tracker,
                )

                data = extract_json(response)

                if data:
                    raw_event_desc = data.get("event_description", "")
                    event_desc = (
                        raw_event_desc.strip()
                        if isinstance(raw_event_desc, str)
                        else ""
                    )
                    options_data = data.get("options", [])
                    options = OptionGenerator._parse_candidate_options(options_data)

                    if event_desc:
                        options = OptionGenerator.complete_new_event_options(
                            options,
                            story_description=event_desc,
                            language=self.language,
                            decision_history=state_dict.get("decision_history", []),
                        )
                        from src.game.daily_transition import (
                            prepare_daily_option_transitions,
                        )

                        options = prepare_daily_option_transitions(
                            options,
                            state_dict,
                            language=self.language,
                        )
                        quick_result = quick_validate_story(
                            story_text=event_desc,
                            character_settings=character_settings,
                            available_people=available_people_names,
                            required_people=sorted(all_parties),
                            language=self.language,
                        )
                        from src.ai.daily_opening import validate_daily_first_opening

                        daily_issues = validate_daily_first_opening(
                            event_desc,
                            state_dict,
                            character_settings,
                            self.language,
                        )
                        if daily_issues:
                            quick_result.issues.extend(daily_issues)
                            quick_result.passed = False
                        if not quick_result.passed:
                            last_validation_error = "; ".join(quick_result.issues)
                            last_rejected_story = event_desc
                            last_validation_findings = list(quick_result.hard_findings)
                            logger.warning(
                                "Scheduled event quick validation failed: %s",
                                quick_result.issues,
                            )
                            continue

                        event = GameEvent(
                            event_description=event_desc,
                            options=options,
                        )
                        logger.info(f"成功生成预定事件: {event_desc[:60]}...")
                        return event

            if daily_mode:
                raise StoryGenerationFailure(
                    "scheduled event candidates exhausted required validation",
                    findings=last_validation_findings,
                    attempts_used=attempts_used,
                )

            # Legacy weekly rounds keep their deterministic compatibility fallback.
            logger.warning("解析预定事件响应失败，使用简化版本")
            return self._generate_simple_scheduled_event(scheduled_events, player_state)

        except StoryGenerationFailure:
            raise
        except Exception as e:
            logger.error(f"生成预定事件失败: {e}")
            if daily_mode:
                raise StoryGenerationFailure(
                    f"scheduled event generation failed: {type(e).__name__}",
                    attempts_used=attempts_used,
                ) from e
            return self._generate_simple_scheduled_event(scheduled_events, player_state)

    def _build_scheduled_event_prompt(
        self,
        scheduled_events: list[Dict[str, Any]],
        player_state: Dict[str, Any],
        character_settings: Dict[str, Any],
        language: str,
    ) -> str:
        """构建预定事件的提示词。"""

        # 合并预定事件信息
        descriptions = []
        all_parties = set()
        event_hints = []

        for se in scheduled_events:
            descriptions.append(se.get("description", ""))
            parties = se.get("parties")
            if isinstance(parties, list):
                all_parties.update(item for item in parties if isinstance(item, str))
            if se.get("event_hint"):
                event_hints.append(str(se.get("event_hint")))

        combined_description = "；".join(descriptions)
        combined_hint = "；".join(event_hints) if event_hints else ""
        parties_str = "、".join(all_parties) if all_parties else ""

        player_name = (
            resolve_protagonist_name(player_state, character_settings, None) or "主角"
        )
        protagonist_gender = _extract_gender_text(character_settings)
        character_context, available_people = _build_full_character_context(
            character_settings,
            language,
        )
        available_people_str = _build_available_people_constraint(
            available_people, language
        )
        name_instruction = _build_protagonist_identity_instruction(
            player_name,
            protagonist_gender,
            language,
        )
        required_cast_context = build_required_cast_constraints(
            character_settings or {}, language
        )
        modern_world_boundary = build_realistic_modern_world_boundary(
            character_settings,
            language,
        )
        era_constraints = _build_era_anachronism_constraints(
            character_settings, language
        )
        timeline = player_state.get("timeline")
        daily_mode = isinstance(timeline, dict) and timeline.get("version") == 2
        week = int(player_state.get("week", 0) or 0)
        current_round = int(player_state.get("current_round", 0) or 0)
        rounds_per_week = player_state.get("rounds_per_week", 3) or 3
        total_chapter = week * int(rounds_per_week) + current_round + 1

        round_names = (
            ["周一", "周中", "周末"]
            if language == "zh"
            else ["Monday", "Midweek", "Weekend"]
        )
        round_name = (
            round_names[current_round]
            if current_round < len(round_names)
            else f"Round {current_round}"
        )
        zh_chapter_constraint = (
            _build_zh_chapter_constraint(
                total_chapter,
                week,
                current_round,
                character_settings,
            )
            if language == "zh" and not daily_mode
            else ""
        )
        zh_timeline_title = f"第{week + 1}周·{round_name}" if language == "zh" else ""
        daily_constraint = build_daily_story_mode_constraint(
            player_state,
            character_settings,
            language,
        )
        resolved_hard_context = ""
        resolved_writing_context = ""
        if daily_mode:
            from src.ai.story_generator import StoryGenerator

            resolved_world = StoryGenerator._build_world_model_from_state_dict(
                player_state
            )
            if resolved_world is not None:
                hard_sections = [resolved_world.build_constraints_text(language)]
                hard_facts = getattr(
                    resolved_world,
                    "hard_established_facts",
                    (),
                )
                fact_lines = [
                    str(fact.get("fact") or "").strip()
                    for fact in hard_facts
                    if isinstance(fact, dict) and str(fact.get("fact") or "").strip()
                ]
                if fact_lines:
                    label = (
                        "【不可变基础事实】"
                        if language == "zh"
                        else "[Immutable Base Facts]"
                    )
                    hard_sections.append(label + "\n" + "\n".join(fact_lines))
                resolved_hard_context = "\n".join(
                    section for section in hard_sections if section
                )
                writing_sections = [
                    getattr(resolved_world, "canonical_tail", ""),
                    getattr(resolved_world, "soft_context", ""),
                ]
                writing_sections = [section for section in writing_sections if section]
                if writing_sections:
                    label = (
                        "【连续性写作上下文（软记录不得作为拒稿依据）】"
                        if language == "zh"
                        else "[Continuity Writing Context (soft records are not rejection grounds)]"
                    )
                    resolved_writing_context = (
                        label + "\n" + "\n\n".join(writing_sections)
                    )
        quality_level = str(
            getattr(self.ai_generator, "quality_level", None) or "expert"
        )
        length_requirement = get_generation_budget(quality_level).length_requirement(
            language
        )

        if language == "zh":
            current_time = (
                "日期由界面统一展示" if daily_mode else f"当前时间：{zh_timeline_title}"
            )
            transition_requirement = (
                "\n7. 每个选项必须包含 transition_text：一句12-28个汉字的含蓄次日转场，"
                "不得复述选项、显示数值、预言结果或引入新事实"
                if daily_mode
                else ""
            )
            transition_json = (
                ', "transition_text": "决定的余韵仍在，时间已悄然走向明日。"'
                if daily_mode
                else ""
            )
            return f"""【强制事件】角色之前做出的承诺必须在本轮兑现。

承诺内容：{combined_description}
涉及人物：{parties_str}
事件提示：{combined_hint}

{current_time}
玩家姓名：{player_name}

{zh_chapter_constraint}
{daily_constraint}

【角色设定硬约束】
{character_context if character_context else "标准现代青年"}{name_instruction}{available_people_str}
{required_cast_context}{modern_world_boundary}{era_constraints}
{resolved_hard_context}

{resolved_writing_context}

【要求】
1. 事件必须围绕兑现上述承诺展开
2. 必须涉及上述人物
3. 事件开头要自然衔接之前的承诺（如"记得之前答应过..."）
4. {length_requirement}，生动有深度
5. 提供恰好3个选项，每个选项目标8-24字、超过40字必须重写，且都要与承诺相关
6. 选项应呈现真实的权衡取舍{transition_requirement}

【输出格式】
返回JSON格式：
{{
  "event_description": "事件描述（{length_requirement}）",
  "options": [
    {{"text": "选项文本（目标8-24字）", "effects": {{"energy": -10, "mood": 5, ...}}{transition_json}}},
    ...
  ]
}}

只返回JSON，不要其他文本。"""
        else:
            current_time = (
                "The interface displays the exact date"
                if daily_mode
                else f"Current time: Week {week}, {round_name}"
            )
            transition_requirement = (
                "\n7. Every option must include transition_text: one subtle 5-18 word sentence "
                "carrying the choice toward tomorrow without stats, predictions, or new facts"
                if daily_mode
                else ""
            )
            transition_json = (
                ', "transition_text": "The choice settles quietly as tomorrow draws nearer."'
                if daily_mode
                else ""
            )
            return f"""[MANDATORY EVENT] The character must fulfill their previous commitment this round.

Commitment: {combined_description}
Characters involved: {parties_str}
Event hints: {combined_hint}

{current_time}
Player name: {player_name}

{daily_constraint}

[Character Setting Hard Constraints]
{character_context if character_context else "Standard modern young adult"}{name_instruction}{available_people_str}
{required_cast_context}{modern_world_boundary}{era_constraints}
{resolved_hard_context}

{resolved_writing_context}

[Requirements]
1. The event must center on fulfilling the above commitment
2. Must involve the listed characters
3. Start naturally by referencing the previous promise (e.g., "Remembering the promise to...")
4. {length_requirement}, vivid and deep
5. Provide exactly 3 options, each targeting 3-12 words; rewrite any option over 16 words, and keep each related to the commitment
6. Options should present real trade-offs{transition_requirement}

[Output Format]
Return JSON:
{{
  "event_description": "Event description ({length_requirement})",
  "options": [
    {{"text": "Option text (target 3-12 words)", "effects": {{"energy": -10, "mood": 5, ...}}{transition_json}}},
    ...
  ]
}}

Return ONLY JSON, no other text."""

    def _generate_simple_scheduled_event(
        self,
        scheduled_events: list[Dict[str, Any]],
        player_state: Any,
    ) -> GameEvent:
        """生成一个简单的预定事件（当AI生成失败时的后备方案）。"""
        # 合并描述
        descriptions = [se.get("description", "") for se in scheduled_events]
        combined_desc = "；".join(descriptions)

        language = self.language
        state_dict = (
            self._prompt_context(player_state) if player_state is not None else {}
        )
        timeline = state_dict.get("timeline")
        first_daily_day = (
            isinstance(timeline, dict) and int(timeline.get("day_index") or 0) == 0
        )

        if language == "zh":
            if first_daily_day:
                from src.ai.prompt_sanitizer import sanitize_persisted_life_vision

                character_settings = state_dict.get("character_settings", {}) or {}
                protagonist = (
                    resolve_protagonist_name(state_dict, character_settings, None)
                    or "主角"
                )
                raw_vision = str(
                    state_dict.get("life_vision")
                    or character_settings.get("life_vision")
                    or "尚待实现的人生方向"
                )
                safe_vision = sanitize_persisted_life_vision(raw_vision)
                vision = " ".join(safe_vision.split())
                vision = vision.translate(str.maketrans("。！？.!?", "，，，，，，"))
                vision = vision.strip("，, ")
                event_desc = (
                    f"{protagonist}仍把“{vision}”放在心上，却先要面对眼前这份必须兑现的承诺。\n\n"
                    f"清晨，{protagonist}站在约定的地点，关于{combined_desc}的现实问题已经摆到面前。"
                )
            else:
                event_desc = f"到了兑现承诺的时候了。{combined_desc}。你需要做出选择。"
            options = [
                EventOption(text="认真兑现承诺", effects={"mood": 10, "energy": -10}),
                EventOption(text="敷衍了事", effects={"mood": -5}),
                EventOption(text="找借口推迟", effects={"mood": -15}),
            ]
        else:
            if first_daily_day:
                from src.ai.prompt_sanitizer import sanitize_persisted_life_vision

                character_settings = state_dict.get("character_settings", {}) or {}
                protagonist = (
                    resolve_protagonist_name(state_dict, character_settings, None)
                    or "The protagonist"
                )
                raw_vision = str(
                    state_dict.get("life_vision")
                    or character_settings.get("life_vision")
                    or "an unrealized direction"
                )
                safe_vision = sanitize_persisted_life_vision(raw_vision)
                vision = " ".join(safe_vision.split())
                vision = vision.translate(str.maketrans("。！？.!?", ",,,,,,"))
                vision = vision.strip("，, ")
                event_desc = (
                    f'{protagonist} still holds onto "{vision}", yet must first face the commitment waiting in reality.\n\n'
                    f"That morning, {protagonist} stands at the agreed place as {combined_desc} comes due."
                )
            else:
                event_desc = f"It's time to fulfill your commitment. {combined_desc}. You need to make a choice."
            options = [
                EventOption(
                    text="Fulfill the commitment seriously",
                    effects={"mood": 10, "energy": -10},
                ),
                EventOption(text="Do it half-heartedly", effects={"mood": -5}),
                EventOption(text="Make an excuse to delay", effects={"mood": -15}),
            ]

        event = GameEvent(
            event_description=event_desc,
            options=options,
        )
        from src.game.daily_transition import prepare_daily_option_transitions

        event.options = prepare_daily_option_transitions(
            event.options,
            state_dict,
            language=language,
        )
        return event
