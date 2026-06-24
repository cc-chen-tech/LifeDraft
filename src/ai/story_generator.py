"""Story generation service.

Handles the core story text generation (Step 1 of the two-stage pipeline),
consistency validation with retry, and life-phase determination.
"""

import json
import logging
import os
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional, Union

from pydantic import ValidationError

from config.prompts import get_round_event_prompt, get_story_only_prompt
from config.prompts._helpers import extract_overused_phrases
from config.prompts.story_prompts import resolve_protagonist_name
from src.ai.client import AIClient
from src.ai.harness.quality_level import PROFILES, QualityLevel
from src.ai.models import EventOption, GameEvent
from src.ai.option_generator import OptionGenerator
from src.ai.system_prompts import get_system_prompt
from src.ai.text_quality import normalize_chinese_punctuation, normalize_generated_story
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
        self._style_manifest = None
        self._prompt_builder = None
        self._style_validator = None

    @staticmethod
    def _normalize_punctuation(text: Optional[str], language: str = "zh") -> Optional[str]:
        if language != "zh" or not text:
            return text
        return normalize_chinese_punctuation(text)

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
        )

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

        # ★ 在 try 块外初始化，确保 except 块能访问已生成的故事
        story_text = None

        try:
            story_text = self.client.call(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=temperature,
                max_tokens=8192,
                stream_callback=stream_callback,
                frequency_penalty=0.4,  # ★ 轮次级别更强的反重复，因为同周多轮更容易重复
                presence_penalty=0.4,  # ★ 鼓励每轮使用不同的表达方式
            )
            story_text = normalize_generated_story(story_text, language=language)
            logger.info(f"Generated round story with {len(story_text)} characters")

            # Step 1.4: Quick rule-based validation (before AI validation)
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
                logger.warning(f"Quick validation failed: {quick_result.issues}")
                retry_lines = "\n".join(f"- {issue}" for issue in quick_result.issues)
                if language == "zh":
                    retry_prompt = (
                        prompt
                        + "\n\n【快速一致性修正 - 必须重写】\n"
                        + retry_lines
                        + "\n请重新生成本轮故事，严格使用可用人物列表和既有人设，不要新增替代关系网络。"
                    )
                else:
                    retry_prompt = (
                        prompt
                        + "\n\n[Quick Consistency Fix - Regenerate Required]\n"
                        + retry_lines
                        + "\nRegenerate this round using the available people list and existing character setup."
                    )
                if status_callback:
                    status_callback("retry")
                story_text = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=retry_prompt,
                    temperature=0.65,
                    max_tokens=8192,
                    stream_callback=stream_callback,
                    frequency_penalty=0.4,
                    presence_penalty=0.4,
                )
                story_text = normalize_generated_story(story_text, language=language)
                logger.info(
                    "Quick validation retry completed with %d characters", len(story_text)
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
                    story_text = None
                    raise ValueError(
                        "Quick validation retry failed: "
                        + "; ".join(retry_result.issues)
                    )
                if retry_result.warnings:
                    logger.info(f"Quick validation retry warnings: {retry_result.warnings}")
            elif quick_result.warnings:
                logger.info(f"Quick validation warnings: {quick_result.warnings}")

            # Step 1.5: AI-based consistency validation (if world_model is provided)
            if world_model and story_text:
                story_text = self._validate_and_retry_story(
                    story_text=story_text,
                    world_model=world_model,
                    player_state=player_state,
                    character_settings=character_settings or {},
                    language=language,
                    original_prompt=prompt,
                    sys_prompt=sys_prompt,
                    stream_callback=stream_callback,
                    status_callback=status_callback,  # ★ 传递 status_callback
                )

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

            return event  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Failed to generate round event: {e}")
            # ★ 如果故事已生成但后续步骤（如选项生成）失败，保留真实故事而非使用 fallback
            if story_text and len(story_text) > 20:
                logger.info(
                    f"Using already-generated story ({len(story_text)} chars) with fallback options"
                )
                fallback_desc = story_text
            else:
                fallback_desc = self._build_round_story_fallback(
                    player_state=player_state,
                    character_settings=character_settings or {},
                    language=language,
                    round_number=round_number,
                )
            return GameEvent(
                event_description=fallback_desc,
                options=OptionGenerator.build_contextual_fallback_options(
                    fallback_desc,
                    language=language,
                ),
            )

    # -------------------- Internal --------------------

    @staticmethod
    def _env_enabled(name: str) -> bool:
        return os.environ.get(name, "").lower() in ("true", "1", "yes")

    def _init_narrative_systems(
        self,
        style_id: str,
        player_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize optional narrative style systems when the feature flag is on."""
        del player_state
        if self._narrative_systems_initialized:
            return

        if not self._env_enabled("ENABLE_NARRATIVE_STYLE_ENGINE"):
            self._narrative_systems_initialized = True
            return

        try:
            from src.ai.narrative.style_manifest import get_style
            from src.ai.narrative.style_prompt_builder import StyleAwarePromptBuilder
            from src.ai.narrative.style_validator import StyleAwareValidator

            self._style_manifest = get_style(style_id)
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
                logger.warning("Style %r not found, style engine disabled", style_id)
        except Exception as exc:
            logger.warning("Failed to initialize narrative style systems: %s", exc)
        finally:
            self._narrative_systems_initialized = True

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

        if self._quality_profile.skip_ai_consistency_check:
            return story_text

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
            )

            if retry_story:
                logger.info(f"重试生成完成，故事长度: {len(retry_story)}")
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
                player_name=resolve_protagonist_name(player_state, character_settings, None) or "主角",
                character_settings=character_settings,
                established_facts=player_state.get("established_facts", []),
                world_model_data=player_state.get("world_model_data", {}),
            )
            return WorldModel.from_player_state(state_obj)
        except Exception as exc:
            logger.warning(f"Failed to build world model from player_state dict: {exc}")
            return None
