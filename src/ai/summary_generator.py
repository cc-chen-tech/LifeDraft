"""Summary generation service.

Handles story compression, weekly summaries, four-week summaries,
and yearly summaries.
"""

import logging
import re as _re
from typing import Any, Dict, List, Optional

from src.ai.client import AIClient
from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """Generates summaries and compresses stories."""

    def __init__(self, client: AIClient):
        self.client = client

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
                    if len(summary) > 700:
                        summary = summary[:697] + "..."
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
                last_error = (
                    f"JSON缺少summary字段，返回keys: {list(data.keys()) if data else 'None'}"
                )
                logger.warning(f"Attempt {attempt + 1}/2: {last_error}")

                # On last attempt, try fallback extraction
                if attempt == 1:
                    logger.warning(f"Attempting summary-only extraction from: {content[:200]}...")
                    summary_text = self._extract_summary_from_raw(content, story, language)
                    summary_text = self._clean_summary_text(summary_text)
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

        # All retries exhausted — truncate story as fallback
        logger.error("compress_story failed after 2 attempts, using truncation fallback")
        fallback = story[:97] + "..." if len(story) > 100 else story
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
                    if len(summary) > 700:
                        summary = summary[:697] + "..."
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

                last_error = (
                    f"JSON缺少summary字段，返回keys: {list(data.keys()) if data else 'None'}"
                )
                logger.warning(f"[Narrative] Attempt {attempt + 1}/2: {last_error}")

                if attempt == 1:
                    summary_text = self._extract_summary_from_raw(content, story, language)
                    summary_text = self._clean_summary_text(summary_text)
                    return {
                        "summary": summary_text,
                        "event_concluded": True,
                        "storyline_updates": [],
                    }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"[Narrative] Attempt {attempt + 1}/2 failed: {e}")

        logger.error(
            "[Narrative] compress_narrative failed after 2 attempts, using truncation fallback"
        )
        fallback = story[:97] + "..." if len(story) > 100 else story
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
                    total_items = sum(len(v) for v in result.values() if isinstance(v, list))
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

    # -------------------- Weekly Summary --------------------

    def generate_weekly_summary(
        self,
        rounds: List[Dict[str, Any]],
        character_settings: Optional[Dict[str, Any]],
        language: str,
        game_date_info: Optional[Dict[str, Any]] = None,
        wealth_context: Optional[Dict[str, Any]] = None,
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

        prompt = get_weekly_summary_prompt(rounds, character_settings, language, game_date_info)
        wealth_ledger = None
        current_balance = 0
        allowed_transaction_ids: List[str] = []
        if wealth_context:
            from src.game.wealth_ledger import WealthLedger

            current_balance = max(0, int(wealth_context.get("current_balance", 0)))
            raw_ledger = wealth_context.get("wealth_ledger")
            wealth_ledger = WealthLedger(
                raw_ledger if isinstance(raw_ledger, dict) else {}
            )
            allowed_transaction_ids = [
                transaction.transaction_id for transaction in wealth_ledger.transactions
            ]
            prompt += wealth_ledger.build_constraints_text(current_balance, language)
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
                        ("本周平静地度过了。" if language == "zh" else "This week passed quietly."),
                    )
                    bonus_effects = data.get("bonus_effects", {})

                    if wealth_ledger is not None:
                        wealth_validation = wealth_ledger.validate_narrative(
                            str(summary),
                            current_balance=current_balance,
                            allowed_transaction_ids=allowed_transaction_ids,
                        )
                        if not wealth_validation.passed:
                            if attempt == 0:
                                last_error = "; ".join(
                                    issue.message for issue in wealth_validation.issues
                                )
                                continue
                            summary = wealth_ledger.sanitize_narrative(
                                str(summary),
                                wealth_validation,
                                current_balance=current_balance,
                            )

                    # Validate bonus_effects
                    valid_bonus = {}
                    for key in ["energy", "mood", "knowledge", "wealth"]:
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
            "summary": ("本周平静地度过了。" if language == "zh" else "This week passed quietly."),
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
        sys_prompt = get_system_prompt("four_week_summary", language)

        try:
            return self.client.call_with_retry(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                retry_count=2,
                temperature=0.7,
                max_tokens=4096,
                language=language,
            )

        except Exception as e:
            logger.error(f"Failed to generate 4-week summary after retries: {e}")
            return "这4周平静地度过了。" if language == "zh" else "These 4 weeks passed quietly."

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
        sys_prompt = get_system_prompt("yearly_summary", language)

        try:
            return self.client.call_with_retry(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                retry_count=2,
                temperature=0.7,
                max_tokens=4096,
                language=language,
            )

        except Exception as e:
            logger.error(f"Failed to generate yearly summary after retries: {e}")
            return (
                "这一年充满了各种经历。"
                if language == "zh"
                else "This year was full of experiences."
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
        cleaned = _re.sub(r'^\s*\{?\s*["\']?summary["\']?\s*[：:]\s*["\']?', "", cleaned)

        # Remove trailing JSON artifacts: "} or '} or just }
        cleaned = _re.sub(r'["\']?\s*\}\s*$', "", cleaned)

        # Remove any remaining leading/trailing quotes that wrap the entire text
        cleaned = cleaned.strip()
        if len(cleaned) >= 2 and cleaned[0] == '"' and cleaned[-1] == '"':
            cleaned = cleaned[1:-1]

        return cleaned.strip()

    @staticmethod
    def _extract_summary_from_raw(content: str, original_story: str, language: str) -> str:
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
            extracted = extracted.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
            if len(extracted) > 700:
                extracted = extracted[:697] + "..."
            return extracted

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
            if len(extracted) > 700:
                extracted = extracted[:697] + "..."
            return extracted

        # Strategy 3: If cleaned text is reasonable length, use it
        cleaned = _re.sub(r'"[^"]+"\s*:', "", cleaned)  # Remove JSON keys
        cleaned = _re.sub(r"[{}\[\],]", "", cleaned)  # Remove JSON syntax chars
        cleaned = _re.sub(r"\s+", " ", cleaned).strip().strip('"')
        if 5 < len(cleaned) < 800:
            if len(cleaned) > 700:
                cleaned = cleaned[:697] + "..."
            return cleaned

        # Strategy 4: Last resort - truncate original story
        fallback = original_story[:97] + "..." if len(original_story) > 100 else original_story
        return fallback
