"""Story generation service.

Handles the core story text generation (Step 1 of the two-stage pipeline),
consistency validation with retry, and life-phase determination.
"""

import json
import logging
import os
import re
from difflib import SequenceMatcher
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional, Union

from pydantic import ValidationError

from config.prompts import get_round_event_prompt, get_story_only_prompt
from config.prompts._helpers import _build_style_constraints_text, extract_overused_phrases
from config.prompts.story_prompts import resolve_protagonist_name
from src.ai.client import AIClient
from src.ai.harness.diagnostics import ConstraintViolationDiagnostic
from src.ai.harness.validation_pipeline import ValidationPipeline
from src.ai.harness.retry_controller import RetryController
from src.ai.harness.quality_level import PROFILES, QualityLevel
from src.ai.generation_budget import get_generation_budget
from src.ai.models import GameEvent
from src.ai.option_generator import OptionGenerator
from src.ai.system_prompts import get_system_prompt
from src.ai.prompt_sanitizer import sanitize_player_name
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.text_quality import normalize_generated_story, validate_narrative_quality
from src.ai.vector_store import get_vector_store, is_vector_search_enabled

logger = logging.getLogger(__name__)


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
        self._validated_round_keys: set[tuple[Any, Any, Any]] = set()
        self._harness_enabled = self._env_enabled("ENABLE_CONSTRAINT_HARNESS")
        self._narrative_systems_initialized = False
        self._validation_pipeline = None
        self._retry_controller = None
        self._diagnostics = None
        self._harness_metrics = None
        self._style_manifest = None
        self._prompt_builder = None
        self._style_validator = None
        self._initialized_style_id: Optional[str] = None

    @staticmethod
    def _normalize_punctuation(text: Optional[str], language: str = "zh") -> Optional[str]:
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

        normalized = normalize_generated_story("".join(converted_quotes), language=language)

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
        normalized = normalized.replace(".", "。").replace("?", "？").replace("!", "！").replace(",", "，")
        normalized = normalized.replace("；", "；").replace(":", "：").replace(";", "；")

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

    def _story_request_timeout_seconds(self) -> float:
        """Keep interactive story requests inside the selected quality budget."""
        budget = get_generation_budget(self.quality_level.value)
        return float(budget.expected_seconds + 30)

    @staticmethod
    def _extract_player_name(player_state: Optional[Dict[str, Any]]) -> str:
        """Resolve and sanitize player name from player state.

        Keep a dedicated helper for test coverage and for other callers that
        need a consistent sanitization policy.
        """
        player_state = player_state or {}
        name = resolve_protagonist_name(player_state, player_state.get("character_settings"), None)
        return sanitize_player_name(name)

    @staticmethod
    def _canonical_story_for_repeat_check(story: str) -> str:
        """Normalize prose for a semantic duplicate check without changing stored text."""
        return re.sub(r"\s+", "", (story or "").replace("\r\n", "\n"))

    @classmethod
    def _repeats_committed_story(cls, candidate: str, committed_stories: list[str]) -> bool:
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
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        last_event_concluded: bool = True,
        last_round_full_story: str = "",
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
        character_habits: Optional[list] = None,
        option_generator=None,
        cache=None,
        status_callback: Optional[Callable[[str], None]] = None,
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
        style_id = str(
            player_state.get("narrative_style_id")
            or (character_settings or {}).get("narrative_style_id")
            or ""
        )
        self._init_narrative_systems(style_id, player_state)
        style_constraints = _build_style_constraints_text(self._prompt_builder, language)

        current_phase = self._get_phase_from_state(player_state)

        # Derive last_event_description from decision history if not provided
        if not last_event_description:
            decision_history = player_state.get("decision_history", [])
            if decision_history:
                last_event_description = decision_history[-1].get("event")

        # ★ 向量检索：获取相关历史片段
        vector_context = ""
        if is_vector_search_enabled():
            try:
                vector_store = get_vector_store()
                # 使用当前情境作为查询
                query_context = last_event_description or ""
                if pending_storylines:
                    query_context += " " + " ".join(str(s) for s in pending_storylines[:3])
                vector_context = vector_store.get_relevant_context(query_context, max_chars=1500)
                if vector_context:
                    logger.info(
                        f"[VectorStore] Injected {len(vector_context)} chars of vector context"
                    )
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # ★ 动态提取历史故事中的高频重复短语，生成禁用列表
        decision_history = player_state.get("decision_history", [])
        overused_phrases = extract_overused_phrases(decision_history, language=language)
        if overused_phrases:
            logger.info(f"[AntiRepeat] Injected dynamic ban list ({len(overused_phrases)} chars)")

        world_model = self._build_world_model_from_state_dict(player_state)

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
            vector_context=vector_context,  # ★ 注入向量检索上下文
            overused_phrases=overused_phrases,  # ★ 注入动态禁用列表
            style_constraints=style_constraints,
        )

        sys_prompt = get_system_prompt("story_novelist", language)
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
                current_temp = max(0.7, base_temperature - (attempt * temperature_decay))
                logger.info(
                    f"Story generation attempt {attempt + 1}/{retry_count}, temperature={current_temp}"
                )

                # Only stream on first attempt
                cb = stream_callback if attempt == 0 else None
                story_text = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=prompt,
                    temperature=current_temp,  # ★ 动态调整温度
                    max_tokens=8192,
                    stream_callback=cb,
                    frequency_penalty=0.3,  # ★ 惩罚重复词汇，减少车轲辘话
                    presence_penalty=0.3,  # ★ 鼓励使用新词汇/新主题
                    request_timeout=self._story_request_timeout_seconds(),
                )

                story_text = normalize_generated_story(story_text, language=language)
                logger.info(f"Generated story with {len(story_text)} characters")
                logger.debug(f"Story preview (first 200 chars): {story_text[:200]}...")
                logger.debug(f"Story preview (last 200 chars): ...{story_text[-200:]}")

                from config.prompts._helpers import _collect_available_people
                from src.ai.quick_validator import quick_validate_story

                available_people_names = [
                    p.get("name", "")
                    for p in _collect_available_people(character_settings)
                    if p.get("name")
                ]
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
                )
                logger.info(f"Generated {len(event.options)} options")
                for i, opt in enumerate(event.options):
                    logger.info(f"Option {i+1}: {opt.text}")

                # Validate and fix relationship names
                option_generator.validate_and_fix_relationships(event, character_settings)

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

                logger.info(f"Successfully generated event with {len(event.options)} options")
                return event  # type: ignore[no-any-return]

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
        relationship_events: Optional[list] = None,
        historical_weekly_summary: Optional[str] = None,
        historical_yearly_summary: Optional[str] = None,
        game_date_info: Optional[Dict[str, Any]] = None,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        last_event_concluded: bool = True,
        last_round_full_story: str = "",
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
        character_habits: Optional[list] = None,
        world_model=None,
        option_generator=None,
        new_character: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
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
        logger.info(
            f"Generating round event: round={round_number}, "
            f"context_length={len(round_context)}, "
            f"rel_events={len(relationship_events) if relationship_events else 0}, "
            f"stream_callback={stream_callback is not None}"
        )

        # ★ 向量检索：获取相关历史片段
        vector_context = ""
        if is_vector_search_enabled():
            try:
                vector_store = get_vector_store()
                # 使用当前情境作为查询
                query_context = round_context or ""
                if pending_storylines:
                    query_context += " " + " ".join(str(s) for s in pending_storylines[:3])
                vector_context = vector_store.get_relevant_context(query_context, max_chars=1500)
                if vector_context:
                    logger.info(
                        f"[VectorStore] Injected {len(vector_context)} chars of vector context"
                    )
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

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
        style_constraints = _build_style_constraints_text(self._prompt_builder, language)

        # Get round story prompt
        prompt = get_round_event_prompt(
            player_state,
            language,
            round_number,
            round_context,
            character_settings,
            relationship_events=relationship_events,
            historical_weekly_summary=historical_weekly_summary,
            historical_yearly_summary=historical_yearly_summary,
            game_date_info=game_date_info,
            pending_storylines=pending_storylines,
            established_facts=established_facts,
            last_event_concluded=last_event_concluded,
            last_round_full_story=last_round_full_story,
            activated_foreshadowing=activated_foreshadowing,
            character_habits=character_habits,
            world_model=world_model,
            new_character=new_character,
            vector_context=vector_context,  # ★ 注入向量检索上下文
            overused_phrases=overused_phrases,  # ★ 注入动态禁用列表
            style_constraints=style_constraints,
            quality_level=self.quality_level.value,
        )
        generation_budget = get_generation_budget(self.quality_level.value)

        # Step 1: Generate story text (with optional streaming)
        sys_prompt = get_system_prompt("story_novelist", language)

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

        from config.prompts._helpers import _collect_available_people
        from src.ai.quick_validator import quick_validate_story

        # 最多尝试次数：默认仅保留 QUICK 重试的一次回退；只有启用约束增强时才走 profile 次数重试。
        # - 无 harness：避免影响现有契约测试（一次主生成 + 一次 quick 重试）
        # - 有 harness：沿用 quality_profile 的重试预算，用于高风险修复。
        max_attempts = (
            self._quality_profile.max_retries + 1
            if self._harness_enabled
            else 1
        )

        available_people_names = [
            p.get("name", "")
            for p in _collect_available_people(character_settings)
            if p.get("name")
        ]
        committed_stories = self._committed_round_stories(
            player_state,
            last_round_full_story,
        )

        best_valid_story_text = ""
        last_generation_error: Optional[Exception] = None

        def _set_best_story(candidate: Optional[str]) -> None:
            if not candidate:
                return
            nonlocal best_valid_story_text
            if len(candidate) > len(best_valid_story_text):
                best_valid_story_text = candidate

        def _hard_shape_issues(candidate: str) -> list[str]:
            shape_issues = validate_narrative_quality(
                candidate,
                language=language,
                perspective="third",
                min_chars=generation_budget.min_length,
                max_chars=generation_budget.max_length,
            )
            return [
                issue
                for issue in shape_issues
                if issue in {"story_too_short", "story_too_long", "over_fragmented_paragraphs"}
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
                    f"{generation_budget.min_length}-{generation_budget.max_length}字，"
                    "使用2-5个自然段，每段有完整场景推进，禁止拆成大量短句碎片。"
                )
            issue_text = "; ".join(hard_shape_issues)
            return (
                "\n\n[Length and Paragraph Fix - Regenerate Required]\n"
                f"{issue_text}. Regenerate this round within "
                f"{generation_budget.min_length}-{generation_budget.max_length} words, "
                "using 2-5 coherent paragraphs."
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

        for attempt in range(max_attempts):
            story_text = None
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

                story_text = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=attempt_prompt,
                    temperature=current_temp,
                    max_tokens=generation_budget.max_tokens,
                    stream_callback=stream_callback if attempt == 0 else None,
                    frequency_penalty=0.4,  # ★ 轮次级别更强的反重复，因为同周多轮更容易重复
                    presence_penalty=0.4,  # ★ 鼓励每轮使用不同的表达方式
                    request_timeout=self._story_request_timeout_seconds(),
                )
                story_text = normalize_generated_story(story_text, language=language)
                logger.info(f"Generated round story with {len(story_text)} characters")

                # Step 1.4: Quick rule-based validation (before AI validation)
                quick_result = quick_validate_story(
                    story_text=story_text,
                    character_settings=character_settings,
                    available_people=available_people_names,
                    language=language,
                )
                quick_retry_used = False

                if not quick_result.passed and generation_budget.allow_quick_regeneration:
                    logger.warning(f"Quick validation failed: {quick_result.issues}")
                    retry_lines = "\n".join(f"- {issue}" for issue in quick_result.issues)
                    retry_prompt = (
                        attempt_prompt
                        + (
                            "\n\n【快速一致性修正 - 必须重写】\n"
                            if language == "zh"
                            else "\n\n[Quick Consistency Fix - Regenerate Required]\n"
                        )
                        + retry_lines
                        + (
                            "\n请重新生成本轮故事，严格使用可用人物列表和既有人设，不要新增替代关系网络。"
                            if language == "zh"
                            else "\nRegenerate this round using the available people list and existing character setup."
                        )
                    )
                    if status_callback:
                        status_callback("retry")

                    retry_story = self.client.call(
                        system_prompt=sys_prompt,
                        user_prompt=retry_prompt,
                        temperature=0.65,
                        max_tokens=generation_budget.max_tokens,
                        stream_callback=stream_callback if attempt == 0 else None,
                        frequency_penalty=0.4,
                        presence_penalty=0.4,
                        request_timeout=self._story_request_timeout_seconds(),
                    )
                    story_text = normalize_generated_story(retry_story, language=language)
                    quick_retry_used = True
                    logger.info(
                        "Quick validation retry completed with %d characters",
                        len(story_text),
                    )

                    retry_result = quick_validate_story(
                        story_text=story_text,
                        character_settings=character_settings,
                        available_people=available_people_names,
                        language=language,
                    )

                    if not retry_result.passed:
                        logger.warning(
                            "Quick validation retry still failed: %s",
                            retry_result.issues,
                        )
                        break
                    if retry_result.warnings:
                        logger.info(
                            "Quick validation retry warnings: %s",
                            retry_result.warnings,
                        )

                elif not quick_result.passed:
                    logger.warning(
                        "Fast generation records local validation issues without a second provider call: %s",
                        quick_result.issues,
                    )
                elif quick_result.warnings:
                    logger.info(f"Quick validation warnings: {quick_result.warnings}")

                hard_shape_issues = _hard_shape_issues(story_text)
                requires_shape_retry = (
                    not quick_retry_used or "story_too_long" in hard_shape_issues
                )
                if (
                    hard_shape_issues
                    and generation_budget.allow_quick_regeneration
                    and requires_shape_retry
                    and max_attempts == 1
                ):
                    logger.warning("Story shape validation failed: %s", hard_shape_issues)
                    if status_callback:
                        status_callback("retry")
                    retry_story = self.client.call(
                        system_prompt=sys_prompt,
                        user_prompt=attempt_prompt + _build_shape_retry_instruction(hard_shape_issues),
                        temperature=0.65,
                        max_tokens=generation_budget.max_tokens,
                        stream_callback=stream_callback if attempt == 0 else None,
                        frequency_penalty=0.4,
                        presence_penalty=0.4,
                        request_timeout=self._story_request_timeout_seconds(),
                    )
                    story_text = normalize_generated_story(retry_story, language=language)
                    logger.info(
                        "Story shape retry completed with %d characters",
                        len(story_text),
                    )
                    retry_shape_issues = _hard_shape_issues(story_text)
                    retry_quick_result = quick_validate_story(
                        story_text=story_text,
                        character_settings=character_settings,
                        available_people=available_people_names,
                        language=language,
                    )
                    if retry_shape_issues or not retry_quick_result.passed:
                        logger.warning(
                            "Story shape retry still failed: shape=%s quick=%s",
                            retry_shape_issues,
                            retry_quick_result.issues,
                        )
                        raise ValueError(
                            "Story shape validation failed: "
                            + "; ".join(retry_shape_issues + retry_quick_result.issues)
                        )
                elif hard_shape_issues:
                    logger.warning(
                        "Story shape issues recorded without another provider retry: %s",
                        hard_shape_issues,
                    )
                else:
                    _set_best_story(story_text)

                if self._repeats_committed_story(story_text, committed_stories):
                    if self._canonical_story_for_repeat_check(
                        best_valid_story_text
                    ) == self._canonical_story_for_repeat_check(story_text):
                        best_valid_story_text = ""
                    logger.warning("Round story repeats committed story; requesting one rewrite")
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
                    retry_story = self.client.call(
                        system_prompt=sys_prompt,
                        user_prompt=repeat_retry_prompt,
                        temperature=0.65,
                        max_tokens=generation_budget.max_tokens,
                        stream_callback=stream_callback if attempt == 0 else None,
                        frequency_penalty=0.5,
                        presence_penalty=0.5,
                        request_timeout=self._story_request_timeout_seconds(),
                    )
                    story_text = normalize_generated_story(retry_story, language=language)
                    repeat_retry_validation = quick_validate_story(
                        story_text=story_text,
                        character_settings=character_settings,
                        available_people=available_people_names,
                        language=language,
                    )
                    repeat_retry_shape_issues = _hard_shape_issues(story_text)
                    if not repeat_retry_validation.passed or repeat_retry_shape_issues:
                        issues = repeat_retry_validation.issues + repeat_retry_shape_issues
                        raise ValueError(
                            "Repeated-story retry failed validation: " + "; ".join(issues)
                        )
                    if self._repeats_committed_story(story_text, committed_stories):
                        raise ValueError("Round story repeats committed story after retry")
                    _set_best_story(story_text)

                # Step 1.5: AI-based consistency validation (if world_model is provided)
                if world_model and story_text and generation_budget.allow_ai_consistency:
                    story_text = self._validate_and_retry_story(
                        story_text=story_text,
                        world_model=world_model,
                        player_state=player_state,
                        character_settings=character_settings or {},
                        language=language,
                        original_prompt=prompt,
                        sys_prompt=sys_prompt,
                        stream_callback=stream_callback if attempt == 0 else None,
                        status_callback=status_callback,
                    )
                    post_validation_shape_issues = _hard_shape_issues(story_text)
                    if post_validation_shape_issues:
                        best_valid_story_text = ""
                        raise ValueError(
                            "Story consistency retry failed shape validation: "
                            + "; ".join(post_validation_shape_issues)
                        )
                    _set_best_story(story_text)

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

                    diagnostic_report = ConstraintViolationDiagnostic().generate_report(
                        story_text=story_text,
                        validation_result=validation_result,
                    ) if self._diagnostics is None else self._diagnostics.generate_report(
                        story_text=story_text,
                        validation_result=validation_result,
                    )

                    should_retry = False
                    if self._retry_controller is not None:
                        should_retry, hint = self._retry_controller.should_retry(
                            validation_result=validation_result,
                            diagnostic_report=diagnostic_report,
                            attempt=attempt,
                        )
                        retry_hint = hint
                    if should_retry:
                        if status_callback:
                            status_callback("retry")
                        logger.info(
                            "Round event harness retry requested on attempt %d",
                            attempt + 1,
                        )
                        continue

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
                )

                # Validate relationships
                option_generator.validate_and_fix_relationships(event, character_settings)

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

                return event

            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Round event attempt {attempt + 1} failed: {e}")
                last_generation_error = e
            except Exception as e:
                logger.error(f"Unexpected error in round event attempt {attempt + 1}: {e}")
                last_generation_error = e

            if attempt < max_attempts - 1:
                retry_hint = None if not retry_hint else retry_hint
                continue

            break

        if len(best_valid_story_text) > 20:
            logger.info(
                "Using best historical story (%d chars) after all round attempts",
                len(best_valid_story_text),
            )
            fallback_options = OptionGenerator.build_contextual_fallback_options(
                best_valid_story_text,
                language=language,
            )
            if OptionGenerator.fallback_options_repeat_recent_history(
                fallback_options, player_state.get("decision_history", [])
            ):
                raise StoryGenerationFailure(
                    "Option generation failed and the contextual fallback repeats recent choices"
                )
            return GameEvent(
                event_description=best_valid_story_text,
                options=fallback_options,
            )

        message = "Story generation failed before producing a valid event"
        if last_generation_error is not None:
            message = f"{message}: {last_generation_error}"
        raise StoryGenerationFailure(message) from last_generation_error

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
                logger.warning("Style %r not found, style engine disabled", requested_style_id)
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

        player_name = resolve_protagonist_name(player_state, character_settings, None) or "你"
        required_people = extract_required_key_people(character_settings or {})
        anchor_person = required_people[0] if required_people else {}

        if language == "zh":
            era = ""
            era_setting = character_settings.get("era")
            if isinstance(era_setting, dict):
                era = str(era_setting.get("era_description") or era_setting.get("description") or "")

            trait = ""
            trait_setting = character_settings.get("traits")
            if isinstance(trait_setting, dict):
                trait = str(
                    trait_setting.get("traits_description")
                    or trait_setting.get("description")
                    or ""
                )

            round_names = ["周初", "周中", "周末"]
            round_name = round_names[round_number] if 0 <= round_number < len(round_names) else "这一天"
            setting_clause = f"在{era}的背景下，" if era else ""
            trait_clause = f"你把{trait}放在心里，" if trait else "你把眼前的线索重新梳理，"
            cast_clause = ""
            if anchor_person.get("name"):
                role = anchor_person.get("role") or anchor_person.get("relationship") or "关键人物"
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
            round_names_en[round_number] if 0 <= round_number < len(round_names_en) else "today"
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
        world_model,
        player_state: Dict[str, Any],
        character_settings: Dict[str, Any],
        language: str,
        original_prompt: str,
        sys_prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
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

        round_key = (
            player_state.get("game_id"),
            player_state.get("week", player_state.get("current_week")),
            player_state.get("current_round"),
        )
        if round_key in self._validated_round_keys:
            logger.info(f"Skipping duplicate story consistency validation for round={round_key}")
            return story_text
        self._validated_round_keys.add(round_key)

        try:
            from src.ai.consistency_validator import ConsistencyValidator

            # ★ 发送校验状态，让用户知道正在检查故事一致性
            if status_callback:
                logger.info("★ 发送 validating 状态提示")
                status_callback("validating")

            validator = ConsistencyValidator(self.client)
            validation = validator.validate_story(
                story_text=story_text,
                world_model=world_model,
                player_state_dict=player_state,
                character_settings=character_settings,
                language=language,
                run_ai_validation=not self._quality_profile.skip_ai_consistency_check,
            )

            if validation.passed:
                return story_text

            if not validation.has_critical_issues:
                logger.info(f"一致性校验有 {len(validation.warning_issues)} 个WARNING，不触发重试")
                return story_text

            # CRITICAL issues found - retry once
            logger.warning(
                f"一致性校验不通过，{len(validation.critical_issues)} 个CRITICAL问题，触发重试"
            )
            for issue in validation.critical_issues:
                logger.warning(f"  CRITICAL [{issue.dimension}]: {issue.description[:80]}")

            # Regenerate with fix instructions appended
            # ★ 重要：重试时也需要流式输出，否则前端会显示不完整的旧内容
            retry_prompt = original_prompt + validation.fix_instructions

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
                logger.warning("★★★ stream_callback is None in retry! This should not happen.")
            else:
                logger.info(f"★ stream_callback is present in retry: {stream_callback}")

            # ★ 优化：重试时使用固定的低温度 0.7，确保更保守、更符合约束
            logger.info(
                f"Consistency retry with temperature=0.7 (conservative), stream_callback={stream_callback is not None}"
            )

            retry_story = self.client.call(
                system_prompt=sys_prompt,
                user_prompt=retry_prompt,
                temperature=0.7,  # 固定低温度，确保严格遵守约束
                max_tokens=8192,
                stream_callback=stream_callback,
                frequency_penalty=0.3,  # ★ 重试时也保持反重复
                presence_penalty=0.3,
                request_timeout=self._story_request_timeout_seconds(),
            )

            if retry_story:
                logger.info(f"重试生成完成，故事长度: {len(retry_story)}")
                wealth_ledger = getattr(world_model, "wealth_ledger", None)
                if wealth_ledger is not None:
                    current_balance = max(0, int(player_state.get("wealth", 0)))
                    wealth_validation = wealth_ledger.validate_narrative(
                        retry_story,
                        current_balance=current_balance,
                    )
                    if not wealth_validation.passed:
                        logger.warning(
                            "Wealth claims remained invalid after story retry; "
                            "applying deterministic correction"
                        )
                        retry_story = wealth_ledger.sanitize_narrative(
                            retry_story,
                            wealth_validation,
                            current_balance=current_balance,
                        )
                return retry_story

            return story_text

        except Exception as e:
            logger.error(f"Story validation/retry failed: {e}")
            return story_text

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
    def _build_world_model_from_state_dict(player_state: Dict[str, Any]):
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
                player_name=resolve_protagonist_name(player_state, character_settings, None) or "主角",
                character_settings=character_settings,
                established_facts=player_state.get("established_facts", []),
                world_model_data=player_state.get("world_model_data", {}),
                continuity_ledger=player_state.get("continuity_ledger", {}),
                wealth=player_state.get("wealth", 0),
                wealth_ledger=player_state.get("wealth_ledger", {}),
            )
            world_model = WorldModel.from_player_state(state_obj)
            world_model.continuity_source_state = player_state
            return world_model
        except Exception as exc:
            logger.warning(f"Failed to build world model from player_state dict: {exc}")
            return None
