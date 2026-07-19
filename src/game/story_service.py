"""Story continuation, compression, and custom choice result generation."""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from src.ai.generator import EventGenerator
from src.ai.prompt_sanitizer import sanitize_custom_action, sanitize_user_choice
from src.ai.story_exceptions import StoryContinuationFailure
from src.ai.system_prompts import get_system_prompt
from src.ai.text_quality import normalize_generated_story

logger = logging.getLogger(__name__)

# A choice still needs time for local and world-model validation after prose
# generation, so each provider attempt must remain below the SSE lifecycle cap.
STORY_CONTINUATION_REQUEST_TIMEOUT_SECONDS = 75.0


class StoryService:
    """Handles story continuation generation, compression, and custom choice results."""

    def __init__(self, ai_generator: EventGenerator, language: str = "zh"):
        self.ai_generator = ai_generator
        self.language = language

    def generate_story_continuation(
        self,
        event_description: str,
        chosen_option: str,
        effects: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]] = None,
        player_state: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        is_custom: bool = False,
        active_wealth_transaction_id: Optional[str] = None,
    ) -> str:
        """
        Generate a detailed story continuation after the player's choice.

        Creates an immersive narrative describing what happens immediately
        after the player makes their choice, including scene descriptions,
        character reactions, and dialogue.

        ★ 包含一致性校验：如果生成的故事与世界模型存在逻辑冲突，
        会自动重试一次并注入修正指令。

        Args:
            event_description: The original event/story text
            chosen_option: The text of the player's chosen option
            effects: The effects dictionary from the chosen option
            character_settings: Character background settings
            player_state: Player state dict for consistency validation
            stream_callback: Optional callback for streaming text chunks
            status_callback: Optional callback for status updates (e.g., 'retrying')

        Returns:
            A 500-800 character story continuation
        """
        # 清洗用户选择，防止 prompt 注入
        sanitized_chosen_option = sanitize_user_choice(chosen_option)

        from config.prompts import get_result_generation_prompt

        try:
            prompt = get_result_generation_prompt(
                event_description=event_description,
                chosen_option=sanitized_chosen_option,
                effects=effects,
                language=self.language,
                character_settings=character_settings or {},  # type: ignore[arg-type]
                is_custom=is_custom,
            )

            wealth_ledger = None
            current_balance = 0
            if player_state:
                from src.game.wealth_ledger import WealthLedger

                wealth_ledger = WealthLedger.from_player_state(player_state)
                current_balance = max(0, int(player_state.get("wealth", 0)))
                prompt += wealth_ledger.build_constraints_text(
                    current_balance, self.language
                )

            sys_prompt = get_system_prompt("story_continuation", self.language)
            continuation = self.ai_generator.generate_completion(
                prompt=prompt,
                system_prompt=sys_prompt,
                temperature=0.8,
                max_tokens=4096,
                stream_callback=stream_callback,
                retry_count=1,
                language=self.language,
                request_timeout=STORY_CONTINUATION_REQUEST_TIMEOUT_SECONDS,
            )
            logger.debug(f"Generated story continuation: {len(continuation)} chars")

            continuation = self._quick_validate_and_retry_continuation(
                continuation=continuation,
                character_settings=character_settings or {},
                player_name=str((player_state or {}).get("player_name") or "").strip(),
                original_prompt=prompt,
                sys_prompt=sys_prompt,
                stream_callback=stream_callback,
                status_callback=status_callback,
            )

            if wealth_ledger is not None:
                continuation = self._validate_and_retry_wealth_narrative(
                    continuation=continuation,
                    ledger=wealth_ledger,
                    current_balance=current_balance,
                    active_transaction_id=active_wealth_transaction_id,
                    original_prompt=prompt,
                    sys_prompt=sys_prompt,
                    status_callback=status_callback,
                )

            # ★ 一致性校验：检查结果故事是否与世界模型一致
            if player_state and continuation:
                continuation = self._validate_and_retry_continuation(
                    continuation=continuation,
                    player_state=player_state,
                    character_settings=character_settings or {},
                    original_prompt=prompt,
                    sys_prompt=sys_prompt,
                    stream_callback=stream_callback,
                    status_callback=status_callback,
                )

            return normalize_generated_story(continuation, language=self.language)

        except StoryContinuationFailure:
            raise
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"Failed to generate story continuation: {e}")
            raise StoryContinuationFailure(
                f"Story continuation generation failed: {e}"
            ) from e
        except Exception as e:
            logger.exception(f"Unexpected error generating story continuation: {e}")
            raise StoryContinuationFailure(
                f"Story continuation generation failed: {e}"
            ) from e

    def _validate_and_retry_wealth_narrative(
        self,
        *,
        continuation: str,
        ledger: Any,
        current_balance: int,
        active_transaction_id: Optional[str],
        original_prompt: str,
        sys_prompt: str,
        status_callback: Optional[Callable[[str], None]],
    ) -> str:
        validation = ledger.validate_narrative(
            continuation,
            current_balance=current_balance,
            active_transaction_id=active_transaction_id,
        )
        if validation.passed:
            return continuation
        if status_callback:
            status_callback("retrying")
            status_callback("retry")
        retry = self.ai_generator.generate_completion(
            prompt=original_prompt + validation.fix_instructions,
            system_prompt=sys_prompt,
            temperature=0.6,
            max_tokens=4096,
            retry_count=1,
            language=self.language,
            request_timeout=STORY_CONTINUATION_REQUEST_TIMEOUT_SECONDS,
        )
        retry_validation = ledger.validate_narrative(
            retry,
            current_balance=current_balance,
            active_transaction_id=active_transaction_id,
        )
        if retry_validation.passed:
            return retry
        logger.warning(
            "Wealth claims remained unsupported after retry; applying deterministic correction: %s",
            [issue.code for issue in retry_validation.issues],
        )
        return ledger.sanitize_narrative(
            retry,
            retry_validation,
            current_balance=current_balance,
        )

    def _quick_validate_and_retry_continuation(
        self,
        continuation: str,
        character_settings: Dict[str, Any],
        player_name: str,
        original_prompt: str,
        sys_prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Fast local validation for post-choice story continuations."""
        if not continuation:
            return continuation

        from config.prompts._helpers import _collect_available_people
        from src.ai.quick_validator import quick_validate_story

        available_people_names = [
            p.get("name", "")
            for p in _collect_available_people(character_settings)
            if p.get("name")
        ]
        if player_name and player_name not in available_people_names:
            available_people_names.append(player_name)
        result = quick_validate_story(
            story_text=continuation,
            character_settings=character_settings,
            available_people=available_people_names,
            language=self.language,
        )
        if result.passed:
            return continuation

        logger.warning("[StoryContinuation] Quick validation failed: %s", result.issues)
        if status_callback:
            status_callback("retrying")
            status_callback("retry")

        retry_lines = "\n".join(f"- {issue}" for issue in result.issues)
        if self.language == "zh":
            retry_prompt = (
                original_prompt
                + "\n\n【选择后续写一致性修正 - 必须重写】\n"
                + "上一版选择后续写存在以下问题：\n"
                + retry_lines
                + "\n请重新续写玩家选择之后的故事，严格遵守角色设定、现实主义世界边界和预设关键人物关系。"
            )
        else:
            retry_prompt = (
                original_prompt
                + "\n\n[Choice Continuation Consistency Fix - Regenerate Required]\n"
                + "The previous post-choice continuation had these issues:\n"
                + retry_lines
                + "\nRewrite the continuation after the player's choice, strictly following the character setup, world boundary, and preset key people relationships."
            )

        retry_continuation = self.ai_generator.generate_completion(
            prompt=retry_prompt,
            system_prompt=sys_prompt,
            temperature=0.65,
            max_tokens=4096,
            stream_callback=stream_callback,
            retry_count=1,
            language=self.language,
            request_timeout=STORY_CONTINUATION_REQUEST_TIMEOUT_SECONDS,
        )
        retry_result = quick_validate_story(
            story_text=retry_continuation,
            character_settings=character_settings,
            available_people=available_people_names,
            language=self.language,
        )
        if retry_result.passed:
            return retry_continuation

        logger.warning(
            "[StoryContinuation] Quick validation retry still failed: %s",
            retry_result.issues,
        )
        if self._has_only_perspective_issues(retry_result.issues):
            # A committed choice must not be stranded because the model used a
            # first-person sentence after an otherwise successful retry. Keep
            # the continuation visible and preserve the diagnostic in logs.
            logger.warning(
                "[StoryContinuation] Accepting retry with perspective-only issues"
            )
            return retry_continuation
        raise ValueError(
            "Choice continuation quick validation failed: "
            + "; ".join(retry_result.issues)
        )

    @staticmethod
    def _has_only_perspective_issues(issues: List[str]) -> bool:
        """Return whether validation found only non-blocking perspective drift."""
        if not issues:
            return False
        perspective_markers = ("第一人称", "first-person")
        return all(any(marker in issue for marker in perspective_markers) for issue in issues)

    def generate_fallback_continuation(
        self, chosen_option: str, effects: Dict[str, Any]
    ) -> str:
        """
        Generate a simple fallback continuation when AI generation fails.

        Args:
            chosen_option: The player's choice text
            effects: The effects dictionary

        Returns:
            A basic continuation description
        """
        if self.language == "zh":
            parts = [f"你选择了{chosen_option}。"]

            if effects.get("mood", 0) > 0:
                parts.append("这个决定让你心情感到舒畅。")
            elif effects.get("mood", 0) < 0:
                parts.append("你的心情因此有些波动。")

            if effects.get("knowledge", 0) > 0:
                parts.append("你从中获得了一些领悟。")

            if effects.get("relationships"):
                for name, change in effects["relationships"].items():
                    if change > 0:
                        parts.append(f"你与{name}的关系变得更近了。")
                    elif change < 0:
                        parts.append(f"你与{name}的关系产生了一些微妙的变化。")

            return "".join(parts)
        else:
            parts = [f"You chose to {chosen_option}."]

            if effects.get("mood", 0) > 0:
                parts.append(" This decision lifted your spirits.")
            elif effects.get("mood", 0) < 0:
                parts.append(" Your mood shifted slightly.")

            if effects.get("knowledge", 0) > 0:
                parts.append(" You gained some insights from this experience.")

            return "".join(parts)

    def _validate_and_retry_continuation(
        self,
        continuation: str,
        player_state: Dict[str, Any],
        character_settings: Dict[str, Any],
        original_prompt: str,
        sys_prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Validate story continuation consistency and retry if CRITICAL issues found.

        Args:
            continuation: The generated story continuation
            player_state: Player state dict for building world model
            character_settings: Character settings
            original_prompt: Original generation prompt
            sys_prompt: System prompt
            stream_callback: Optional streaming callback for retry
            status_callback: Optional status callback

        Returns:
            Original or regenerated continuation
        """
        try:
            from src.ai.consistency_validator import ConsistencyValidator
            from src.game.world_model import WorldModel

            # ★ 从 player_state 构建 WorldModel
            world_model = None
            try:
                # 需要将 dict 转换为 PlayerState 对象
                from src.game.state.player_state import PlayerState

                if isinstance(player_state, dict):
                    ps_obj = PlayerState(**player_state) if player_state else None
                else:
                    ps_obj = player_state

                if ps_obj:
                    world_model = WorldModel.from_player_state(ps_obj)
                    logger.debug("[StoryContinuation] Built WorldModel for validation")
            except (ImportError, ValueError, TypeError, KeyError) as e:
                logger.warning(f"[StoryContinuation] Failed to build WorldModel: {e}")
                return continuation
            except Exception as e:
                logger.exception(
                    f"[StoryContinuation] Unexpected error building WorldModel: {e}"
                )
                return continuation

            if not world_model:
                return continuation

            validator = ConsistencyValidator(self.ai_generator.ai_client)
            validation = validator.validate_story(
                story_text=continuation,
                world_model=world_model,
                player_state_dict=(
                    player_state
                    if isinstance(player_state, dict)
                    else player_state.to_dict()
                ),
                character_settings=character_settings,
                language=self.language,
            )

            if validation.passed:
                return continuation

            if not validation.has_critical_issues:
                logger.info(
                    f"[StoryContinuation] 一致性校验有 {len(validation.warning_issues)} 个WARNING，不触发重试"
                )
                return continuation

            # CRITICAL issues found - retry once
            logger.warning(
                f"[StoryContinuation] 一致性校验不通过，{len(validation.critical_issues)} 个CRITICAL问题，触发重试"
            )
            for issue in validation.critical_issues:
                logger.warning(f"  CRITICAL [{issue.dimension}]: {issue.description}")

            # 发送状态提示
            if status_callback:
                status_callback("retrying")
                status_callback("retry")

            # 重试时注入修正指令
            retry_prompt = original_prompt + validation.fix_instructions

            retry_continuation = self.ai_generator.generate_completion(
                prompt=retry_prompt,
                system_prompt=sys_prompt,
                temperature=0.7,  # 降低温度确保更保守
                max_tokens=4096,
                stream_callback=stream_callback,
                retry_count=1,
                language=self.language,
                request_timeout=STORY_CONTINUATION_REQUEST_TIMEOUT_SECONDS,
            )

            if retry_continuation:
                logger.info(
                    f"[StoryContinuation] 重试生成完成，故事长度: {len(retry_continuation)}"
                )
                return retry_continuation

            return continuation

        except (ImportError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"[StoryContinuation] Validation/retry failed: {e}")
            return continuation
        except Exception as e:
            logger.exception(
                f"[StoryContinuation] Unexpected error during validation/retry: {e}"
            )
            return continuation

    def compress_story(
        self,
        story: str,
        choice: str,
        pending_storylines: Optional[List] = None,
        established_facts: Optional[List] = None,
        character_habits: Optional[List] = None,
    ) -> Dict[str, Any]:
        """
        Compress a story into a 100-character summary, evaluate storyline status,
        extract/update world facts, and track character habit changes.

        Args:
            story: The full story text
            choice: The player's choice text
            pending_storylines: Current pending storylines for evaluation
            established_facts: Current established world facts for consistency tracking
            character_habits: Current character habits for tracking changes

        Returns:
            Dict with 'summary', 'storyline_updates', 'fact_updates', 'habit_updates', etc.
        """
        return self.ai_generator.compress_story(
            story,
            choice,
            self.language,
            pending_storylines,
            established_facts,
            character_habits,
        )

    def compress_narrative(
        self, story: str, choice: str, pending_storylines: Optional[List] = None
    ) -> Dict[str, Any]:
        """Narrative compression only (parallel-friendly). Returns summary + event_concluded + storyline_updates."""
        return self.ai_generator.compress_narrative(
            story, choice, self.language, pending_storylines
        )

    def extract_world_updates(
        self,
        story: str,
        choice: str,
        established_facts: Optional[List] = None,
        character_habits: Optional[List] = None,
    ) -> Dict[str, Any]:
        """World state extraction only (parallel-friendly). Returns fact/habit/location/career/commitment/causal/foreshadowing updates."""
        return self.ai_generator.extract_world_updates(
            story, choice, self.language, established_facts, character_habits
        )

    def generate_custom_choice_effects(
        self,
        event_description: str,
        custom_text: str,
        character_settings: Optional[Dict[str, Any]] = None,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Use AI to generate ONLY the attribute effects for a custom choice.
        Story continuation is generated separately via generate_story_continuation.

        Args:
            event_description: Current event description
            custom_text: User's custom choice text
            character_settings: Character background settings
            current_state: Current player state dict (for context)

        Returns:
            Dictionary with effects: {"energy": int, "mood": int, "knowledge": int, "wealth": int}
        """
        from config.prompts.story_prompts import (
            get_custom_choice_effects_prompt,
            get_custom_choice_user_prompt,
        )

        current_state = current_state or {}

        system_prompt = get_custom_choice_effects_prompt(
            character_settings=character_settings or {},
            current_state=current_state,
            language=self.language,
        )

        # 清洗用户自定义输入，防止 prompt 注入
        sanitized_custom_text = sanitize_custom_action(custom_text)
        user_prompt = get_custom_choice_user_prompt(
            event_description=event_description,
            custom_text=sanitized_custom_text,
            language=self.language,
        )

        last_error = None
        for attempt in range(2):
            try:
                prompt = user_prompt
                if attempt > 0 and last_error:
                    prompt += f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出有效的JSON格式。】"

                result = self.ai_generator.generate_completion_json(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.8,
                    max_tokens=4096,
                )
                if result and isinstance(result, dict):
                    effect_keys = ("energy", "mood", "knowledge", "wealth")
                    effects = {key: result.get(key) for key in effect_keys}
                    if all(
                        isinstance(value, int) and not isinstance(value, bool)
                        for value in effects.values()
                    ):
                        return effects
                    last_error = "invalid effect payload: all resource effects must be integers"
                else:
                    last_error = (
                        "JSON解析失败或缺少属性字段，"
                        f"返回keys: {list(result.keys()) if result else 'None'}"
                    )
                logger.warning(f"Attempt {attempt + 1}/2: {last_error}")
            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/2 failed: {e}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/2 failed (unexpected): {e}")

        message = "Failed to generate custom choice effects after 2 attempts"
        logger.error("%s: %s", message, last_error)
        raise StoryContinuationFailure(f"{message}: {last_error}")

    def generate_custom_choice_result(
        self,
        event_description: str,
        custom_text: str,
        character_settings: Optional[Dict[str, Any]] = None,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Use AI to generate result for a custom (user-typed) choice.

        Args:
            event_description: Current event description
            custom_text: User's custom choice text
            character_settings: Character background settings
            current_state: Current player state dict (for context)

        Returns:
            Dictionary with 'effects' and 'story_continuation'
        """
        from config.prompts.story_prompts import (
            get_custom_choice_result_prompt,
            get_custom_choice_user_prompt,
        )

        current_state = current_state or {}

        system_prompt = get_custom_choice_result_prompt(
            character_settings=character_settings or {},
            current_state=current_state,
            language=self.language,
        )

        # 清洗用户自定义输入，防止 prompt 注入
        sanitized_custom_text = sanitize_custom_action(custom_text)
        user_prompt = get_custom_choice_user_prompt(
            event_description=event_description,
            custom_text=sanitized_custom_text,
            language=self.language,
        )

        last_error = None
        for attempt in range(2):
            try:
                prompt = user_prompt
                if attempt > 0 and last_error:
                    prompt += f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出有效的JSON格式。】"

                result = self.ai_generator.generate_completion_json(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.8,
                    max_tokens=4096,  # ★ 增加以避免截断
                )
                if result:
                    validation_error = self._validate_custom_choice_result_story(
                        result,
                        character_settings or {},
                    )
                    if validation_error:
                        last_error = validation_error
                        logger.warning(
                            "Attempt %s/2 custom choice result failed consistency: %s",
                            attempt + 1,
                            validation_error,
                        )
                        continue
                    return result
                last_error = "JSON解析失败，未能提取有效结果"
                logger.warning(f"Attempt {attempt + 1}/2: {last_error}")
            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/2 failed: {e}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/2 failed (unexpected): {e}")

        message = "Failed to generate custom choice result after 2 attempts"
        logger.error("%s: %s", message, last_error)
        raise StoryContinuationFailure(f"{message}: {last_error}")

    def _validate_custom_choice_result_story(
        self,
        result: Dict[str, Any],
        character_settings: Dict[str, Any],
    ) -> str:
        """Return a consistency error for generated custom-choice story JSON."""
        story = str(result.get("story_continuation") or "").strip()
        if not story:
            return "story_continuation 为空"

        from config.prompts._helpers import _collect_available_people
        from src.ai.quick_validator import quick_validate_story

        available_people_names = [
            p.get("name", "")
            for p in _collect_available_people(character_settings)
            if p.get("name")
        ]
        validation = quick_validate_story(
            story_text=story,
            character_settings=character_settings,
            available_people=available_people_names,
            language=self.language,
        )
        if validation.passed:
            return ""
        return "; ".join(validation.issues)
