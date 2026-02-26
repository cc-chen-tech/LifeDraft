"""Round choice processing service.

Handles the processing of player choices and post-choice pipeline.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, Optional

from src.ai.models import GameEvent
from src.ai.vector_store import get_vector_store, is_vector_search_enabled
from src.game.narrative_manager import NarrativeManager
from src.game.world_model_updater import WorldModelUpdater

logger = logging.getLogger(__name__)


class RoundChoiceProcessor:
    """Service for processing round choices.
    
    This service handles:
    - Standard option selection
    - Custom choice processing
    - Post-choice pipeline execution
    - Story compression and world updates
    """
    
    def __init__(
        self,
        player_state_getter: callable,
        ai_generator: Any,
        language_getter: callable,
        story_service: Any,
        current_event_getter: callable,
        current_event_setter: callable,
        result_callback: Optional[Callable] = None,
    ):
        """
        Args:
            player_state_getter: Function that returns current player state
            ai_generator: EventGenerator instance
            language_getter: Function that returns current language
            story_service: StoryService instance
            current_event_getter: Function that returns current event
            current_event_setter: Function to set current event
            result_callback: Optional callback when result is ready
        """
        self._get_player_state = player_state_getter
        self.ai_generator = ai_generator
        self._get_language = language_getter
        self.story_service = story_service
        self._get_current_event = current_event_getter
        self._set_current_event = current_event_setter
        self.result_callback = result_callback
    
    @property
    def player_state(self):
        return self._get_player_state()
    
    @property
    def language(self):
        return self._get_language()
    
    @property
    def current_event(self):
        return self._get_current_event()
    
    def make_round_choice(
        self,
        option_index: int,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        finalize_week_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Process a player's choice for the current round.
        Updates attributes, generates story continuation, and handles round/week transitions.
        
        Args:
            option_index: Index of the chosen option (0-based)
            stream_callback: Optional callback for streaming story continuation text
            status_callback: Optional callback for reporting processing status
            finalize_week_callback: Optional callback for week finalization
        
        Returns:
            Dictionary with story_continuation, summary, effects_applied, need_weekly_summary, etc.
        """
        player_state = self.player_state
        if not player_state:
            raise ValueError("Game not started.")
        
        current_event = self.current_event
        if not current_event:
            raise ValueError("No current event. Generate a round event first.")
        
        # Save reference to current event at the start
        if option_index < 0 or option_index >= len(current_event.options):
            raise ValueError(f"Invalid option index: {option_index}")
        
        chosen_option = current_event.options[option_index]
        effects = chosen_option.effects
        
        # 1. Apply effects immediately (real-time update)
        player_state.update(
            energy=effects.get("energy", 0),
            mood=effects.get("mood", 0),
            knowledge=effects.get("knowledge", 0),
            wealth=effects.get("wealth", 0),
            relationships=effects.get("relationships")
        )
        
        logger.debug(f"Applied effects: {effects}")
        
        # 2. Generate story continuation
        story_continuation = self._generate_story_continuation(
            current_event.event_description,
            chosen_option.text,
            effects,
            stream_callback=stream_callback,
            status_callback=status_callback,
        )
        
        # 3. Build full story and delegate to shared pipeline
        full_story = current_event.event_description
        if story_continuation:
            full_story += "\n\n" + story_continuation
        
        return self._post_choice_pipeline(
            event=current_event,
            choice_text=chosen_option.text,
            story_continuation=story_continuation,
            effects=effects,
            full_story=full_story,
            status_callback=status_callback,
            finalize_week_callback=finalize_week_callback,
        )

    def make_custom_choice(
        self,
        custom_text: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        finalize_week_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        处理用户自定义的选择。
        AI 会根据用户输入生成合理的结果和属性变化。
        
        Args:
            custom_text: 用户自定义的选择文本
            stream_callback: Optional callback for streaming story continuation text
            status_callback: Optional callback for reporting processing status
            finalize_week_callback: Optional callback for week finalization
        
        Returns:
            Dictionary with story_continuation, summary, effects_applied, need_weekly_summary, etc.
        """
        player_state = self.player_state
        if not player_state:
            raise ValueError("Game not started.")
        
        current_event = self.current_event
        if not current_event:
            raise ValueError("No current event. Generate a round event first.")
        
        logger.info(f"Processing custom choice: {custom_text[:50]}...")
        
        # 1. 调用 AI 生成自定义选择的属性变化（快速 JSON 调用）
        effects = self._generate_custom_choice_effects(current_event.event_description, custom_text)
        
        # 2. 应用属性变化
        player_state.update(
            energy=effects.get("energy", 0),
            mood=effects.get("mood", 0),
            knowledge=effects.get("knowledge", 0),
            wealth=effects.get("wealth", 0),
            relationships=effects.get("relationships")
        )
        
        logger.debug(f"Applied effects from custom choice: {effects}")
        
        # 3. 生成故事续写（流式输出）
        story_continuation = self._generate_story_continuation(
            current_event.event_description,
            custom_text,
            effects,
            stream_callback=stream_callback,
            status_callback=status_callback,
        )
        
        # 4. Build full story and delegate to shared pipeline
        full_story = current_event.event_description
        if story_continuation:
            full_story += "\n\n" + story_continuation
        
        return self._post_choice_pipeline(
            event=current_event,
            choice_text=custom_text,
            story_continuation=story_continuation,
            effects=effects,
            full_story=full_story,
            is_custom=True,
            status_callback=status_callback,
            finalize_week_callback=finalize_week_callback,
        )

    def _post_choice_pipeline(
        self,
        event: GameEvent,
        choice_text: str,
        story_continuation: str,
        effects: Dict[str, Any],
        full_story: str,
        is_custom: bool = False,
        status_callback: Optional[Callable[[str], None]] = None,
        finalize_week_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Shared post-choice processing pipeline for make_round_choice and make_custom_choice.
        
        Handles: story compression → narrative/world-model updates → save records → advance round → week finalization.
        """
        player_state = self.player_state
        
        # 1. Parallel: narrative compression + world extraction + story analyzer
        if status_callback:
            status_callback("compressing")

        pending_storylines = player_state.pending_storylines if player_state else []
        established_facts = player_state.established_facts if player_state else []
        character_habits = player_state.character_habits if player_state else []

        with ThreadPoolExecutor(max_workers=3) as executor:
            narrative_future = executor.submit(
                self.story_service.compress_narrative,
                full_story, choice_text, pending_storylines
            )
            world_future = executor.submit(
                self.story_service.extract_world_updates,
                full_story, choice_text, established_facts, character_habits
            )
            analyzer_future = executor.submit(
                WorldModelUpdater.run_story_analyzer,
                player_state, full_story, choice_text,
                self.ai_generator.ai_client, self.language
            )
            # Wait for all to complete
            narrative_result = narrative_future.result()
            world_result = world_future.result()
            analyzer_future.result()  # side-effect only

        # Merge results
        compression_result = {**narrative_result, **world_result}
        summary = compression_result["summary"]

        # 2. Store event conclusion status
        event_concluded = compression_result.get("event_concluded", True)
        player_state.last_event_concluded = event_concluded

        # 3. Build structured full story
        structured_full_story = event.event_description
        if story_continuation:
            choice_marker = (
                f"\n\n--- 主角选择了：{choice_text} ---\n\n"
                if self.language == "zh"
                else f"\n\n--- Player chose: {choice_text} ---\n\n"
            )
            structured_full_story += choice_marker + story_continuation
        player_state.last_round_full_story = structured_full_story
        logger.info(f"Event concluded: {event_concluded}, full story length: {len(full_story)}")

        # 4. Process narrative & world-model updates
        NarrativeManager.process_storyline_updates(player_state, compression_result.get("storyline_updates", []))
        NarrativeManager.process_fact_updates(player_state, compression_result.get("fact_updates", []))
        NarrativeManager.process_foreshadowing_seeds(player_state, compression_result.get("foreshadowing_seeds", []))
        NarrativeManager.process_habit_updates(player_state, compression_result.get("habit_updates", []))
        WorldModelUpdater.process_location_updates(player_state, compression_result.get("location_updates", []))
        WorldModelUpdater.process_career_updates(player_state, compression_result.get("career_updates", []))
        WorldModelUpdater.process_commitment_updates(player_state, compression_result.get("commitment_updates", []))
        WorldModelUpdater.process_causal_updates(player_state, compression_result.get("causal_updates", []))

        # 4.5 Sync story characters to character_settings
        # This handles characters that AI introduced in the story without going through
        # the formal character introduction mechanism
        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=full_story,
            relationships_in_effects=effects.get("relationships"),
        )

        # 5. Save records
        date_info = player_state.get_game_date_info()

        round_record = {
            "week": player_state.week,
            "round": player_state.current_round,
            "summary": summary,
            "event_description": event.event_description,
            "story_continuation": story_continuation,
            "choice": choice_text,
            "effects": effects.copy(),
            "date_info": date_info,
            "event_concluded": event_concluded,
        }
        if is_custom:
            round_record["is_custom"] = True
        player_state.round_history.append(round_record)

        story_entry = {
            "week": player_state.week,
            "round": player_state.current_round,
            "story": event.event_description,
            "choice": choice_text,
            "continuation": story_continuation,
            "date_info": date_info,
        }
        if is_custom:
            story_entry["is_custom"] = True
        player_state.story_history.append(story_entry)

        # ★ 向量存储：将故事存入向量库以支持语义检索
        if is_vector_search_enabled():
            try:
                vector_store = get_vector_store()
                story_id = f"week{player_state.week}_round{player_state.current_round}"
                full_story_text = event.event_description
                if story_continuation:
                    full_story_text += f"\n\n[选择: {choice_text}]\n\n{story_continuation}"
                vector_store.add_story(
                    story_id=story_id,
                    content=full_story_text,
                    metadata={
                        "week": player_state.week,
                        "round": player_state.current_round,
                        "choice": choice_text[:100],  # 截断防止过长
                        "is_custom": is_custom,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to add story to vector store: {e}")

        decision_record = {
            "week": player_state.week,
            "round": player_state.current_round,
            "event": event.event_description[:200] + "...",
            "choice": choice_text,
            "effects": effects.copy(),
            "date_info": date_info,
        }
        if is_custom:
            decision_record["is_custom"] = True
        player_state.decision_history.append(decision_record)

        logger.info(f"Saved {'custom ' if is_custom else ''}choice record: week={player_state.week}, round={player_state.current_round}")

        # 6. Clear current event data
        player_state.current_event_data = None

        # 7. Advance round and check if week is complete
        need_weekly_summary = player_state.advance_round()

        result = {
            "story_continuation": story_continuation,
            "summary": summary,
            "effects_applied": effects.copy(),
            "need_weekly_summary": need_weekly_summary,
        }

        # 8. If week is complete, finalize
        if need_weekly_summary and finalize_week_callback:
            finalize_week_callback(result, status_callback=status_callback)

        # 9. Clean up and check game over
        self._set_current_event(None)
        player_state.current_event_data = None
        result["game_over"] = player_state.is_game_over()

        if self.result_callback:
            self.result_callback(result, player_state)

        return result

    def _generate_custom_choice_effects(self, event_description: str, custom_text: str) -> Dict[str, Any]:
        """用 AI 生成自定义选择的属性变化。委托给 StoryService。"""
        player_state = self.player_state
        character_settings = player_state.character_settings if player_state else {}
        current_state = player_state.to_dict() if player_state else {}
        return self.story_service.generate_custom_choice_effects(
            event_description, custom_text, character_settings, current_state
        )

    def _generate_custom_choice_result(self, event_description: str, custom_text: str) -> Dict[str, Any]:
        """用 AI 生成自定义选择的结果。委托给 StoryService。"""
        player_state = self.player_state
        character_settings = player_state.character_settings if player_state else {}
        current_state = player_state.to_dict() if player_state else {}
        return self.story_service.generate_custom_choice_result(
            event_description, custom_text, character_settings, current_state
        )

    def _generate_story_continuation(
        self,
        event_description: str,
        chosen_option: str,
        effects: Dict[str, Any],
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Generate a detailed story continuation. Delegates to StoryService."""
        player_state = self.player_state
        character_settings = player_state.character_settings if player_state else {}
        player_state_dict = player_state.to_dict() if player_state else {}
        return self.story_service.generate_story_continuation(
            event_description, chosen_option, effects, character_settings,
            player_state=player_state_dict,
            stream_callback=stream_callback,
            status_callback=status_callback,
        )
