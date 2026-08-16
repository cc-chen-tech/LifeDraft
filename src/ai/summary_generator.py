"""Summary generation service.

Handles story compression, weekly summaries, four-week summaries,
and yearly summaries.
"""

import logging
import re as _re
from typing import Any, Dict, List, Optional

from src.ai.client import AIClient
from src.ai.budgets import (
    InformationBudget,
    format_information_budget_requirement,
    measure_narrative_length,
    resolve_information_budget,
)
from src.ai.professional_risk import apply_professional_risk_guardrail
from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)


_ZH_SENTENCE_PATTERN = _re.compile(r"[^。！？!?]+[。！？!?](?:[”’\"']*)", _re.UNICODE)
_EN_SENTENCE_PATTERN = _re.compile(r"[^.!?]+[.!?](?:[”’\"']*)(?=\s|$)", _re.UNICODE)


def display_summary_overflow_fallback(language: str) -> str:
    """Return a complete, non-authoritative placeholder for uncompactable prose."""
    return (
        "完整记录仍保存在事件账本中。"
        if str(language).lower().startswith("zh")
        else "The complete record remains preserved in the event ledger."
    )


class _LegacyCompletionClientAdapter:
    """One-release adapter for standalone summary generator callers."""

    def __init__(self, generator: Any):
        self.generator = generator

    def call_with_retry(self, **kwargs: Any) -> str:
        return str(
            self.generator.generate_completion(
                prompt=kwargs["user_prompt"],
                system_prompt=kwargs["system_prompt"],
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 2048),
            )
        )


def compact_display_summary(text: str, budget: InformationBudget) -> str:
    """Compact display prose without cutting a sentence or event in half."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned
    language = "zh" if budget.unit == "characters" else "en"
    punctuation = "。" if language == "zh" else "."
    if not cleaned.endswith(("。", "！", "？", ".", "!", "?")):
        cleaned += punctuation
    if measure_narrative_length(cleaned, language) <= budget.compression_threshold:
        return cleaned

    pattern = _ZH_SENTENCE_PATTERN if language == "zh" else _EN_SENTENCE_PATTERN
    sentences = [match.group(0).strip() for match in pattern.finditer(cleaned)]
    if not sentences:
        return display_summary_overflow_fallback(language)

    selected: list[str] = []
    separator = "" if language == "zh" else " "
    for sentence in sentences:
        candidate = separator.join([*selected, sentence])
        if measure_narrative_length(candidate, language) > budget.compression_threshold:
            break
        selected.append(sentence)
        if (
            measure_narrative_length(candidate, language)
            >= budget.compression_threshold
        ):
            break
    if selected:
        return separator.join(selected)
    return display_summary_overflow_fallback(language)


class SummaryGenerator:
    """Generates summaries and compresses stories."""

    def __init__(self, client: AIClient):
        self.client = client

    @classmethod
    def for_compatibility_generator(cls, generator: Any) -> "SummaryGenerator":
        """Resolve the shared service behind an EventGenerator or legacy stub."""
        existing = getattr(generator, "summary_gen", None)
        if isinstance(existing, cls):
            return existing
        if callable(getattr(generator, "generate_completion", None)):
            return cls(_LegacyCompletionClientAdapter(generator))  # type: ignore[arg-type]
        client = getattr(generator, "ai_client", None)
        if client is not None:
            return cls(client)
        return cls(_LegacyCompletionClientAdapter(generator))  # type: ignore[arg-type]

    def generate_display_summary(
        self,
        *,
        summary_kind: str,
        prompt: str,
        language: str,
        fallback: str,
        temperature: float = 0.7,
    ) -> str:
        """Generate recoverable display prose using the shared localized budget."""
        budget = resolve_information_budget(summary_kind, language)
        user_prompt = f"{prompt}\n\n{format_information_budget_requirement(summary_kind, language)}"
        try:
            summary = self.client.call_with_retry(
                system_prompt=get_system_prompt("narrative_summary", language),
                user_prompt=user_prompt,
                retry_count=2,
                temperature=temperature,
                max_tokens=2048,
                language=language,
            )
            cleaned = self._clean_summary_text(summary)
            return compact_display_summary(cleaned, budget) or fallback
        except Exception as exc:
            logger.warning(
                "Display summary generation failed for %s: %s", summary_kind, exc
            )
            return fallback

    # -------------------- Story Compression --------------------

    def compress_story(
        self,
        story: str,
        choice: str,
        language: str,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        character_habits: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Compress a story into a summary and evaluate storyline status.

        Args:
            story: The full story text
            choice: The player's choice text
            language: Language code ('zh' or 'en')
            pending_storylines: Current pending storylines for evaluation
            established_facts: Current established world facts
            character_habits: Current character habits for tracking changes

        Returns:
            Dict with 'summary', 'storyline_updates', 'fact_updates',
            'event_concluded', 'foreshadowing_seeds', 'habit_updates'
        """
        from config.prompts import get_story_compression_prompt

        logger.info(f"Compressing story of {len(story)} chars")

        prompt = get_story_compression_prompt(
            story,
            choice,
            language,
            pending_storylines,
            established_facts,
            character_habits,
        )

        sys_prompt = get_system_prompt("story_compressor", language)

        last_error: Optional[str] = None
        for attempt in range(2):
            try:
                user_prompt = prompt
                if attempt > 0 and last_error:
                    feedback = (
                        f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出有效的JSON格式。】"
                        if language == "zh"
                        else f"\n\n[Previous attempt failed: {last_error}. Please ensure valid JSON output.]"
                    )
                    user_prompt = prompt + feedback

                content = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    temperature=0.5,
                    max_tokens=4096,
                )

                # Try to parse as JSON
                data = extract_json(content)
                if data and "summary" in data:
                    summary = self._clean_summary_text(data["summary"])
                    summary = compact_display_summary(
                        summary, resolve_information_budget("week", language)
                    )
                    storyline_updates = data.get("storyline_updates", [])
                    fact_updates = data.get("fact_updates", [])
                    event_concluded = data.get("event_concluded", True)
                    foreshadowing_seeds = data.get("foreshadowing_seeds", [])
                    habit_updates = data.get("habit_updates", [])
                    logger.info(
                        f"Compressed to {len(summary)} chars with "
                        f"{len(storyline_updates)} storyline updates, "
                        f"{len(fact_updates)} fact updates, "
                        f"event_concluded={event_concluded}, "
                        f"{len(foreshadowing_seeds)} foreshadowing seeds, "
                        f"{len(habit_updates)} habit updates"
                    )
                    return {
                        "summary": summary,
                        "storyline_updates": storyline_updates,
                        "fact_updates": fact_updates,
                        "event_concluded": event_concluded,
                        "foreshadowing_seeds": foreshadowing_seeds,
                        "habit_updates": habit_updates,
                    }

                # JSON parsed but missing 'summary' field
                last_error = f"JSON缺少summary字段，返回keys: {list(data.keys()) if data else 'None'}"
                logger.warning(f"Attempt {attempt + 1}/2: {last_error}")

                # On last attempt, try fallback extraction
                if attempt == 1:
                    logger.warning(
                        f"Attempting summary-only extraction from: {content[:200]}..."
                    )
                    summary_text = self._extract_summary_from_raw(
                        content, story, language
                    )
                    summary_text = self._clean_summary_text(summary_text)
                    summary_text = compact_display_summary(
                        summary_text, resolve_information_budget("week", language)
                    )
                    logger.info(f"Fallback summary: {len(summary_text)} chars")
                    return {
                        "summary": summary_text,
                        "storyline_updates": [],
                        "fact_updates": [],
                        "event_concluded": True,
                        "foreshadowing_seeds": [],
                        "habit_updates": [],
                    }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/2 failed: {e}")

        logger.error("compress_story failed after 2 attempts, using sentence fallback")
        fallback = compact_display_summary(
            story, resolve_information_budget("week", language)
        )
        return {
            "summary": fallback,
            "storyline_updates": [],
            "fact_updates": [],
            "event_concluded": True,
            "foreshadowing_seeds": [],
            "habit_updates": [],
        }

    # -------------------- Split Compression (Parallel) --------------------

    def compress_narrative(
        self,
        story: str,
        choice: str,
        language: str,
        pending_storylines: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Narrative compression only: summary + event_concluded + storyline_updates.
        Designed to run in parallel with extract_world_updates.

        Returns:
            Dict with 'summary', 'event_concluded', 'storyline_updates'
        """
        from config.prompts import get_narrative_compression_prompt

        logger.info(f"[Narrative] Compressing story of {len(story)} chars")

        prompt = get_narrative_compression_prompt(
            story,
            choice,
            language,
            pending_storylines,
        )
        sys_prompt = get_system_prompt("story_compressor", language)

        last_error: Optional[str] = None
        for attempt in range(2):
            try:
                user_prompt = prompt
                if attempt > 0 and last_error:
                    feedback = (
                        f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出有效的JSON格式。】"
                        if language == "zh"
                        else f"\n\n[Previous attempt failed: {last_error}. Please ensure valid JSON output.]"
                    )
                    user_prompt = prompt + feedback

                content = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    temperature=0.5,
                    max_tokens=4096,
                )

                data = extract_json(content)
                if data and "summary" in data:
                    summary = self._clean_summary_text(data["summary"])
                    summary = compact_display_summary(
                        summary, resolve_information_budget("week", language)
                    )
                    storyline_updates = data.get("storyline_updates", [])
                    event_concluded = data.get("event_concluded", True)
                    logger.info(
                        f"[Narrative] Compressed to {len(summary)} chars, "
                        f"{len(storyline_updates)} storyline updates, "
                        f"event_concluded={event_concluded}"
                    )
                    return {
                        "summary": summary,
                        "event_concluded": event_concluded,
                        "storyline_updates": storyline_updates,
                    }

                last_error = f"JSON缺少summary字段，返回keys: {list(data.keys()) if data else 'None'}"
                logger.warning(f"[Narrative] Attempt {attempt + 1}/2: {last_error}")

                if attempt == 1:
                    summary_text = self._extract_summary_from_raw(
                        content, story, language
                    )
                    summary_text = self._clean_summary_text(summary_text)
                    summary_text = compact_display_summary(
                        summary_text, resolve_information_budget("week", language)
                    )
                    return {
                        "summary": summary_text,
                        "event_concluded": True,
                        "storyline_updates": [],
                    }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Narrative] Attempt {attempt + 1}/2 failed: {e}")

        logger.error(
            "[Narrative] compress_narrative failed after 2 attempts, using sentence fallback"
        )
        fallback = compact_display_summary(
            story, resolve_information_budget("week", language)
        )
        return {
            "summary": fallback,
            "event_concluded": True,
            "storyline_updates": [],
        }

    def extract_world_updates(
        self,
        story: str,
        choice: str,
        language: str,
        established_facts: Optional[list] = None,
        character_habits: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        World state extraction only: fact_updates, foreshadowing_seeds,
        habit_updates, location_updates, career_updates,
        commitment_updates, causal_updates.
        Designed to run in parallel with compress_narrative.

        Returns:
            Dict with all world extraction fields.
        """
        from config.prompts import get_world_extraction_prompt

        logger.info(f"[WorldExtract] Extracting world updates from {len(story)} chars")

        prompt = get_world_extraction_prompt(
            story,
            choice,
            language,
            established_facts,
            character_habits,
        )
        sys_prompt = get_system_prompt("story_compressor", language)

        _empty_result: Dict[str, Any] = {
            "fact_updates": [],
            "foreshadowing_seeds": [],
            "habit_updates": [],
            "location_updates": [],
            "career_updates": [],
            "commitment_updates": [],
            "causal_updates": [],
        }

        last_error: Optional[str] = None
        for attempt in range(2):
            try:
                user_prompt = prompt
                if attempt > 0 and last_error:
                    feedback = (
                        f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出有效的JSON格式。】"
                        if language == "zh"
                        else f"\n\n[Previous attempt failed: {last_error}. Please ensure valid JSON output.]"
                    )
                    user_prompt = prompt + feedback

                content = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    temperature=0.5,
                    max_tokens=4096,
                )

                data = extract_json(content)
                if data and isinstance(data, dict):
                    result = {}
                    for key in _empty_result:
                        result[key] = data.get(key, [])
                    total_items = sum(
                        len(v) for v in result.values() if isinstance(v, list)
                    )
                    logger.info(
                        f"[WorldExtract] Extracted {total_items} total items across {len(result)} categories"
                    )
                    return result

                last_error = f"JSON解析失败，返回类型: {type(data).__name__}"
                logger.warning(f"[WorldExtract] Attempt {attempt + 1}/2: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[WorldExtract] Attempt {attempt + 1}/2 failed: {e}")

        logger.error(
            "[WorldExtract] extract_world_updates failed after 2 attempts, returning empty"
        )
        return dict(_empty_result)

    def extract_daily_world_projection(
        self,
        story: str,
        options: list[Any],
        tracked_state: Any = None,
        *,
        language: str = "zh",
    ) -> "WorldProjectionPayload":
        """Extract a typed daily projection without converting failures to empty data."""
        from config.prompts import get_daily_world_projection_prompt
        from src.game.world_projection_schema import (
            WorldProjectionExtractionError,
            WorldProjectionPayload,
            validate_projection_payload,
        )

        prompt = get_daily_world_projection_prompt(
            story, options, language, tracked_state
        )
        system_prompt = get_system_prompt("story_compressor", language)
        last_error: Optional[WorldProjectionExtractionError] = None
        for attempt in range(2):
            try:
                content = self.client.call(
                    system_prompt=system_prompt,
                    user_prompt=prompt,
                    temperature=0.5,
                    max_tokens=4096,
                )
                data = extract_json(content)
                if not isinstance(data, dict):
                    raise WorldProjectionExtractionError(
                        f"Daily world projection response was {type(data).__name__}, not a JSON object",
                        code="invalid_json",
                    )
                return validate_projection_payload(data, story, options, tracked_state)
            except WorldProjectionExtractionError as exc:
                last_error = exc
            except TimeoutError as exc:
                last_error = WorldProjectionExtractionError(
                    f"Daily world projection provider timed out: {exc}",
                    code="provider_timeout",
                )
            except Exception as exc:
                last_error = WorldProjectionExtractionError(
                    f"Daily world projection provider failed: {exc}",
                    code="provider_error",
                )
            logger.warning(
                "[DailyWorldProjection] attempt %s/2 failed: %s",
                attempt + 1,
                last_error,
            )

        assert last_error is not None
        raise last_error

    def compress_and_extract(
        self,
        story: str,
        choice: str,
        language: str,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        character_habits: Optional[list] = None,
    ) -> Dict[str, Any]:
        """P1-成本优化：叙事压缩 + 世界状态提取合并为一次 LLM 调用。

        故事原文只发送一次；返回的 dict 同时包含 narrative 字段
        （summary / event_concluded / storyline_updates）与 world 字段
        （fact_updates / foreshadowing_seeds / habit_updates / location_updates /
        career_updates / commitment_updates / causal_updates）。
        """
        from config.prompts import get_combined_choice_postprocess_prompt

        logger.info(f"[CombinedPostprocess] Processing story of {len(story)} chars")

        prompt = get_combined_choice_postprocess_prompt(
            story,
            choice,
            language,
            pending_storylines,
            established_facts,
            character_habits,
        )
        sys_prompt = get_system_prompt("story_compressor", language)

        last_error: Optional[str] = None
        for attempt in range(2):
            try:
                user_prompt = prompt
                if attempt > 0 and last_error:
                    feedback = (
                        f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出有效的JSON格式。】"
                        if language == "zh"
                        else f"\n\n[Previous attempt failed: {last_error}. Please ensure valid JSON output.]"
                    )
                    user_prompt = prompt + feedback

                content = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    temperature=0.5,
                    max_tokens=8192,
                )

                data = extract_json(content)
                if data and isinstance(data, dict) and "summary" in data:
                    summary = self._clean_summary_text(data["summary"])
                    summary = compact_display_summary(
                        summary, resolve_information_budget("week", language)
                    )
                    result = {
                        "summary": summary,
                        "event_concluded": data.get("event_concluded", True),
                        "storyline_updates": data.get("storyline_updates", []),
                    }
                    for key in (
                        "fact_updates",
                        "foreshadowing_seeds",
                        "habit_updates",
                        "location_updates",
                        "career_updates",
                        "commitment_updates",
                        "causal_updates",
                    ):
                        result[key] = data.get(key, [])
                    logger.info(
                        f"[CombinedPostprocess] summary={len(summary)} chars, "
                        f"storylines={len(result['storyline_updates'])}, "
                        f"facts={len(result['fact_updates'])}"
                    )
                    return result

                last_error = f"JSON缺少summary字段，返回keys: {list(data.keys()) if data else 'None'}"
                logger.warning(
                    f"[CombinedPostprocess] Attempt {attempt + 1}/2: {last_error}"
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"[CombinedPostprocess] Attempt {attempt + 1}/2 failed: {e}"
                )

        logger.error(
            "[CombinedPostprocess] failed after 2 attempts; returning deterministic fallback"
        )
        fallback = compact_display_summary(
            story, resolve_information_budget("week", language)
        )
        return {
            "summary": fallback,
            "event_concluded": True,
            "storyline_updates": [],
            "fact_updates": [],
            "foreshadowing_seeds": [],
            "habit_updates": [],
            "location_updates": [],
            "career_updates": [],
            "commitment_updates": [],
            "causal_updates": [],
        }

    # -------------------- Weekly Summary --------------------

    def generate_weekly_summary(
        self,
        rounds: List[Dict[str, Any]],
        character_settings: Optional[Dict[str, Any]],
        language: str,
        game_date_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate weekly summary and bonus effects.

        Args:
            rounds: List of round records for the week
            character_settings: Character background settings
            language: Language code ('zh' or 'en')
            game_date_info: Game-internal date info

        Returns:
            Dict with 'summary' and 'bonus_effects'
        """
        from config.prompts import get_weekly_summary_prompt

        logger.info(f"Generating weekly summary for {len(rounds)} rounds")

        prompt = get_weekly_summary_prompt(
            rounds, character_settings, language, game_date_info
        )
        sys_prompt = get_system_prompt("weekly_summary", language)

        last_error: Optional[str] = None
        for attempt in range(2):
            try:
                user_prompt = prompt
                if attempt > 0 and last_error:
                    feedback = (
                        f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出有效的JSON格式。】"
                        if language == "zh"
                        else f"\n\n[Previous attempt failed: {last_error}. Please ensure valid JSON output.]"
                    )
                    user_prompt = prompt + feedback

                content = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    temperature=0.7,
                    max_tokens=4096,
                )
                logger.info(f"Weekly summary response: {content[:200]}...")

                # Extract JSON
                data = extract_json(content)
                if data:
                    summary = data.get(
                        "summary",
                        (
                            "本周平静地度过了。"
                            if language == "zh"
                            else "This week passed quietly."
                        ),
                    )
                    summary = compact_display_summary(
                        self._clean_summary_text(str(summary)),
                        resolve_information_budget("week", language),
                    )
                    bonus_effects = data.get("bonus_effects", {})

                    # Validate bonus_effects
                    valid_bonus = {}
                    for key in ["energy", "mood", "knowledge"]:
                        val = bonus_effects.get(key, 0)
                        if isinstance(val, (int, float)) and -20 <= val <= 20:
                            valid_bonus[key] = int(val)

                    logger.info(f"Weekly summary: {summary[:50]}...")
                    logger.info(f"Bonus effects: {valid_bonus}")

                    return {"summary": summary, "bonus_effects": valid_bonus}

                last_error = "JSON解析失败，未能提取有效结果"
                logger.warning(f"Attempt {attempt + 1}/2: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/2 failed: {e}")

        # Fallback
        logger.error("generate_weekly_summary failed after 2 attempts, using fallback")
        return {
            "summary": (
                "本周平静地度过了。"
                if language == "zh"
                else "This week passed quietly."
            ),
            "bonus_effects": {},
        }

    # -------------------- Four-Week Summary --------------------

    def generate_four_week_summary(
        self,
        stories: List[str],
        decisions: List[Dict[str, Any]],
        character_settings: Optional[Dict[str, Any]] = None,
        language: str = "zh",
        game_date_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a summary for the past 4 weeks.

        Args:
            stories: List of story descriptions from the past 4 weeks
            decisions: List of decisions made in the past 4 weeks
            character_settings: Character background settings
            language: Language code
            game_date_info: Game-internal date info

        Returns:
            Summary text
        """
        from config.prompts import get_four_week_summary_prompt

        prompt = get_four_week_summary_prompt(
            stories, decisions, character_settings, language, game_date_info
        )
        return self.generate_display_summary(
            summary_kind="month",
            prompt=prompt,
            language=language,
            fallback=(
                "这4周平静地度过了。"
                if language == "zh"
                else "These 4 weeks passed quietly."
            ),
        )

    # -------------------- Yearly Summary --------------------

    def generate_yearly_summary(
        self,
        four_week_summaries: List[Dict[str, Any]],
        character_settings: Optional[Dict[str, Any]] = None,
        start_week: int = 0,
        end_week: int = 47,
        language: str = "zh",
        game_date_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a yearly summary based on 4-week summaries.

        Args:
            four_week_summaries: List of 4-week summaries (up to 12)
            character_settings: Character background settings
            start_week: Starting week number
            end_week: Ending week number
            language: Language code
            game_date_info: Game-internal date info

        Returns:
            Yearly summary text
        """
        from config.prompts import get_yearly_summary_prompt

        prompt = get_yearly_summary_prompt(
            four_week_summaries,
            character_settings,
            start_week,
            end_week,
            language,
            game_date_info,
        )
        return self.generate_display_summary(
            summary_kind="year",
            prompt=prompt,
            language=language,
            fallback=(
                "这一年充满了各种经历。"
                if language == "zh"
                else "This year was full of experiences."
            ),
        )

    # -------------------- Internal Helpers --------------------

    @staticmethod
    def _clean_summary_text(summary: str) -> str:
        """
        Clean summary text by removing any residual code block markers,
        JSON structural artifacts, or nested format prefixes.
        This is a final safety net applied to ALL summary paths.
        """
        if not summary:
            return summary

        # Remove code block markers (backticks and single quotes, with optional lang tag)
        cleaned = _re.sub(r"`{3}(?:json)?\s*", "", summary)
        cleaned = _re.sub(r"`{3}", "", cleaned)
        cleaned = _re.sub(r"'{3}(?:json)?\s*", "", cleaned)
        cleaned = _re.sub(r"'{3}", "", cleaned)

        # Remove standalone "json" / "JSON" prefix at the start
        cleaned = _re.sub(r"^\s*[Jj][Ss][Oo][Nn]\s*[：:]?\s*", "", cleaned)

        # Remove JSON structural prefix: {"summary":" or "summary":" or summary:
        cleaned = _re.sub(
            r'^\s*\{?\s*["\']?summary["\']?\s*[：:]\s*["\']?', "", cleaned
        )

        # Remove trailing JSON artifacts: "} or '} or just }
        cleaned = _re.sub(r'["\']?\s*\}\s*$', "", cleaned)

        # Remove any remaining leading/trailing quotes that wrap the entire text
        cleaned = cleaned.strip()
        if len(cleaned) >= 2 and cleaned[0] == '"' and cleaned[-1] == '"':
            cleaned = cleaned[1:-1]

        return apply_professional_risk_guardrail(cleaned.strip(), language="auto")

    @staticmethod
    def _extract_summary_from_raw(
        content: str, original_story: str, language: str
    ) -> str:
        """
        Try to extract a clean summary from raw/malformed AI response.
        Handles cases where JSON parsing fails but summary text exists.

        Args:
            content: Raw AI response text
            original_story: Original story for last-resort truncation
            language: Language code

        Returns:
            Clean summary text without any JSON/code markers
        """
        text = content.strip()

        # Strategy 1: Try to extract "summary" value via regex from partial JSON
        summary_match = _re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if summary_match:
            extracted = summary_match.group(1)
            extracted = (
                extracted.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            )
            return compact_display_summary(
                extracted, resolve_information_budget("week", language)
            )

        # Strategy 2: Remove all JSON/code markers and extract readable text
        cleaned = text
        cleaned = _re.sub(r"```(?:json)?\s*", "", cleaned)
        cleaned = _re.sub(r"```", "", cleaned)
        cleaned = _re.sub(r"'''(?:json)?\s*", "", cleaned)
        cleaned = _re.sub(r"'''", "", cleaned)
        cleaned = cleaned.strip().strip("{}").strip()
        value_match = _re.search(r'"[^"]+"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
        if value_match:
            extracted = value_match.group(1)
            return compact_display_summary(
                extracted, resolve_information_budget("week", language)
            )

        # Strategy 3: If cleaned text is reasonable length, use it
        cleaned = _re.sub(r'"[^"]+"\s*:', "", cleaned)  # Remove JSON keys
        cleaned = _re.sub(r"[{}\[\],]", "", cleaned)  # Remove JSON syntax chars
        cleaned = _re.sub(r"\s+", " ", cleaned).strip().strip('"')
        if 5 < len(cleaned) < 800:
            return compact_display_summary(
                cleaned, resolve_information_budget("week", language)
            )

        return compact_display_summary(
            original_story, resolve_information_budget("week", language)
        )
