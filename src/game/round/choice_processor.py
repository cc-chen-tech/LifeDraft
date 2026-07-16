"""Round choice processing service.

Handles the processing of player choices and post-choice pipeline.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from config.settings import settings
from src.ai.models import GameEvent
from src.ai.vector_store import get_vector_store, is_vector_search_enabled
from src.game.narrative_manager import NarrativeManager
from src.game.continuity_ledger import ContinuityLedger
from src.game.world_model_updater import WorldModelUpdater
from src.game.wealth_ledger import WealthLedger

if TYPE_CHECKING:
    from src.ai.generator import EventGenerator
    from src.game.state import PlayerState
    from src.game.story_service import StoryService

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
        player_state_getter: Callable[[], "PlayerState"],
        ai_generator: "EventGenerator",
        language_getter: Callable[[], str],
        story_service: "StoryService",
        current_event_getter: Callable[[], Optional[GameEvent]],
        current_event_setter: Callable[[Optional[GameEvent]], None],
        result_callback: Optional[Callable[[Dict[str, Any], "PlayerState"], None]] = None,
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
    def player_state(self) -> Optional["PlayerState"]:
        return self._get_player_state()

    @property
    def language(self) -> str:
        return self._get_language()

    @property
    def current_event(self) -> Optional[GameEvent]:
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
        effects_requested = chosen_option.effects
        effects, resource_warnings = self._normalize_effects_for_current_state(effects_requested)

        staged_state = player_state.model_copy(deep=True)
        staged_transaction_id = self._apply_wealth_transaction(
            staged_state,
            requested_delta=effects_requested.get("wealth", effects.get("wealth", 0)),
            reason=chosen_option.text,
        )
        staged_state.update(
            energy=effects.get("energy", 0),
            mood=effects.get("mood", 0),
            knowledge=effects.get("knowledge", 0),
            relationships=effects.get("relationships"),
        )

        # Generate against a staged state. No gameplay mutation is committed until
        # the provider has produced a valid continuation.
        story_continuation = self._generate_story_continuation(
            current_event.event_description,
            chosen_option.text,
            effects,
            stream_callback=stream_callback,
            status_callback=status_callback,
            active_wealth_transaction_id=staged_transaction_id,
            player_state=staged_state,
        )

        self._apply_wealth_transaction(
            player_state,
            requested_delta=effects_requested.get("wealth", effects.get("wealth", 0)),
            reason=chosen_option.text,
        )
        player_state.update(
            energy=effects.get("energy", 0),
            mood=effects.get("mood", 0),
            knowledge=effects.get("knowledge", 0),
            relationships=effects.get("relationships"),
        )
        logger.debug(f"Applied effects: {effects}")

        # 3. Build full story and delegate to shared pipeline
        full_story = current_event.event_description
        if story_continuation:
            full_story += "\n\n" + story_continuation

        return self._post_choice_pipeline(
            event=current_event,
            choice_text=chosen_option.text,
            story_continuation=story_continuation,
            effects=effects,
            effects_requested=effects_requested,
            resource_warnings=resource_warnings,
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
        effects_requested = self._generate_custom_choice_effects(
            current_event.event_description, custom_text
        )
        effects, resource_warnings = self._normalize_effects_for_current_state(effects_requested)

        staged_state = player_state.model_copy(deep=True)
        staged_transaction_id = self._apply_wealth_transaction(
            staged_state,
            requested_delta=effects_requested.get("wealth", effects.get("wealth", 0)),
            reason=custom_text,
        )
        staged_state.update(
            energy=effects.get("energy", 0),
            mood=effects.get("mood", 0),
            knowledge=effects.get("knowledge", 0),
            relationships=effects.get("relationships"),
        )

        # Generate custom-choice prose before committing its staged effects.
        story_continuation = self._generate_story_continuation(
            current_event.event_description,
            custom_text,
            effects,
            stream_callback=stream_callback,
            status_callback=status_callback,
            is_custom=True,
            active_wealth_transaction_id=staged_transaction_id,
            player_state=staged_state,
        )

        self._apply_wealth_transaction(
            player_state,
            requested_delta=effects_requested.get("wealth", effects.get("wealth", 0)),
            reason=custom_text,
        )
        player_state.update(
            energy=effects.get("energy", 0),
            mood=effects.get("mood", 0),
            knowledge=effects.get("knowledge", 0),
            relationships=effects.get("relationships"),
        )
        logger.debug(f"Applied effects from custom choice: {effects}")

        # 4. Build full story and delegate to shared pipeline
        full_story = current_event.event_description
        if story_continuation:
            full_story += "\n\n" + story_continuation

        return self._post_choice_pipeline(
            event=current_event,
            choice_text=custom_text,
            story_continuation=story_continuation,
            effects=effects,
            effects_requested=effects_requested,
            resource_warnings=resource_warnings,
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
        effects_requested: Optional[Dict[str, Any]] = None,
        resource_warnings: Optional[list[Dict[str, Any]]] = None,
        is_custom: bool = False,
        status_callback: Optional[Callable[[str], None]] = None,
        finalize_week_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Shared post-choice processing pipeline for make_round_choice and make_custom_choice.

        Handles: story compression → narrative/world-model updates → save records → advance round → week finalization.
        """
        player_state = self.player_state
        if player_state is None:
            raise ValueError("Player state is not available")

        # 1. Parallel: narrative compression + world extraction + story analyzer
        if status_callback:
            status_callback("compressing")

        pending_storylines = player_state.pending_storylines
        established_facts = player_state.established_facts
        character_habits = player_state.character_habits

        with ThreadPoolExecutor(max_workers=3) as executor:
            narrative_future = executor.submit(
                self.story_service.compress_narrative,
                full_story,
                choice_text,
                pending_storylines,
            )
            world_future = executor.submit(
                self.story_service.extract_world_updates,
                full_story,
                choice_text,
                established_facts,
                character_habits,
            )
            analyzer_future = executor.submit(
                WorldModelUpdater.run_story_analyzer,
                player_state,
                full_story,
                choice_text,
                self.ai_generator.ai_client,
                self.language,
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
        NarrativeManager.process_storyline_updates(
            player_state, compression_result.get("storyline_updates", [])
        )
        NarrativeManager.process_fact_updates(
            player_state, compression_result.get("fact_updates", [])
        )
        NarrativeManager.process_foreshadowing_seeds(
            player_state, compression_result.get("foreshadowing_seeds", [])
        )
        NarrativeManager.process_habit_updates(
            player_state, compression_result.get("habit_updates", [])
        )
        WorldModelUpdater.process_location_updates(
            player_state, compression_result.get("location_updates", [])
        )
        WorldModelUpdater.process_career_updates(
            player_state, compression_result.get("career_updates", [])
        )
        WorldModelUpdater.process_commitment_updates(
            player_state, compression_result.get("commitment_updates", [])
        )

        # ★ 5. 检测并升级过期剧情线（在 storyline + commitment 更新之后执行）
        NarrativeManager.escalate_overdue_storylines(player_state)

        WorldModelUpdater.process_causal_updates(
            player_state, compression_result.get("causal_updates", [])
        )

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
        completed_week = player_state.week
        completed_round = player_state.current_round

        round_record = {
            "week": player_state.week,
            "round": player_state.current_round,
            "summary": summary,
            "event_description": event.event_description,
            "story_continuation": story_continuation,
            "choice": choice_text,
            "effects": effects.copy(),
            "effects_requested": (effects_requested or effects).copy(),
            "resource_warnings": list(resource_warnings or []),
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
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to add story to vector store: {e}")

        decision_record = {
            "week": player_state.week,
            "round": player_state.current_round,
            "event": event.event_description[:200] + "...",
            "choice": choice_text,
            "effects": effects.copy(),
            "effects_requested": (effects_requested or effects).copy(),
            "resource_warnings": list(resource_warnings or []),
            "date_info": date_info,
        }
        if is_custom:
            decision_record["is_custom"] = True
        player_state.decision_history.append(decision_record)

        # P1-7: commit the accepted round to the authoritative ledger only
        # after the result and its source records exist. The stable event ID
        # makes repeated choice delivery idempotent.
        ledger_fact_updates = list(compression_result.get("fact_updates", []))
        for update in compression_result.get("career_updates", []):
            subject = str(update.get("character") or "").strip()
            role = str(update.get("new_role") or "").strip()
            if subject and role:
                employer = str(update.get("employer") or "").strip()
                ledger_fact_updates.append(
                    {
                        "action": "update",
                        "subject": subject,
                        "category": "career",
                        "fact": f"{role}{f'（{employer}）' if employer else ''}",
                    }
                )
        for update in compression_result.get("location_updates", []):
            subject = str(update.get("character") or "").strip()
            location = str(update.get("to") or update.get("location") or "").strip()
            if subject and location:
                ledger_fact_updates.append(
                    {
                        "action": "update",
                        "subject": subject,
                        "category": "location",
                        "fact": location,
                    }
                )
        for update in compression_result.get("commitment_updates", []):
            description = str(update.get("description") or "").strip()
            action = str(update.get("action") or "").strip()
            if not description:
                continue
            ledger_fact_updates.append(
                {
                    "action": "update" if action != "new" else "new",
                    "subject": description,
                    "category": "completed_event" if action == "fulfilled" else "commitment",
                    "fact": (
                        f"承诺已完成：{description}"
                        if action == "fulfilled"
                        else f"承诺状态 {action or 'pending'}：{description}"
                    ),
                }
            )
        for name, change in (effects.get("relationships") or {}).items():
            ledger_fact_updates.append(
                {
                    "action": "update",
                    "subject": str(name),
                    "category": "relationship",
                    "fact": (
                        f"与主角的关系变动 {int(change):+d}，"
                        f"当前亲密度 {player_state.relationships.get(str(name), 50)}"
                    ),
                }
            )

        ledger = ContinuityLedger.from_player_state(player_state)
        ledger.record_committed_event(
            event_id=f"w{completed_week}-r{completed_round}",
            week=completed_week,
            round_number=completed_round,
            date_info=date_info,
            summary=summary,
            choice=choice_text,
            story_text=full_story,
            fact_updates=ledger_fact_updates,
        )
        ledger.persist(player_state)

        # ★ 显示用周数（人类可读，从1开始）
        week_display = f"第{player_state.week + 1}周" if player_state.week is not None else "未知周"
        logger.info(
            f"Saved {'custom ' if is_custom else ''}choice record: {week_display}, round={player_state.current_round}"
        )

        # 6. Clear current event data and last_round_full_story
        logger.info(
            f"[ChoiceProcessor] Clearing current_event_data (before: {player_state.current_event_data is not None}), last_round_full_story (before: {bool(player_state.last_round_full_story)})"
        )
        player_state.current_event_data = None
        # ★ CRITICAL: 清除 last_round_full_story，防止恢复逻辑找到旧故事
        player_state.last_round_full_story = ""
        logger.info(
            f"[ChoiceProcessor] Cleared current_event_data (after: {player_state.current_event_data is not None}), last_round_full_story (after: {bool(player_state.last_round_full_story)})"
        )

        # 7. Advance round and check if week is complete
        need_weekly_summary = player_state.advance_round()

        result = {
            "story_continuation": story_continuation,
            "summary": summary,
            "effects_applied": effects.copy(),
            "effects_requested": (effects_requested or effects).copy(),
            "resource_warnings": list(resource_warnings or []),
            "need_weekly_summary": need_weekly_summary,
        }

        # 8. If week is complete, finalize
        if need_weekly_summary and finalize_week_callback:
            finalize_week_callback(result, status_callback=status_callback)

        # 9. Clean up and check game over
        self._set_current_event(None)
        logger.info(
            f"[ChoiceProcessor] Final cleanup - current_event_data before: {player_state.current_event_data is not None}"
        )
        player_state.current_event_data = None
        logger.info(
            f"[ChoiceProcessor] Final cleanup - current_event_data after: {player_state.current_event_data is not None}"
        )
        result["game_over"] = player_state.is_game_over()

        visible_phase = (
            "ending"
            if result["game_over"]
            else "summary"
            if need_weekly_summary and result.get("weekly_summary")
            else "result"
        )
        player_state.resume_view = {
            "phase": visible_phase,
            "story_text": full_story,
            "round_summary": summary,
            "summary_text": (
                result.get("weekly_summary", "") if visible_phase == "summary" else ""
            ),
            "resource_warnings": list(resource_warnings or []),
            "completed_week": completed_week,
            "completed_round": completed_round,
        }

        if self.result_callback:
            self.result_callback(result, player_state)

        return result

    def _normalize_effects_for_current_state(
        self, effects: Dict[str, Any]
    ) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
        """Return actual deltas after resource bounds plus warning metadata."""
        player_state = self.player_state
        if player_state is None:
            return effects.copy(), []

        normalized = effects.copy()
        warnings: list[Dict[str, Any]] = []

        bounded_resources = {
            "energy": (player_state.energy, settings.MIN_RESOURCE, settings.MAX_RESOURCE, "精力"),
            "mood": (player_state.mood, settings.MIN_RESOURCE, settings.MAX_RESOURCE, "情绪"),
            "knowledge": (
                player_state.knowledge,
                settings.MIN_RESOURCE,
                settings.MAX_RESOURCE,
                "学识",
            ),
            "wealth": (player_state.wealth, 0, None, "财富"),
        }

        for resource, (current_value, min_value, max_value, display_name) in bounded_resources.items():
            requested_delta = effects.get(resource)
            if not isinstance(requested_delta, int):
                continue

            raw_next_value = current_value + requested_delta
            clamped_next_value = max(min_value, raw_next_value)
            if max_value is not None:
                clamped_next_value = min(max_value, clamped_next_value)

            actual_delta = clamped_next_value - current_value
            normalized[resource] = actual_delta

            if actual_delta != requested_delta:
                direction = "insufficient_resource" if requested_delta < 0 else "resource_cap"
                message = (
                    f"{display_name}不足，实际变化为 {actual_delta:+d}"
                    if direction == "insufficient_resource"
                    else f"{display_name}已接近上限，实际变化为 {actual_delta:+d}"
                )
                warnings.append(
                    {
                        "resource": resource,
                        "display_name": display_name,
                        "reason": direction,
                        "current": current_value,
                        "requested_delta": requested_delta,
                        "applied_delta": actual_delta,
                        "message": message,
                    }
                )

        return normalized, warnings

    def _generate_custom_choice_effects(
        self, event_description: str, custom_text: str
    ) -> Dict[str, Any]:
        """用 AI 生成自定义选择的属性变化。委托给 StoryService。"""
        player_state = self.player_state
        character_settings = player_state.character_settings if player_state else {}
        current_state = player_state.to_dict() if player_state else {}
        return self.story_service.generate_custom_choice_effects(
            event_description, custom_text, character_settings, current_state
        )

    def _generate_custom_choice_result(
        self, event_description: str, custom_text: str
    ) -> Dict[str, Any]:
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
        is_custom: bool = False,
        active_wealth_transaction_id: Optional[str] = None,
        player_state: Optional["PlayerState"] = None,
    ) -> str:
        """Generate a detailed story continuation. Delegates to StoryService."""
        effective_state = player_state or self.player_state
        character_settings = effective_state.character_settings if effective_state else {}
        player_state_dict = effective_state.to_dict() if effective_state else {}
        if active_wealth_transaction_id:
            player_state_dict["_active_wealth_transaction_id"] = (
                active_wealth_transaction_id
            )
        return self.story_service.generate_story_continuation(
            event_description,
            chosen_option,
            effects,
            character_settings,
            player_state=player_state_dict,
            stream_callback=stream_callback,
            status_callback=status_callback,
            is_custom=is_custom,
            active_wealth_transaction_id=active_wealth_transaction_id,
        )

    def _apply_wealth_transaction(
        self,
        player_state: "PlayerState",
        *,
        requested_delta: Any,
        reason: str,
    ) -> Optional[str]:
        if not isinstance(requested_delta, int) or isinstance(requested_delta, bool):
            requested_delta = 0
        ledger = WealthLedger.from_player_state(player_state)
        if requested_delta == 0:
            ledger.persist(player_state)
            return None
        source_event_id = f"w{player_state.week}-r{player_state.current_round}"
        transaction_id = f"choice:{source_event_id}"
        ledger.apply_transaction(
            player_state,
            transaction_id=transaction_id,
            requested_delta=requested_delta,
            reason=reason,
            source_event_id=source_event_id,
            week=player_state.week,
            round_number=player_state.current_round,
        )
        return transaction_id
