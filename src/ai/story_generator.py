"""Story generation service.

Handles the core story text generation (Step 1 of the two-stage pipeline),
consistency validation with retry, and life-phase determination.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from difflib import SequenceMatcher
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union, cast

from pydantic import ValidationError

from config.prompts import get_round_event_prompt, get_story_only_prompt
from config.prompts._helpers import (
    _build_style_constraints_text,
    extract_overused_phrases,
)
from config.prompts.story_prompts import (
    build_daily_story_mode_constraint,
    resolve_protagonist_name,
)
from src.ai.budgets import (
    GenerationBudgetError,
    GenerationCallTracker,
    GenerationOperation,
    NarrativeBudget,
    NarrativeKind,
    measure_narrative_length,
    resolve_narrative_budget,
)
from src.ai.client import AIClient
from src.ai.harness.diagnostics import ConstraintViolationDiagnostic
from src.ai.harness.validation_pipeline import ValidationPipeline
from src.ai.harness.retry_controller import RetryController
from src.ai.harness.quality_level import PROFILES, QualityLevel
from src.ai.long_story_context import (
    DynamicContextParts,
    LongStoryContextBuilder,
    is_deepseek_v4_model,
    prepend_history_prefix,
)
from src.ai.generation_budget import get_daily_generation_budget, get_generation_budget
from src.ai.models import GameEvent, StoryDeliveryNotice
from src.ai.option_generator import OptionGenerator
from src.ai.prompt_sanitizer import sanitize_persisted_player_name
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_validation import (
    FindingSeverity,
    ValidationFinding,
    findings_from_legacy,
)
from src.ai.system_prompts import get_system_prompt
from src.ai.text_quality import normalize_generated_story, validate_narrative_quality

if TYPE_CHECKING:
    from src.ai.cache import EventCache
    from src.ai.quick_validator import QuickValidationResult
    from src.game.world_model import WorldModel

logger = logging.getLogger(__name__)


_TERMINAL_CONTINUITY_CONSTRAINTS = frozenset(
    {
        "available_people",
        "established_facts",
        "world_model_position",
        "world_model_commitment",
        "no_fabrication",
        "era_consistency",
        "temporal_consistency",
        "commitment_fulfillment",
        "character_state_continuity",
        "item_continuity",
        "spatial_movement",
        "npc_attribute_stability",
        "information_barrier",
        "cause_effect_consistency",
    }
)


def _localized_story_shape_issues(
    candidate: str,
    *,
    language: str,
    target_min: int,
    target_max: int,
    use_localized_measurement: bool,
) -> list[str]:
    """Validate narrative shape without treating English characters as words."""
    if not use_localized_measurement:
        return validate_narrative_quality(
            candidate,
            language=language,
            perspective="third",
            min_chars=target_min,
            max_chars=target_max,
        )

    issues = validate_narrative_quality(
        candidate,
        language=language,
        perspective="third",
    )
    measured_length = measure_narrative_length(candidate, language)
    if measured_length < target_min:
        issues.append("story_too_short")
    if measured_length > target_max:
        issues.append("story_too_long")
    return issues


class _EmptyStoryProviderOutput(ValueError):
    """A round-prose provider call returned no normalized text."""


class StoryGenerator:
    """Generates story text for events and rounds."""

    def __init__(
        self,
        client: AIClient,
        quality_level: Optional[Union[QualityLevel, str]] = None,
    ):
        self.client = client
        self.quality_level = QualityLevel(quality_level or QualityLevel.EXPERT)
        self._quality_profile = PROFILES[self.quality_level]
        self._harness_enabled = self._env_enabled("ENABLE_CONSTRAINT_HARNESS")
        self._soft_narrative_lengths = self._env_enabled(
            "ENABLE_SOFT_NARRATIVE_LENGTHS"
        )
        self._unified_narrative_budgets = self._env_enabled(
            "ENABLE_UNIFIED_NARRATIVE_BUDGETS"
        )
        self._narrative_systems_initialized = False
        self._validation_pipeline: Optional[ValidationPipeline] = None
        self._retry_controller: Optional[RetryController] = None
        self._diagnostics: Optional[ConstraintViolationDiagnostic] = None
        self._harness_metrics: Optional[Any] = None
        self._style_manifest: Optional[Any] = None
        self._prompt_builder: Optional[Any] = None
        self._style_validator: Optional[Any] = None
        self._initialized_style_id: Optional[str] = None

    @staticmethod
    def _normalize_punctuation(
        text: Optional[str], language: str = "zh"
    ) -> Optional[str]:
        """Backward-compatible punctuation normalization helper used by contract tests."""
        if text is None or language != "zh":
            return text
        if not text:
            return text

        converted_quotes = []
        quote_open = True
        for char in text:
            if char == '"':
                converted_quotes.append("“" if quote_open else "”")
                quote_open = not quote_open
            else:
                converted_quotes.append(char)

        normalized = normalize_generated_story(
            "".join(converted_quotes), language=language
        )

        # Convert remaining ASCII punctuation artifacts used by legacy contract expectations.
        normalized = normalized.replace("(", "（").replace(")", "）")

        converted_chars = []
        quote_open = True
        for char in normalized:
            if char == '"':
                converted_chars.append("“" if quote_open else "”")
                quote_open = not quote_open
            else:
                converted_chars.append(char)
        normalized = "".join(converted_chars)

        # Preserve existing conversion semantics for commas, periods, question marks and spaces.
        normalized = (
            normalized.replace(".", "。")
            .replace("?", "？")
            .replace("!", "！")
            .replace(",", "，")
        )
        normalized = (
            normalized.replace("；", "；").replace(":", "：").replace(";", "；")
        )

        return normalized

    @staticmethod
    def _resolve_temperature(
        attempt: int,
        base_temperature: float,
        decay: float,
        *,
        min_temperature: float = 0.7,
    ) -> float:
        """Compute retry temperature with floor.

        Keep one-decimal precision for stable contract checks and easier test
        assertions while preserving exact numeric behavior in runtime.
        """
        if attempt <= 0:
            return base_temperature
        return max(min_temperature, base_temperature - attempt * decay)

    def _story_request_timeout_seconds(
        self,
        narrative_budget: Optional[NarrativeBudget] = None,
        generation_tracker: Optional[GenerationCallTracker] = None,
    ) -> float:
        """Keep interactive story requests inside the selected quality budget."""
        if generation_tracker is not None:
            fallback = float(
                get_generation_budget(self.quality_level.value).expected_seconds + 30
            )
            return float(generation_tracker.cap_timeout(fallback) or fallback)
        if narrative_budget is not None and narrative_budget.total_deadline_seconds is not None:
            return float(narrative_budget.total_deadline_seconds)
        budget = get_generation_budget(self.quality_level.value)
        return float(budget.expected_seconds + 30)

    def _call_required_round_story(
        self,
        *,
        language: str,
        generation_tracker: Optional[GenerationCallTracker] = None,
        **call_kwargs: Any,
    ) -> str:
        """Generate required round prose in non-thinking mode and reject blanks."""
        if generation_tracker is not None:
            generation_tracker.consume("prose")
        provider_story = self.client.call(
            thinking=False,
            generation_tracker=generation_tracker,
            **call_kwargs,
        )
        story_text = normalize_generated_story(
            provider_story or "",
            language=language,
        )
        if not story_text.strip():
            raise _EmptyStoryProviderOutput("Story provider returned empty text")
        return story_text

    @staticmethod
    def _extract_player_name(player_state: Optional[Dict[str, Any]]) -> str:
        """Resolve and sanitize player name from player state.

        Keep a dedicated helper for test coverage and for other callers that
        need a consistent sanitization policy.
        """
        player_state = player_state or {}
        name = resolve_protagonist_name(
            player_state, player_state.get("character_settings"), None
        )
        return sanitize_persisted_player_name(name)

    @staticmethod
    def _validation_people_names(
        player_state: Optional[Dict[str, Any]],
        character_settings: Optional[Dict[str, Any]],
    ) -> list[str]:
        """Return the canonical cast plus protagonist for local story validation."""
        from config.prompts._helpers import _collect_available_people

        names = [
            str(person.get("name") or "").strip()
            for person in _collect_available_people(character_settings)
            if str(person.get("name") or "").strip()
        ]
        protagonist_name = resolve_protagonist_name(
            player_state or {}, character_settings, None
        )
        if protagonist_name and protagonist_name not in names:
            names.append(protagonist_name)
        return names

    @staticmethod
    def _canonical_story_for_repeat_check(story: str) -> str:
        """Normalize prose for a semantic duplicate check without changing stored text."""
        return re.sub(r"\s+", "", (story or "").replace("\r\n", "\n"))

    @classmethod
    def _repeats_committed_story(
        cls, candidate: str, committed_stories: list[str]
    ) -> bool:
        """Return whether a substantial candidate duplicates a committed round story."""
        canonical_candidate = cls._canonical_story_for_repeat_check(candidate)
        if len(canonical_candidate) < 160:
            return False

        for committed_story in committed_stories:
            canonical_committed = cls._canonical_story_for_repeat_check(committed_story)
            if len(canonical_committed) < 160:
                continue
            if canonical_candidate == canonical_committed:
                return True
            if min(len(canonical_candidate), len(canonical_committed)) < 240:
                continue
            similarity = SequenceMatcher(
                None,
                canonical_candidate,
                canonical_committed,
                autojunk=False,
            ).ratio()
            if similarity >= 0.92:
                return True
        return False

    @staticmethod
    def _committed_round_stories(
        player_state: Dict[str, Any],
        last_round_full_story: str,
    ) -> list[str]:
        """Collect only persisted story prose, not summaries or pending stream chunks."""
        stories: list[str] = []
        if last_round_full_story:
            stories.append(last_round_full_story)

        for entry in player_state.get("round_history", []) or []:
            if not isinstance(entry, dict):
                continue
            for field in ("event_description", "story_text", "full_story"):
                value = entry.get(field)
                if isinstance(value, str) and value:
                    stories.append(value)
                    break

        for entry in player_state.get("decision_history", []) or []:
            if not isinstance(entry, dict):
                continue
            for field in ("event", "event_description", "story_text", "full_story"):
                value = entry.get(field)
                if isinstance(value, str) and value:
                    stories.append(value)
                    break
        return stories

    def _long_history_prefix(
        self, player_state: Dict[str, Any], dynamic_tail: str = ""
    ) -> str:
        """Return cache-stable history only when the active model supports it."""
        model = getattr(self.client, "model", None)
        if not is_deepseek_v4_model(model):
            logger.info("Long story context disabled for model=%s", model or "unknown")
            return ""
        builder = LongStoryContextBuilder()
        context = (
            builder.build_for_request(
                player_state,
                DynamicContextParts(current_request=dynamic_tail),
            )
            if dynamic_tail
            else builder.build(player_state)
        )
        logger.info("Long story context: %d tokens", context.input_tokens)
        return context.history_prefix

    # -------------------- Public API --------------------

    def generate_event(
        self,
        player_state: Dict[str, Any],
        language: str = "en",
        retry_count: int = 3,
        character_settings: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        four_week_summary: Optional[str] = None,
        yearly_summary: Optional[str] = None,
        opening_story: Optional[str] = None,
        last_event_description: Optional[str] = None,
        game_date_info: Optional[Dict[str, Any]] = None,
        pending_storylines: Optional[list[Any]] = None,
        established_facts: Optional[list[Any]] = None,
        last_event_concluded: bool = True,
        last_round_full_story: str = "",
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
        character_habits: Optional[list[Any]] = None,
        option_generator: Optional[OptionGenerator] = None,
        cache: Optional[EventCache] = None,
        status_callback: Optional[Callable[[Any], None]] = None,
        narrative_budget: Optional[NarrativeBudget] = None,
        generation_tracker: Optional[GenerationCallTracker] = None,
    ) -> GameEvent:
        """
        Generate a game event (story + options) based on player state.

        Two-stage pipeline:
          Step 1: Generate pure story text (this class)
          Step 2: Generate options based on the story (OptionGenerator)

        Args:
            player_state: Current player state dictionary
            language: Language code ('en' or 'zh')
            retry_count: Number of retries on failure
            character_settings: Optional character settings
            stream_callback: Optional streaming callback
            four_week_summary: Recent 4-week summary for context
            yearly_summary: Yearly summary for context
            opening_story: Opening story text for continuity
            last_event_description: Last event description for continuity
            game_date_info: Game-internal date info
            pending_storylines: Pending storylines for continuity
            established_facts: Established world facts for consistency
            last_event_concluded: Whether last event was concluded
            last_round_full_story: Full story of last round
            activated_foreshadowing: Activated foreshadowing seed
            character_habits: Character habits for behavioral consistency
            option_generator: OptionGenerator instance for Step 2
            cache: EventCache instance for caching results

        Returns:
            GameEvent object

        Raises:
            ValueError: If generation fails after retries
        """
        if self._unified_narrative_budgets or narrative_budget is not None:
            narrative_budget = narrative_budget or resolve_narrative_budget(
                NarrativeKind.ROUND,
                GenerationOperation.GENERATE,
                self.quality_level.value,
                language,
            )
            generation_tracker = generation_tracker or GenerationCallTracker(
                narrative_budget
            )
            retry_count = min(retry_count, narrative_budget.prose_call_limit)

        style_id = str(
            player_state.get("narrative_style_id")
            or (character_settings or {}).get("narrative_style_id")
            or ""
        )
        self._init_narrative_systems(style_id, player_state)
        style_constraints = _build_style_constraints_text(
            self._prompt_builder, language
        )

        current_phase = self._get_phase_from_state(player_state)

        # Derive last_event_description from decision history if not provided
        if not last_event_description:
            decision_history = player_state.get("decision_history", [])
            if decision_history:
                last_event_description = decision_history[-1].get("event")

        # ★ 动态提取历史故事中的高频重复短语，生成禁用列表
        decision_history = player_state.get("decision_history", [])
        overused_phrases = extract_overused_phrases(decision_history, language=language)
        if overused_phrases:
            logger.info(
                f"[AntiRepeat] Injected dynamic ban list ({len(overused_phrases)} chars)"
            )

        world_model = self._build_world_model_from_state_dict(player_state)
        if world_model is not None:
            established_facts = getattr(
                world_model,
                "hard_established_facts",
                established_facts,
            )

        story_prompt = get_story_only_prompt(
            player_state,
            language,
            current_phase,
            character_settings,
            opening_story,
            last_event_description,
            four_week_summary,
            yearly_summary,
            game_date_info,
            pending_storylines,
            established_facts,
            last_event_concluded,
            last_round_full_story,
            activated_foreshadowing,
            character_habits,
            world_model=world_model,
            overused_phrases=overused_phrases,  # ★ 注入动态禁用列表
            style_constraints=style_constraints,
            quality_level=self.quality_level.value,
        )
        sys_prompt = get_system_prompt("story_novelist", language)
        history_prefix = self._long_history_prefix(
            player_state, sys_prompt + story_prompt
        )
        story_prompt = prepend_history_prefix(history_prefix, story_prompt)
        last_error: Optional[str] = None

        # ★ 优化：使用渐进式温度策略
        # - 初次生成：0.85 (平衡创意性与准确性)
        # - 第一次重试：0.75 (更保守)
        # - 第二次重试：0.7 (最保守，确保符合约束)
        base_temperature = 0.85
        temperature_decay = 0.15  # 每次重试降低 0.15

        for attempt in range(retry_count):
            try:
                # Step 1: Generate story text (pure narrative, no JSON)
                prompt = story_prompt
                if attempt > 0 and last_error:
                    if language == "zh":
                        prompt += f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题。】"
                    else:
                        prompt += f"\n\n[Previous attempt failed: {last_error}. Please avoid the same issue.]"

                # 计算当前温度：随着重试次数递减
                current_temp = max(
                    0.7, base_temperature - (attempt * temperature_decay)
                )
                logger.info(
                    f"Story generation attempt {attempt + 1}/{retry_count}, temperature={current_temp}"
                )

                # Only stream on first attempt
                cb = stream_callback if attempt == 0 else None
                if generation_tracker is not None:
                    generation_tracker.consume("prose")
                story_text = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=prompt,
                    temperature=current_temp,  # ★ 动态调整温度
                    max_tokens=(
                        narrative_budget.max_output_tokens
                        if narrative_budget is not None
                        else get_generation_budget(self.quality_level.value).max_tokens
                    ),
                    stream_callback=cb,
                    frequency_penalty=0.3,  # ★ 惩罚重复词汇，减少车轲辘话
                    presence_penalty=0.3,  # ★ 鼓励使用新词汇/新主题
                    request_timeout=self._story_request_timeout_seconds(
                        narrative_budget, generation_tracker
                    ),
                    generation_tracker=generation_tracker,
                )

                story_text = normalize_generated_story(story_text, language=language)
                logger.info(f"Generated story with {len(story_text)} characters")
                logger.debug(f"Story preview (first 200 chars): {story_text[:200]}...")
                logger.debug(f"Story preview (last 200 chars): ...{story_text[-200:]}")

                from src.ai.quick_validator import quick_validate_story

                available_people_names = self._validation_people_names(
                    player_state, character_settings
                )
                quick_result = quick_validate_story(
                    story_text=story_text,
                    character_settings=character_settings,
                    available_people=available_people_names,
                    language=language,
                )
                if not quick_result.passed:
                    raise ValueError("; ".join(quick_result.issues))

                # Step 2: Generate options based on the story
                if option_generator is None:
                    raise ValueError("option_generator is required")

                if status_callback:
                    status_callback("generating_options")

                logger.info("Step 2: Generating options based on the story...")
                event = option_generator.generate_options_only(
                    story_description=story_text,
                    player_state=player_state,
                    character_settings=character_settings,
                    language=language,
                    retry_count=retry_count,
                    history_prefix=history_prefix,
                    generation_tracker=generation_tracker,
                )
                logger.info(f"Generated {len(event.options)} options")
                for i, opt in enumerate(event.options):
                    logger.info(f"Option {i+1}: {opt.text}")

                # Validate and fix relationship names
                option_generator.validate_and_fix_relationships(
                    event, character_settings
                )

                # Validate event quality
                option_generator.validate_event_quality(event)
                option_generator.ensure_options_consistency(
                    event=event,
                    story_description=story_text,
                    available_people=available_people_names,
                    language=language,
                )

                # Cache the event
                if cache:
                    cache.set(player_state, language, event)

                logger.info(
                    f"Successfully generated event with {len(event.options)} options"
                )
                return event

            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == retry_count - 1:
                    raise ValueError(
                        f"Failed to generate valid event after {retry_count} attempts: {e}"
                    )
                continue

            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error during event generation: {e}")
                if attempt == retry_count - 1:
                    raise ValueError(f"Event generation failed: {e}")
                continue

        raise ValueError("Event generation failed after all retries")

    def generate_round_event(
        self,
        player_state: Dict[str, Any],
        language: str,
        round_number: int,
        round_context: str,
        character_settings: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        relationship_events: Optional[list[Any]] = None,
        historical_weekly_summary: Optional[str] = None,
        historical_yearly_summary: Optional[str] = None,
        game_date_info: Optional[Dict[str, Any]] = None,
        pending_storylines: Optional[list[Any]] = None,
        established_facts: Optional[list[Any]] = None,
        last_event_concluded: bool = True,
        last_round_full_story: str = "",
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
        character_habits: Optional[list[Any]] = None,
        world_model: Optional[Any] = None,
        option_generator: Optional[OptionGenerator] = None,
        new_character: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[Any], None]] = None,
        narrative_budget: Optional[NarrativeBudget] = None,
        generation_tracker: Optional[GenerationCallTracker] = None,
        operation_id: Optional[str] = None,
    ) -> GameEvent:
        """
        Generate a single round's story and options.

        Args:
            player_state: Current player state dictionary
            language: Language code ('zh' or 'en')
            round_number: Round number within week (0=Mon, 1=Mid, 2=Weekend)
            round_context: Previous rounds' summaries and choices
            character_settings: Character background settings
            stream_callback: Optional callback for streaming story text
            relationship_events: Triggered relationship events
            historical_weekly_summary: Random historical weekly summary
            historical_yearly_summary: Random historical yearly summary
            game_date_info: Game-internal date info
            pending_storylines: Pending storylines for continuity
            established_facts: Established world facts for consistency
            last_event_concluded: Whether last event was concluded
            last_round_full_story: Full story of last round
            activated_foreshadowing: Activated foreshadowing seed
            character_habits: Character habits for behavioral consistency
            world_model: Optional WorldModel instance for consistency constraints
            option_generator: OptionGenerator instance for Step 2

        Returns:
            GameEvent with story and options
        """
        timeline = player_state.get("timeline")
        daily_mode = isinstance(timeline, dict) and timeline.get("version") == 2
        if daily_mode or self._unified_narrative_budgets or narrative_budget is not None:
            narrative_budget = narrative_budget or resolve_narrative_budget(
                NarrativeKind.ROUND,
                GenerationOperation.GENERATE,
                self.quality_level.value,
                language,
            )
            generation_tracker = generation_tracker or GenerationCallTracker(
                narrative_budget
            )

        logger.info(
            f"Generating round event: round={round_number}, "
            f"context_length={len(round_context)}, "
            f"rel_events={len(relationship_events) if relationship_events else 0}, "
            f"stream_callback={stream_callback is not None}"
        )

        # ★ 动态提取历史故事中的高频重复短语，生成禁用列表
        decision_history = player_state.get("decision_history", [])
        overused_phrases = extract_overused_phrases(decision_history, language=language)
        if overused_phrases:
            logger.info(
                f"[AntiRepeat] Round: Injected dynamic ban list ({len(overused_phrases)} chars)"
            )

        style_id = str(
            player_state.get("narrative_style_id")
            or (character_settings or {}).get("narrative_style_id")
            or ""
        )
        self._init_narrative_systems(style_id, player_state)
        style_constraints = _build_style_constraints_text(
            self._prompt_builder, language
        )
        if world_model is not None:
            established_facts = getattr(
                world_model,
                "hard_established_facts",
                established_facts,
            )

        # Get round story prompt
        prompt = get_round_event_prompt(
            player_state,
            language,
            round_number,
            round_context,
            character_settings,
            relationship_events=relationship_events,
            historical_weekly_summary=None,
            historical_yearly_summary=None,
            game_date_info=game_date_info,
            pending_storylines=pending_storylines,
            established_facts=established_facts,
            last_event_concluded=last_event_concluded,
            last_round_full_story=last_round_full_story,
            activated_foreshadowing=activated_foreshadowing,
            character_habits=character_habits,
            world_model=world_model,
            new_character=new_character,
            overused_phrases=overused_phrases,  # ★ 注入动态禁用列表
            style_constraints=style_constraints,
            quality_level=self.quality_level.value,
        )
        generation_budget = (
            get_daily_generation_budget(self.quality_level.value)
            if daily_mode
            else get_generation_budget(self.quality_level.value)
        )
        target_min = (
            narrative_budget.length.target_min
            if narrative_budget is not None
            else generation_budget.min_length
        )
        target_max = (
            narrative_budget.length.target_max
            if narrative_budget is not None
            else generation_budget.max_length
        )
        active_max_tokens = (
            narrative_budget.max_output_tokens
            if narrative_budget is not None
            else generation_budget.max_tokens
        )
        allow_quick_regeneration = (
            narrative_budget.prose_call_limit > 1
            if narrative_budget is not None
            else generation_budget.allow_quick_regeneration
        )
        allow_ai_consistency = (
            narrative_budget.validation_call_limit > 0
            if narrative_budget is not None
            else generation_budget.allow_ai_consistency
        )
        if daily_mode:
            prompt += build_daily_story_mode_constraint(
                player_state,
                character_settings,
                language,
            )

        resume_view = player_state.get("resume_view")
        previous_failure = None
        if isinstance(resume_view, dict):
            previous_failure = resume_view.get("previous_failure")
            if previous_failure is None and resume_view.get("phase") == "failed":
                previous_failure = resume_view.get("failure")
        if isinstance(previous_failure, dict):
            failure_code = str(previous_failure.get("code") or "RETRY_EXHAUSTED")[:80]
            failure_summary = str(previous_failure.get("summary") or "")[:180]
            if language == "zh":
                prompt += (
                    "\n\n【上次手动重试原因】\n"
                    f"错误编号：{failure_code}\n"
                    f"原因：{failure_summary}\n"
                    "请避免再次出现同类问题，但不要虚构新的关系人物来规避检查。"
                )
            else:
                prompt += (
                    "\n\n[Previous Manual Retry Reason]\n"
                    f"Code: {failure_code}\n"
                    f"Reason: {failure_summary}\n"
                    "Avoid the same issue without inventing replacement relationship characters."
                )

        # Step 1: Generate story text (with optional streaming)
        sys_prompt = get_system_prompt("story_novelist", language)
        history_prefix = self._long_history_prefix(player_state, sys_prompt + prompt)
        prompt = prepend_history_prefix(history_prefix, prompt)

        # ★ 动态温度策略：根据上下文调整温度
        # - 有未完结剧情线或上一轮未结束时，使用更保守的温度
        # - 新事件可以更有创意
        has_pending = pending_storylines and len(pending_storylines) > 0
        needs_continuation = not last_event_concluded
        if has_pending or needs_continuation:
            temperature = 0.65  # 更保守，确保剧情连贯
            logger.info(
                f"Dynamic temperature: {temperature} (pending_storylines={has_pending}, continuation={needs_continuation})"
            )
        else:
            temperature = 0.75  # 允许更多创意
            logger.info(f"Dynamic temperature: {temperature} (new event)")

        from src.ai.daily_opening import validate_daily_first_opening
        from src.ai.quick_validator import quick_validate_story

        # 最多尝试次数：默认仅保留 QUICK 重试的一次回退；只有启用约束增强时才走 profile 次数重试。
        # - 无 harness：避免影响现有契约测试（一次主生成 + 一次 quick 重试）
        # - 有 harness：沿用 quality_profile 的重试预算，用于高风险修复。
        max_story_requests = (
            narrative_budget.prose_call_limit
            if narrative_budget is not None
            else self._quality_profile.max_retries + 1
        )
        max_attempts = max_story_requests

        available_people_names = self._validation_people_names(
            player_state, character_settings
        )
        required_people_names: list[str] = []
        for relationship_event in relationship_events or []:
            if isinstance(relationship_event, dict):
                required_name = str(
                    relationship_event.get("character_name")
                    or relationship_event.get("name")
                    or ""
                ).strip()
                if required_name and required_name not in required_people_names:
                    required_people_names.append(required_name)
        if isinstance(new_character, dict):
            required_name = str(new_character.get("name") or "").strip()
            if required_name and required_name not in required_people_names:
                required_people_names.append(required_name)

        def _quick_validate_round_story(candidate: str) -> QuickValidationResult:
            result = quick_validate_story(
                story_text=candidate,
                character_settings=character_settings,
                available_people=available_people_names,
                required_people=required_people_names,
                language=language,
            )
            opening_issues = validate_daily_first_opening(
                candidate,
                player_state,
                character_settings,
                language,
            )
            if opening_issues:
                result.issues.extend(opening_issues)
                result.passed = False
            result.findings = findings_from_legacy(
                issues=result.issues,
                warnings=result.warnings,
                source="quick_validator",
            )
            return result

        committed_stories = self._committed_round_stories(
            player_state,
            last_round_full_story,
        )
        opening_story = (character_settings or {}).get("opening_story")
        if isinstance(opening_story, str) and opening_story.strip():
            committed_stories.append(opening_story)

        best_valid_story_text = ""
        best_soft_story_text = ""
        best_soft_story_rank: Optional[tuple[int, float, int, int]] = None
        last_generation_error: Optional[Exception] = None
        last_findings: list[ValidationFinding] = []
        provider_requests_used = 0
        generation_operation_id = operation_id or uuid.uuid4().hex

        def _call_candidate_story(**kwargs: Any) -> str:
            nonlocal provider_requests_used
            if provider_requests_used >= max_story_requests:
                raise GenerationBudgetError(
                    f"prose call allowance exhausted ({provider_requests_used}/{max_story_requests})"
                )
            provider_requests_used += 1
            if status_callback:
                status_callback(
                    {
                        "phase": (
                            "generating_story"
                            if provider_requests_used == 1
                            else "retry"
                        ),
                        "attempt": provider_requests_used,
                        "max_attempts": max_story_requests,
                        "quality_level": self.quality_level.value,
                    }
                )
            # Candidate prose stays private until every hard gate and option
            # construction has succeeded. Suppress provider streaming so a
            # rejected draft can never flash in the reader.
            kwargs["stream_callback"] = None
            candidate = self._call_required_round_story(**kwargs)
            candidate_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:12]
            logger.info(
                "story_candidate operation_id=%s game_id=%s quality=%s request=%d "
                "length=%d hash=%s",
                generation_operation_id,
                player_state.get("game_id"),
                self.quality_level.value,
                provider_requests_used,
                len(candidate),
                candidate_hash,
            )
            return candidate

        def _emit_selected_story(candidate: str) -> None:
            if stream_callback and candidate:
                stream_callback(candidate)

        def _log_findings(findings: list[ValidationFinding], disposition: str) -> None:
            for finding in findings:
                logger.info(
                    "story_finding operation_id=%s game_id=%s request=%d code=%s "
                    "severity=%s confidence=%.2f disposition=%s fingerprint=%s",
                    generation_operation_id,
                    player_state.get("game_id"),
                    provider_requests_used,
                    finding.code,
                    finding.severity.value,
                    finding.confidence,
                    disposition,
                    finding.fingerprint,
                )

        def _hard_findings(findings: list[ValidationFinding]) -> list[ValidationFinding]:
            return [
                finding
                for finding in findings
                if finding.severity.value == "hard"
            ]

        def _set_best_story(candidate: Optional[str]) -> None:
            if not candidate:
                return
            nonlocal best_valid_story_text
            if self._soft_narrative_lengths:
                best_valid_story_text = candidate
            elif len(candidate) > len(best_valid_story_text):
                best_valid_story_text = candidate

        def _remember_soft_story(
            candidate: str,
            *,
            warning_count: int,
            validation_score: float,
        ) -> None:
            nonlocal best_soft_story_text, best_soft_story_rank
            rank = (
                max(1, int(warning_count)),
                -float(validation_score),
                -len(candidate),
                provider_requests_used,
            )
            if best_soft_story_rank is None or rank < best_soft_story_rank:
                best_soft_story_text = candidate
                best_soft_story_rank = rank

        def _hard_shape_issues(candidate: str) -> list[str]:
            shape_issues = _localized_story_shape_issues(
                candidate,
                language=language,
                target_min=target_min,
                target_max=target_max,
                use_localized_measurement=narrative_budget is not None,
            )
            return [
                issue
                for issue in shape_issues
                if issue
                in {"story_too_short", "story_too_long", "over_fragmented_paragraphs"}
            ]

        def _build_shape_retry_instruction(hard_shape_issues: list[str]) -> str:
            if language == "zh":
                issue_text = "；".join(
                    {
                        "story_too_short": "故事太短",
                        "story_too_long": "故事太长",
                        "over_fragmented_paragraphs": "段落过碎",
                    }.get(issue, issue)
                    for issue in hard_shape_issues
                )
                return (
                    "\n\n【篇幅与分段修正 - 必须重写】\n"
                    f"{issue_text}。请重新生成本轮故事，严格控制在"
                    f"{target_min}-{target_max}字，"
                    "使用2-5个自然段，每段有完整场景推进，禁止拆成大量短句碎片。"
                )
            issue_text = "; ".join(hard_shape_issues)
            return (
                "\n\n[Length and Paragraph Fix - Regenerate Required]\n"
                f"{issue_text}. Regenerate this round within "
                f"{target_min}-{target_max} words, "
                "using 2-5 coherent paragraphs."
            )

        def _build_terminal_continuity_retry_instruction(
            failures: list[Any],
        ) -> str:
            issue_lines = []
            for failure in failures[:5]:
                evidence = str(getattr(failure, "evidence", "") or "").strip()
                detail = f" ({evidence[:120]})" if evidence else ""
                constraint_type = str(
                    getattr(failure, "constraint_type", failure)
                ).strip()
                issue_lines.append(f"- {constraint_type}{detail}")
            issues = "\n".join(issue_lines)
            if language == "zh":
                return (
                    "【严重连续性修正 - 必须重写】\n"
                    f"上一版违反以下连续性约束：\n{issues}\n"
                    "请依据既有事实、人物状态和因果关系重新生成，不得绕过这些约束。"
                )
            return (
                "[Severe Continuity Fix - Regenerate Required]\n"
                f"The previous draft violated these continuity constraints:\n{issues}\n"
                "Regenerate from established facts, character state, and causal history."
            )

        def _build_targeted_repair_prompt(
            base_prompt: str,
            rejected_story: str,
            issues: list[str],
        ) -> str:
            issue_lines = "\n".join(f"- {issue}" for issue in issues[:8])
            if language == "zh":
                return (
                    base_prompt
                    + "\n\n【定点修订 - 返回完整故事】\n"
                    + "上一稿存在以下确定性问题：\n"
                    + issue_lines
                    + "\n\n【上一稿全文】\n"
                    + rejected_story
                    + "\n【上一稿结束】\n"
                    + "请保留合格的情节、文风和事实，只修正上述问题，并返回修订后的完整故事。"
                )
            return (
                base_prompt
                + "\n\n[Targeted Revision - Return the Full Story]\n"
                + "The rejected draft has these confirmed issues:\n"
                + issue_lines
                + "\n\n[Full Rejected Draft]\n"
                + rejected_story
                + "\n[End Rejected Draft]\n"
                + "Preserve valid plot, style, and facts; fix only the listed issues and return the full revised story."
            )

        # 初始化 Harness 组件（延迟初始化，避免每次构建时重复创建）
        if self._harness_enabled and self._validation_pipeline is None:
            from src.ai.harness import default_registry

            self._validation_pipeline = ValidationPipeline(default_registry)
        if self._harness_enabled and self._retry_controller is None:
            self._retry_controller = RetryController(profile=self._quality_profile)
        if self._harness_enabled and self._diagnostics is None:
            self._diagnostics = ConstraintViolationDiagnostic()

        retry_hint = None
        previous_hard_fingerprints: set[str] = set()

        for attempt in range(max_attempts):
            best_story_before_attempt = best_valid_story_text
            story_text = None
            candidate_validation_score = 100.0
            harness_soft_warning_count = 0
            try:
                attempt_prompt = prompt
                if retry_hint:
                    attempt_prompt = prompt + f"\n\n[Retry Hint]\n{retry_hint}"

                current_temp = self._resolve_temperature(
                    attempt,
                    temperature,
                    0.05,
                    min_temperature=0.65,
                )
                logger.info(
                    f"Round story attempt {attempt + 1}/{max_attempts}, temperature={current_temp}"
                )

                story_text = _call_candidate_story(
                    language=language,
                    generation_tracker=generation_tracker,
                    system_prompt=sys_prompt,
                    user_prompt=attempt_prompt,
                    temperature=current_temp,
                    max_tokens=active_max_tokens,
                    stream_callback=stream_callback,
                    frequency_penalty=0.4,  # ★ 轮次级别更强的反重复，因为同周多轮更容易重复
                    presence_penalty=0.4,  # ★ 鼓励每轮使用不同的表达方式
                    request_timeout=self._story_request_timeout_seconds(
                        narrative_budget, generation_tracker
                    ),
                )
                logger.info(f"Generated round story with {len(story_text)} characters")

                # Step 1.4: Quick rule-based validation (before AI validation)
                quick_result = _quick_validate_round_story(story_text)
                last_findings = list(quick_result.findings)
                _log_findings(
                    last_findings,
                    "retry" if _hard_findings(last_findings) else "accept_warning",
                )
                first_hard_fingerprints = {
                    finding.fingerprint for finding in _hard_findings(last_findings)
                }
                quick_retry_used = False
                locally_usable_story = quick_result.passed
                repeated_from_previous_candidate = (
                    first_hard_fingerprints.intersection(
                        previous_hard_fingerprints
                    )
                )
                quick_circuit_broken = False
                if repeated_from_previous_candidate:
                    logger.warning(
                        "Story validation circuit breaker: repeated hard fingerprint(s)=%s",
                        sorted(repeated_from_previous_candidate),
                    )
                    break
                elif first_hard_fingerprints:
                    previous_hard_fingerprints = first_hard_fingerprints
                else:
                    previous_hard_fingerprints = set()

                if (
                    not quick_circuit_broken
                    and not quick_result.passed
                    and allow_quick_regeneration
                ):
                    logger.warning(f"Quick validation failed: {quick_result.issues}")
                    retry_prompt = _build_targeted_repair_prompt(
                        attempt_prompt,
                        story_text,
                        quick_result.issues,
                    )
                    if status_callback:
                        status_callback("retry")

                    story_text = _call_candidate_story(
                        language=language,
                        generation_tracker=generation_tracker,
                        system_prompt=sys_prompt,
                        user_prompt=retry_prompt,
                        temperature=0.65,
                        max_tokens=active_max_tokens,
                        stream_callback=stream_callback,
                        frequency_penalty=0.4,
                        presence_penalty=0.4,
                        request_timeout=self._story_request_timeout_seconds(
                            narrative_budget, generation_tracker
                        ),
                    )
                    quick_retry_used = True
                    logger.info(
                        "Quick validation retry completed with %d characters",
                        len(story_text),
                    )

                    retry_result = _quick_validate_round_story(story_text)
                    last_findings = list(retry_result.findings)
                    _log_findings(
                        last_findings,
                        "retry" if _hard_findings(last_findings) else "accepted",
                    )

                    if not retry_result.passed:
                        logger.warning(
                            "Quick validation retry still failed: %s",
                            retry_result.issues,
                        )
                        locally_usable_story = False
                        repeated_hard_fingerprints = first_hard_fingerprints.intersection(
                            finding.fingerprint
                            for finding in _hard_findings(last_findings)
                        )
                        if repeated_hard_fingerprints:
                            logger.warning(
                                "Story validation circuit breaker: repeated hard fingerprint(s)=%s",
                                sorted(repeated_hard_fingerprints),
                            )
                            break
                        elif provider_requests_used < max_story_requests:
                            previous_hard_fingerprints = {
                                finding.fingerprint
                                for finding in _hard_findings(last_findings)
                            }
                            retry_hint = "\n".join(retry_result.issues[:8])
                            logger.info(
                                "Hard validation findings changed; trying a fresh candidate within budget"
                            )
                            continue
                        else:
                            break
                    else:
                        locally_usable_story = True
                        previous_hard_fingerprints = set()
                    if retry_result.warnings:
                        logger.info(
                            "Quick validation retry warnings: %s",
                            retry_result.warnings,
                        )

                elif not quick_circuit_broken and not quick_result.passed:
                    locally_usable_story = False
                    logger.warning(
                        "Fast generation rejected deterministic hard validation issues without a second provider call: %s",
                        quick_result.issues,
                    )
                    raise ValueError(
                        "Quick validation failed: " + "; ".join(quick_result.issues)
                    )
                elif quick_result.warnings:
                    logger.info(f"Quick validation warnings: {quick_result.warnings}")

                hard_shape_issues = _hard_shape_issues(story_text)
                requires_shape_retry = (
                    not quick_retry_used or "story_too_long" in hard_shape_issues
                )
                if (
                    hard_shape_issues
                    and allow_quick_regeneration
                    and requires_shape_retry
                    and provider_requests_used < max_story_requests
                ):
                    logger.warning(
                        "Story shape validation failed: %s", hard_shape_issues
                    )
                    if status_callback:
                        status_callback("retry")
                    story_text = _call_candidate_story(
                        language=language,
                        generation_tracker=generation_tracker,
                        system_prompt=sys_prompt,
                        user_prompt=attempt_prompt
                        + _build_shape_retry_instruction(hard_shape_issues),
                        temperature=0.65,
                        max_tokens=active_max_tokens,
                        stream_callback=stream_callback,
                        frequency_penalty=0.4,
                        presence_penalty=0.4,
                        request_timeout=self._story_request_timeout_seconds(
                            narrative_budget, generation_tracker
                        ),
                    )
                    logger.info(
                        "Story shape retry completed with %d characters",
                        len(story_text),
                    )
                    retry_shape_issues = _hard_shape_issues(story_text)
                    retry_quick_result = _quick_validate_round_story(story_text)
                    if not retry_quick_result.passed:
                        logger.warning(
                            "Story shape retry still failed: shape=%s quick=%s",
                            retry_shape_issues,
                            retry_quick_result.issues,
                        )
                        if (
                            self._soft_narrative_lengths
                            and len(best_valid_story_text) > 20
                        ):
                            story_text = best_valid_story_text
                        else:
                            raise ValueError(
                                "Story shape validation failed: "
                                + "; ".join(
                                    retry_shape_issues + retry_quick_result.issues
                                )
                            )
                    elif retry_shape_issues:
                        logger.warning(
                            "Story shape retry completed with diagnostics: %s",
                            retry_shape_issues,
                        )
                        if not self._soft_narrative_lengths:
                            raise ValueError(
                                "Story shape validation failed: "
                                + "; ".join(retry_shape_issues)
                            )
                    if self._soft_narrative_lengths and retry_quick_result.passed:
                        last_findings = list(retry_quick_result.findings)
                elif hard_shape_issues:
                    logger.warning(
                        "Story shape issues recorded without another provider retry: %s",
                        hard_shape_issues,
                    )
                    if not self._soft_narrative_lengths:
                        raise ValueError(
                            "Story shape validation failed: "
                            + "; ".join(hard_shape_issues)
                        )

                if self._repeats_committed_story(story_text, committed_stories):
                    if self._canonical_story_for_repeat_check(
                        best_valid_story_text
                    ) == self._canonical_story_for_repeat_check(story_text):
                        best_valid_story_text = ""
                    logger.warning(
                        "Round story repeats committed story; requesting one rewrite"
                    )
                    if status_callback:
                        status_callback("retry")
                    repeat_retry_prompt = attempt_prompt + (
                        "\n\n【重复正文修正 - 必须重写】\n"
                        "上一版与已提交轮次重复。请围绕当前日期、未解决事项和玩家状态写出一个"
                        "不同的具体事件；不得复用先前场景、句式或选项。"
                        if language == "zh"
                        else "\n\n[Repeated Story Fix - Regenerate Required]\n"
                        "The previous version duplicates a committed round. Write a distinct concrete event "
                        "grounded in the current date, unresolved threads, and player state; do not reuse "
                        "the earlier scene, phrasing, or options."
                    )
                    story_text = _call_candidate_story(
                        language=language,
                        generation_tracker=generation_tracker,
                        system_prompt=sys_prompt,
                        user_prompt=repeat_retry_prompt,
                        temperature=0.65,
                        max_tokens=active_max_tokens,
                        stream_callback=stream_callback,
                        frequency_penalty=0.5,
                        presence_penalty=0.5,
                        request_timeout=self._story_request_timeout_seconds(
                            narrative_budget, generation_tracker
                        ),
                    )
                    repeat_retry_validation = _quick_validate_round_story(story_text)
                    repeat_retry_shape_issues = _hard_shape_issues(story_text)
                    if not repeat_retry_validation.passed:
                        issues = (
                            repeat_retry_validation.issues + repeat_retry_shape_issues
                        )
                        raise ValueError(
                            "Repeated-story retry failed validation: "
                            + "; ".join(issues)
                        )
                    if repeat_retry_shape_issues:
                        logger.warning(
                            "Repeated-story retry shape diagnostics: %s",
                            repeat_retry_shape_issues,
                        )
                        if not self._soft_narrative_lengths:
                            raise ValueError(
                                "Repeated-story retry failed validation: "
                                + "; ".join(repeat_retry_shape_issues)
                            )
                    if self._repeats_committed_story(story_text, committed_stories):
                        raise ValueError(
                            "Round story repeats committed story after retry"
                        )

                # Step 1.5: AI-based consistency validation (if world_model is provided)
                if world_model and story_text and allow_ai_consistency:
                    story_text = self._validate_and_retry_story(
                        story_text=story_text,
                        world_model=world_model,
                        player_state=player_state,
                        character_settings=character_settings or {},
                        language=language,
                        original_prompt=prompt,
                        sys_prompt=sys_prompt,
                        stream_callback=stream_callback,
                        status_callback=status_callback,
                        narrative_budget=narrative_budget,
                        generation_tracker=generation_tracker,
                        story_call=_call_candidate_story,
                    )
                    post_validation_quick_result = _quick_validate_round_story(
                        story_text
                    )
                    last_findings = list(post_validation_quick_result.findings)
                    _log_findings(
                        last_findings,
                        (
                            "retry"
                            if _hard_findings(last_findings)
                            else "accepted"
                        ),
                    )
                    if not post_validation_quick_result.passed:
                        raise ValueError(
                            "Story consistency retry failed quick validation: "
                            + "; ".join(post_validation_quick_result.issues)
                        )
                    post_validation_shape_issues = _hard_shape_issues(story_text)
                    if post_validation_shape_issues:
                        logger.warning(
                            "Story consistency retry shape diagnostics: %s",
                            post_validation_shape_issues,
                        )
                        if not self._soft_narrative_lengths:
                            best_valid_story_text = ""
                            raise ValueError(
                                "Story consistency retry failed shape validation: "
                                + "; ".join(post_validation_shape_issues)
                            )

                # Harness 检查（仅在开启时执行），支持在无效内容上继续 retry
                if self._harness_enabled and self._validation_pipeline:
                    diagnostic_context = {
                        "character_settings": character_settings,
                        "available_people": available_people_names,
                        "relationship_events": relationship_events,
                        "historical_weekly_summary": historical_weekly_summary,
                        "historical_yearly_summary": historical_yearly_summary,
                        "game_date_info": game_date_info,
                        "pending_storylines": pending_storylines,
                        "established_facts": established_facts,
                        "world_model_state": getattr(world_model, "__dict__", None),
                        "character_habits": character_habits,
                    }
                    validation_result = self._validation_pipeline.validate(
                        story_text=story_text,
                        context=diagnostic_context,
                        profile=self._quality_profile,
                    )
                    candidate_validation_score = float(validation_result.score)
                    harness_soft_warning_count = sum(
                        len(getattr(validation_result, field_name, []) or [])
                        for field_name in ("high_warnings", "medium_notes", "low_notes")
                    )

                    validation_failures = (
                        validation_result.critical_failures
                        + validation_result.high_warnings
                        + validation_result.medium_notes
                        + validation_result.low_notes
                        if self._soft_narrative_lengths
                        else validation_result.critical_failures
                    )
                    promoted_continuity_failures = (
                        [
                            failure
                            for failure in validation_failures
                            if getattr(failure, "constraint_type", None)
                            in _TERMINAL_CONTINUITY_CONSTRAINTS
                        ]
                        if self._soft_narrative_lengths
                        else []
                    )
                    hard_validation_failures = list(
                        validation_result.critical_failures
                    )
                    for failure in promoted_continuity_failures:
                        if failure not in hard_validation_failures:
                            hard_validation_failures.append(failure)
                    terminal_validation_failed = (
                        bool(hard_validation_failures)
                        if self._soft_narrative_lengths
                        else not validation_result.passed
                    )

                    if terminal_validation_failed:
                        best_valid_story_text = best_story_before_attempt

                    diagnostic_report = (
                        ConstraintViolationDiagnostic().generate_report(
                            story_text=story_text,
                            validation_result=validation_result,
                        )
                        if self._diagnostics is None
                        else self._diagnostics.generate_report(
                            story_text=story_text,
                            validation_result=validation_result,
                        )
                    )

                    should_retry = False
                    if terminal_validation_failed and self._soft_narrative_lengths:
                        should_retry = (
                            attempt < self._quality_profile.max_retries
                            and attempt < max_attempts - 1
                        )
                        retry_hint = (
                            _build_terminal_continuity_retry_instruction(
                                hard_validation_failures
                            )
                            if should_retry
                            else None
                        )
                    elif (
                        terminal_validation_failed
                        and self._retry_controller is not None
                    ):
                        should_retry, retry_hint = self._retry_controller.should_retry(
                            validation_result=validation_result,
                            diagnostic_report=diagnostic_report,
                            attempt=attempt,
                        )
                    if should_retry:
                        if status_callback:
                            status_callback("retry")
                        logger.info(
                            "Round event harness retry requested on attempt %d",
                            attempt + 1,
                        )
                        continue

                    if self._soft_narrative_lengths and not validation_result.passed:
                        logger.warning(
                            "Non-terminal Harness diagnostics retained: %s",
                            [
                                str(getattr(failure, "constraint_type", failure))
                                for failure in validation_failures
                                if failure not in hard_validation_failures
                            ],
                        )

                    if hard_validation_failures or (
                        terminal_validation_failed
                        and self._quality_profile.enforce_validation_on_all_attempts
                    ):
                        raise ValueError(
                            "Story harness validation failed after final attempt"
                        )

                # This exact text has now passed quick, shape, repetition,
                # consistency, and Harness hard gates. Only now may it become
                # a historical or soft-warning fallback candidate.
                _set_best_story(story_text)
                soft_warning_count = harness_soft_warning_count + sum(
                    1
                    for finding in last_findings
                    if finding.severity is FindingSeverity.WARNING
                )
                if soft_warning_count:
                    _remember_soft_story(
                        story_text,
                        warning_count=soft_warning_count,
                        validation_score=candidate_validation_score,
                    )
                    if provider_requests_used < max_story_requests:
                        retry_hint = (
                            "Improve non-blocking story quality warnings while preserving all established facts."
                        )
                        logger.info(
                            "Soft-warning candidate retained; trying another candidate within budget"
                        )
                        continue
                    break

                # Step 2: Generate options based on the story
                if option_generator is None:
                    raise ValueError("option_generator is required")

                if status_callback:
                    status_callback("generating_options")

                event = option_generator.generate_options_only(
                    story_description=story_text,
                    player_state=player_state,
                    character_settings=character_settings,
                    language=language,
                    history_prefix=history_prefix,
                    generation_tracker=generation_tracker,
                )

                # Validate relationships
                option_generator.validate_and_fix_relationships(
                    event, character_settings
                )

                # Validate options consistency
                option_issues = option_generator.validate_options_consistency(
                    event=event,
                    story_description=story_text,
                    available_people=available_people_names,
                    language=language,
                )
                if option_issues:
                    logger.warning(f"Options consistency issues found: {option_issues}")
                    option_generator.ensure_options_consistency(
                        event=event,
                        story_description=story_text,
                        available_people=available_people_names,
                        language=language,
                    )

                logger.info(
                    "story_generation_outcome operation_id=%s game_id=%s quality=%s "
                    "attempts=%d warnings=%d committed=true manual_retry=%s",
                    generation_operation_id,
                    player_state.get("game_id"),
                    self.quality_level.value,
                    provider_requests_used,
                    sum(
                        1
                        for finding in last_findings
                        if finding.severity.value == "warning"
                    ),
                    bool(previous_failure),
                )
                _emit_selected_story(story_text)
                return event

            except _EmptyStoryProviderOutput as e:
                if not self._soft_narrative_lengths:
                    best_valid_story_text = best_story_before_attempt
                logger.warning(f"Round event attempt {attempt + 1} failed: {e}")
                last_generation_error = e
            except GenerationBudgetError as e:
                logger.warning("Round request budget exhausted: %s", e)
                best_valid_story_text = ""
                last_generation_error = e
                break
            except StoryGenerationFailure as e:
                # A candidate rejected by a hard consistency check is never a
                # safe historical fallback. Preserve its structured findings
                # for the player-facing terminal failure instead.
                best_valid_story_text = ""
                last_findings = list(e.findings)
                last_generation_error = e
                logger.warning(
                    "Round event attempt %d failed hard consistency validation: %s",
                    attempt + 1,
                    e,
                )
                if e.circuit_break:
                    raise
            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Round event attempt {attempt + 1} failed: {e}")
                last_generation_error = e
            except StopIteration:
                # Deterministic test providers may intentionally expose a
                # finite sequence. Preserve the concrete rejection from the
                # preceding attempt instead of replacing it with an empty
                # StopIteration message.
                logger.warning("Round story provider fixture exhausted")
                break
            except Exception as e:
                logger.error(
                    f"Unexpected error in round event attempt {attempt + 1}: {e}"
                )
                last_generation_error = e

            # Internal repair calls share the same provider budget as outer
            # attempts. Keep trying fresh candidates until that total budget
            # is actually spent.
            if provider_requests_used >= max_story_requests:
                break

            if attempt < max_attempts - 1:
                retry_hint = None if not retry_hint else retry_hint
                continue

            break

        if len(best_soft_story_text) > 20:
            logger.info(
                "Using best soft-warning story (%d chars) after all round attempts",
                len(best_soft_story_text),
            )
            fallback_options = OptionGenerator.complete_new_event_options(
                [],
                story_description=best_soft_story_text,
                language=language,
                decision_history=player_state.get("decision_history", []),
            )
            from src.game.daily_transition import prepare_daily_option_transitions

            fallback_options = prepare_daily_option_transitions(
                fallback_options,
                player_state,
                language=language,
            )
            if language == "zh":
                notice_summary = "已展示自动尝试中较好的一稿"
                notice_reason = (
                    "这版故事通过了必要检查，但仍有非关键质量提示。"
                    "你可以继续阅读，也可以重新生成。"
                )
            else:
                notice_summary = "Showing the best available draft"
                notice_reason = (
                    "This story passed all required checks but still has non-blocking quality warnings. "
                    "You can keep reading or regenerate it."
                )
            logger.info(
                "story_generation_outcome operation_id=%s game_id=%s quality=%s "
                "attempts=%d committed=true fallback=soft_warning",
                generation_operation_id,
                player_state.get("game_id"),
                self.quality_level.value,
                provider_requests_used,
            )
            event = GameEvent(
                event_description=best_soft_story_text,
                options=fallback_options,
                delivery_notice=StoryDeliveryNotice(
                    summary=notice_summary,
                    reason=notice_reason,
                    attempts_used=max(1, provider_requests_used),
                ),
            )
            _emit_selected_story(best_soft_story_text)
            return event

        if len(best_valid_story_text) > 20:
            logger.info(
                "Using best historical story (%d chars) after all round attempts",
                len(best_valid_story_text),
            )
            fallback_options = OptionGenerator.complete_new_event_options(
                [],
                story_description=best_valid_story_text,
                language=language,
                decision_history=player_state.get("decision_history", []),
            )
            from src.game.daily_transition import prepare_daily_option_transitions

            fallback_options = prepare_daily_option_transitions(
                fallback_options,
                player_state,
                language=language,
            )
            logger.info(
                "story_generation_outcome operation_id=%s game_id=%s quality=%s "
                "attempts=%d committed=true fallback=true",
                generation_operation_id,
                player_state.get("game_id"),
                self.quality_level.value,
                provider_requests_used,
            )
            event = GameEvent(
                event_description=best_valid_story_text,
                options=fallback_options,
            )
            _emit_selected_story(best_valid_story_text)
            return event

        message = "Story generation failed before producing a valid event"
        if last_generation_error is not None:
            message = f"{message}: {last_generation_error}"
        attempts_used = (
            generation_tracker.prose_calls
            if generation_tracker is not None
            else provider_requests_used
        )
        logger.info(
            "story_generation_outcome operation_id=%s game_id=%s quality=%s "
            "attempts=%d committed=false hard_findings=%d",
            generation_operation_id,
            player_state.get("game_id"),
            self.quality_level.value,
            attempts_used,
            sum(
                1
                for finding in last_findings
                if finding.severity.value == "hard"
            ),
        )
        raise StoryGenerationFailure(
            message,
            findings=last_findings,
            attempts_used=attempts_used,
        ) from last_generation_error

    # -------------------- Internal --------------------

    @staticmethod
    def _env_enabled(name: str) -> bool:
        return os.environ.get(name, "").lower() in ("true", "1", "yes")

    def _init_narrative_systems(
        self,
        style_id: str,
        player_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize or refresh narrative style systems for the selected style."""
        del player_state
        requested_style_id = style_id or "magical_realism"
        if (
            self._narrative_systems_initialized
            and self._initialized_style_id == requested_style_id
        ):
            return

        self._style_manifest = None
        self._prompt_builder = None
        self._style_validator = None

        try:
            from src.ai.narrative.style_manifest import get_style
            from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder
            from src.ai.narrative.style_validator import StyleAwareValidator

            self._style_manifest = get_style(requested_style_id)
            if not self._style_manifest and not style_id:
                self._style_manifest = get_style("magical_realism")

            if self._style_manifest:
                self._prompt_builder = StyleAwarePromptBuilder(self._style_manifest)
                self._style_validator = StyleAwareValidator(self._style_manifest)
                logger.info(
                    "Style engine initialized: %s",
                    self._style_manifest.style_id,
                )
            else:
                logger.warning(
                    "Style %r not found, style engine disabled", requested_style_id
                )
        except Exception as exc:
            logger.warning("Failed to initialize narrative style systems: %s", exc)
        finally:
            self._narrative_systems_initialized = True
            self._initialized_style_id = requested_style_id

    def _gather_narrative_hints(
        self,
        player_state: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return optional narrative hints for legacy extension points."""
        del player_state, character_settings
        return {}

    def _log_constraint_completeness(self, *args: Any, **kwargs: Any) -> None:
        """Legacy diagnostics hook retained for tests and extension callers."""
        del args, kwargs

    def _extract_validation_context(
        self,
        player_state: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        """Return the era context used by fast story validation."""
        del player_state
        from src.ai.quick_validator import QuickValidator

        return QuickValidator.extract_era_context(character_settings)

    @staticmethod
    def _build_round_story_fallback(
        player_state: Dict[str, Any],
        character_settings: Dict[str, Any],
        language: str,
        round_number: int,
    ) -> str:
        from src.game.relationship_authority import extract_required_key_people

        player_name = (
            resolve_protagonist_name(player_state, character_settings, None) or "你"
        )
        required_people = extract_required_key_people(character_settings or {})
        anchor_person = required_people[0] if required_people else {}

        if language == "zh":
            era = ""
            era_setting = character_settings.get("era")
            if isinstance(era_setting, dict):
                era = str(
                    era_setting.get("era_description")
                    or era_setting.get("description")
                    or ""
                )

            trait = ""
            trait_setting = character_settings.get("traits")
            if isinstance(trait_setting, dict):
                trait = str(
                    trait_setting.get("traits_description")
                    or trait_setting.get("description")
                    or ""
                )

            round_names = ["周初", "周中", "周末"]
            round_name = (
                round_names[round_number]
                if 0 <= round_number < len(round_names)
                else "这一天"
            )
            setting_clause = f"在{era}的背景下，" if era else ""
            trait_clause = (
                f"你把{trait}放在心里，" if trait else "你把眼前的线索重新梳理，"
            )
            cast_clause = ""
            if anchor_person.get("name"):
                role = (
                    anchor_person.get("role")
                    or anchor_person.get("relationship")
                    or "关键人物"
                )
                cast_clause = f"{anchor_person['name']}这位{role}仍在你的关系网里，"

            return (
                f"{setting_clause}{round_name}，{player_name}没有遇到突发的巨大转折，"
                "但生活仍然留下了需要判断的细节。"
                f"{trait_clause}{cast_clause}一边确认身边人的态度，一边衡量接下来要投入多少精力。"
                "这段平静并不是停滞，而是一次调整节奏的机会；你可以先回应眼前的请求，"
                "也可以暂时放慢脚步，把现场线索核对清楚后再行动。"
            )

        round_names_en = ["early in the week", "midweek", "late in the week"]
        round_name_en = (
            round_names_en[round_number]
            if 0 <= round_number < len(round_names_en)
            else "today"
        )
        cast_clause_en = (
            f"{anchor_person['name']} still matters in your relationship network, "
            if anchor_person.get("name")
            else ""
        )
        return (
            f"{round_name_en.title()}, {player_name} does not encounter a dramatic turn, "
            "but the day still leaves several details worth weighing. You take a moment "
            f"to read the mood around you, {cast_clause_en}sort through the immediate clues, and decide "
            "whether to answer the request in front of you or slow down and verify the "
            "situation before acting."
        )

    def _validate_and_retry_story(
        self,
        story_text: str,
        world_model: Any,
        player_state: Dict[str, Any],
        character_settings: Dict[str, Any],
        language: str,
        original_prompt: str,
        sys_prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        narrative_budget: Optional[NarrativeBudget] = None,
        generation_tracker: Optional[GenerationCallTracker] = None,
        story_call: Optional[Callable[..., str]] = None,
    ) -> str:
        """
        Validate story consistency and retry once if CRITICAL issues found.

        Optimized strategy:
        - Only retry for truly critical issues (causal breaks, major contradictions)
        - Use tiered validation: check only the most important constraints first

        Returns:
            Original or regenerated story text
        """
        # ★ 诊断日志：确认进入时 stream_callback 状态
        logger.info(
            f"[_validate_and_retry_story] Entered with stream_callback={stream_callback is not None}"
        )

        try:
            from src.ai.consistency_validator import ConsistencyValidator

            # ★ 发送校验状态，让用户知道正在检查故事一致性
            if status_callback:
                logger.info("★ 发送 validating 状态提示")
                status_callback("validating")

            validator = ConsistencyValidator(self.client)  # type: ignore[no-untyped-call]
            validation = validator.validate_story(
                story_text=story_text,
                world_model=world_model,
                player_state_dict=player_state,
                character_settings=character_settings,
                language=language,
                run_ai_validation=not self._quality_profile.skip_ai_consistency_check,
                generation_tracker=generation_tracker,
                max_output_tokens=(
                    narrative_budget.max_output_tokens
                    if narrative_budget is not None
                    else get_generation_budget(self.quality_level.value).max_tokens
                ),
            )

            if validation.passed:
                return story_text

            if not validation.has_critical_issues:
                logger.info(
                    f"一致性校验有 {len(validation.warning_issues)} 个WARNING，不触发重试"
                )
                return story_text

            # CRITICAL issues found - retry once
            logger.warning(
                f"一致性校验不通过，{len(validation.critical_issues)} 个CRITICAL问题，触发重试"
            )
            for issue in validation.critical_issues:
                logger.warning(
                    f"  CRITICAL [{issue.dimension}]: {issue.description[:80]}"
                )

            # Regenerate with fix instructions appended
            # ★ 重要：重试时也需要流式输出，否则前端会显示不完整的旧内容
            if language == "zh":
                retry_prompt = (
                    original_prompt
                    + "\n\n【定点一致性修订 - 返回完整故事】\n"
                    + validation.fix_instructions
                    + "\n\n【上一稿全文】\n"
                    + story_text
                    + "\n【上一稿结束】\n"
                    + "请保留没有问题的内容，仅修正上述一致性问题，并返回完整故事。"
                )
            else:
                retry_prompt = (
                    original_prompt
                    + "\n\n[Targeted Consistency Revision - Return the Full Story]\n"
                    + validation.fix_instructions
                    + "\n\n[Full Rejected Draft]\n"
                    + story_text
                    + "\n[End Rejected Draft]\n"
                    + "Preserve valid content, fix the listed consistency issues, and return the full story."
                )

            # ★ 先发送状态提示，让前端显示"正在优化故事"
            if status_callback:
                logger.info("★ 发送 retrying 状态提示")
                status_callback("retrying")

            # ★ 发送特殊的 retry 事件让前端清空故事（通过 status 回调）
            # 不再使用 stream_callback 发送 RETRY 标记，避免干扰故事流
            if status_callback:
                logger.info("★ 发送 retry 事件让前端清空故事")
                status_callback("retry")  # 前端会识别这个状态并清空故事

            # ★ 诊断日志：确认 stream_callback 状态
            if stream_callback is None:
                logger.warning(
                    "★★★ stream_callback is None in retry! This should not happen."
                )
            else:
                logger.info(f"★ stream_callback is present in retry: {stream_callback}")

            # ★ 优化：重试时使用固定的低温度 0.7，确保更保守、更符合约束
            logger.info(
                f"Consistency retry with temperature=0.7 (conservative), stream_callback={stream_callback is not None}"
            )

            retry_story = (story_call or self._call_required_round_story)(
                language=language,
                generation_tracker=generation_tracker,
                system_prompt=sys_prompt,
                user_prompt=retry_prompt,
                temperature=0.7,  # 固定低温度，确保严格遵守约束
                max_tokens=(
                    narrative_budget.max_output_tokens
                    if narrative_budget is not None
                    else get_generation_budget(self.quality_level.value).max_tokens
                ),
                stream_callback=stream_callback,
                frequency_penalty=0.3,  # ★ 重试时也保持反重复
                presence_penalty=0.3,
                request_timeout=self._story_request_timeout_seconds(
                    narrative_budget, generation_tracker
                ),
            )

            if retry_story:
                logger.info(f"重试生成完成，故事长度: {len(retry_story)}")
                repaired_validation = validator.validate_story(
                    story_text=retry_story,
                    world_model=world_model,
                    player_state_dict=player_state,
                    character_settings=character_settings,
                    language=language,
                    run_ai_validation=not self._quality_profile.skip_ai_consistency_check,
                    generation_tracker=generation_tracker,
                    max_output_tokens=(
                        narrative_budget.max_output_tokens
                        if narrative_budget is not None
                        else get_generation_budget(self.quality_level.value).max_tokens
                    ),
                )
                if repaired_validation.passed or not repaired_validation.has_critical_issues:
                    return retry_story

                def _fingerprints(result: Any) -> set[str]:
                    return {
                        hashlib.sha256(
                            (
                                str(issue.dimension).strip().lower()
                                + "|"
                                + re.sub(r"\s+", " ", str(issue.description)).strip().lower()
                            ).encode("utf-8")
                        ).hexdigest()[:16]
                        for issue in result.critical_issues
                    }

                original_fingerprints = _fingerprints(validation)
                repaired_fingerprints = _fingerprints(repaired_validation)
                repeated = bool(original_fingerprints & repaired_fingerprints)
                findings = [
                    ValidationFinding(
                        code="VALIDATION_FAILED",
                        severity=FindingSeverity.HARD,
                        confidence=0.9,
                        source="consistency_validator",
                        message=issue.description,
                        evidence=issue.description,
                        repair_instruction=issue.fix_suggestion,
                    )
                    for issue in repaired_validation.critical_issues
                ]
                raise StoryGenerationFailure(
                    (
                        "repeated consistency hard fingerprint after targeted repair"
                        if repeated
                        else "consistency repair still contains hard findings"
                    ),
                    findings=findings,
                    attempts_used=(
                        generation_tracker.prose_calls
                        if generation_tracker is not None
                        else 1
                    ),
                    circuit_break=repeated,
                )

            return story_text

        except (_EmptyStoryProviderOutput, GenerationBudgetError, StoryGenerationFailure):
            raise
        except Exception as e:
            logger.error(f"Story validation/retry failed: {e}")
            raise StoryGenerationFailure(
                "consistency validation service unavailable",
                findings=[
                    ValidationFinding(
                        code="VALIDATION_SERVICE_ERROR",
                        severity=FindingSeverity.HARD,
                        confidence=1.0,
                        source="consistency_validator",
                        message="故事一致性校验服务暂时不可用",
                        repair_instruction="稍后重新生成并再次校验",
                    )
                ],
                attempts_used=(
                    generation_tracker.prose_calls
                    if generation_tracker is not None
                    else 1
                ),
            ) from e

    @staticmethod
    def _get_phase_from_state(player_state: Dict[str, Any]) -> str:
        """Determine life phase from player state."""
        week = player_state.get("week", 0)
        if week < 24:
            return "early_career"
        elif week < 48:
            return "establishing"
        elif week < 72:
            return "growth"
        else:
            return "consolidation"

    @staticmethod
    def _build_world_model_from_state_dict(
        player_state: Dict[str, Any],
    ) -> Optional[WorldModel]:
        """Build world-model constraints for dict-based generation entrypoints."""
        if not player_state:
            return None

        has_world_context = bool(
            player_state.get("world_model_data")
            or player_state.get("established_facts")
            or player_state.get("character_settings")
        )
        if not has_world_context:
            return None

        try:
            from src.game.world_model import WorldModel

            character_settings = player_state.get("character_settings", {})
            state_obj = SimpleNamespace(
                week=player_state.get("week", 0),
                current_round=player_state.get("current_round", 0),
                age=player_state.get("age"),
                player_name=resolve_protagonist_name(
                    player_state, character_settings, None
                )
                or "主角",
                character_settings=character_settings,
                established_facts=player_state.get("established_facts", []),
                world_model_data=player_state.get("world_model_data", {}),
                continuity_ledger=player_state.get("continuity_ledger", {}),
                timeline=player_state.get("timeline"),
                timeline_version=player_state.get("timeline_version"),
                day_history=player_state.get("day_history", []),
            )
            timeline = player_state.get("timeline")
            if isinstance(timeline, dict) and timeline.get("version") == 2:
                from src.game.world_constraint_freshness import (
                    build_validation_world_model,
                )

                validation_view = build_validation_world_model(state_obj)
                world_model = validation_view.world_model
                world_model.soft_context = validation_view.soft_context
                world_model.constraint_freshness = validation_view.freshness
            else:
                world_model = WorldModel.from_player_state(state_obj)
            world_model.continuity_source_state = player_state
            return cast("WorldModel", world_model)
        except Exception as exc:
            logger.warning(f"Failed to build world model from player_state dict: {exc}")
            return None
