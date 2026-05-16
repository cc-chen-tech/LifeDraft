"""Option generation and validation service.

Handles option generation for existing stories (Step 2 of the two-stage pipeline),
relationship name validation/fixing, and event quality checks.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from src.ai.client import AIClient
from src.ai.models import EventOption, GameEvent
from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json
from src.game.constants import GENERIC_CHARACTER_NAMES, GENERIC_OPTION_TEXTS

logger = logging.getLogger(__name__)


def _normalize_option_text(text: str) -> str:
    """Normalize option text for generic-option matching."""
    return re.sub(r"[\s，。！？、,.!?]+", "", text).lower()


class OptionGenerator:
    """Generates and validates options for game events."""

    def __init__(self, client: AIClient):
        self.client = client

    # -------------------- Public API --------------------

    def generate_options_only(
        self,
        story_description: str,
        player_state: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]] = None,
        language: str = "zh",
        retry_count: int = 3,
    ) -> GameEvent:
        """
        Generate options for an existing story (used for opening story).

        Args:
            story_description: The existing story text
            player_state: Current player state
            character_settings: Character background settings
            language: Language code
            retry_count: Number of retries on failure

        Returns:
            GameEvent with the story and generated options
        """
        from config.prompts import get_options_only_prompt

        logger.info("=" * 80)
        logger.info("GENERATING OPTIONS ONLY")
        logger.info(f"Story length: {len(story_description)} characters")
        logger.debug(f"Story preview (first 300 chars): {story_description[:300]}...")
        logger.info(f"Language: {language}")
        logger.info("=" * 80)

        prompt = get_options_only_prompt(
            story_description, player_state, character_settings, language
        )
        logger.info(f"Prompt length: {len(prompt)} characters")
        logger.debug(f"Prompt preview (first 500 chars):\n{prompt[:500]}...")

        sys_prompt = get_system_prompt("option_generator", language)
        last_error: Optional[str] = None

        for attempt in range(retry_count):
            try:
                logger.info(f"Attempt {attempt + 1}/{retry_count}...")

                user_prompt = prompt
                if attempt > 0 and last_error:
                    if language == "zh":
                        user_prompt += (
                            f"\n\n【上次生成失败，原因：{last_error}。"
                            f"请避免同样的问题，确保输出格式正确。】"
                        )
                    else:
                        user_prompt += (
                            f"\n\n[Previous attempt failed: {last_error}. "
                            f"Please avoid the same issue and ensure correct format.]"
                        )

                content = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=user_prompt,
                    temperature=0.7,  # 从 0.8 降至 0.7，减少选项幻觉
                    max_tokens=2000,  # 从 1000 增至 2000，防止截断
                )

                content = content.strip()
                logger.info(f"AI response length: {len(content)} characters")
                logger.debug(f"AI response preview:\n{content[:500]}...")

                # Extract JSON from response
                data = extract_json(content)
                if data:
                    # Create GameEvent with the original story and generated options
                    options = [EventOption(**opt) for opt in data.get("options", [])]
                    logger.info(f"Parsed {len(options)} options:")
                    for i, opt in enumerate(options):
                        logger.info(f"  Option {i+1}: {opt.text}")
                        logger.info(f"    Effects: {opt.effects}")

                    if len(options) >= 2:
                        logger.info("Options generated successfully!")
                        return GameEvent(
                            event_description=story_description,
                            options=options,
                        )

                last_error = "Invalid options format or fewer than 2 options"
                logger.warning(f"Attempt {attempt + 1}: Invalid options format, retrying...")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {e}")

        # Fallback: return with default options
        logger.error("All attempts failed, using fallback options")
        default_options = [
            EventOption(
                text=("积极面对新的一天" if language == "zh" else "Face the new day positively"),
                effects={"energy": -5, "mood": 10, "knowledge": 0, "wealth": 0},
                likely_choice=True,
            ),
            EventOption(
                text=("保持平常心继续前进" if language == "zh" else "Keep calm and move forward"),
                effects={"energy": 0, "mood": 0, "knowledge": 5, "wealth": 0},
                likely_choice=False,
            ),
        ]
        return GameEvent(event_description=story_description, options=default_options)

    # -------------------- Validation --------------------

    def validate_and_fix_relationships(
        self,
        event: GameEvent,
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Validate and fix relationship names in event options.
        Ensures names are corrected if they match key_people or family_members,
        and allows non-key_people characters to have relationship changes.

        Matching strategy (in order):
        1. Exact match against valid names (key_people + family_members)
        2. Case-insensitive exact match
        3. Role-based match (name matches a key_person's role)
        4. Keep the original name as-is (non-key_people can still have relationships)

        Args:
            event: GameEvent to validate
            character_settings: Character settings containing key_people and family
        """
        if not character_settings:
            return

        key_people = []
        if "relationships" in character_settings:
            key_people = character_settings["relationships"].get("key_people", [])

        # Build list of valid names from key_people + family_members
        valid_names = [p.get("name", "") for p in key_people if p.get("name")]

        # Also include family members as valid names
        if "family" in character_settings:
            for member in character_settings["family"].get("family_members", []):
                if isinstance(member, dict):
                    member_name = member.get("name", "")
                    if member_name and member_name not in valid_names:
                        valid_names.append(member_name)

        if not valid_names:
            return

        # Fix relationship names in each option
        for option in event.options:
            if hasattr(option, "effects") and option.effects:
                relationships = option.effects.get("relationships", {})
                if relationships:
                    fixed_relationships = {}
                    for name, value in relationships.items():
                        # Check if name is valid
                        if name in valid_names:
                            fixed_relationships[name] = value
                        else:
                            found_match = False

                            # Try exact match first (case-insensitive)
                            for valid_name in valid_names:
                                if name.lower() == valid_name.lower():
                                    fixed_relationships[valid_name] = value
                                    found_match = True
                                    logger.warning(
                                        f"Fixed relationship name: '{name}' -> '{valid_name}'"
                                    )
                                    break

                            # If not found, try to match by role
                            if not found_match:
                                for person in key_people:
                                    role = person.get("role", "").lower()
                                    if role and (name.lower() in role or role in name.lower()):
                                        person_name = person.get("name", "")
                                        if person_name in valid_names:
                                            fixed_relationships[person_name] = value
                                            found_match = True
                                            logger.warning(
                                                f"Fixed relationship name by role: "
                                                f"'{name}' -> '{person_name}'"
                                            )
                                            break

                            # If no match in key_people/family, keep as-is
                            # Non-key_people characters can still have relationship changes
                            if not found_match:
                                fixed_relationships[name] = value
                                logger.info(f"Keeping non-key_people relationship: '{name}'")

                    # Update relationships in effects
                    option.effects["relationships"] = fixed_relationships

    def validate_event_quality(self, event: GameEvent) -> None:
        """
        Validate that the event has good quality.

        Checks:
        - All options have required effects
        - At least one option has action_points cost
        - Options present real trade-offs
        """
        if len(event.options) < 2:
            raise ValueError("Event must have at least 2 options")

        # Check that all options have effects
        for option in event.options:
            if "action_points" not in option.effects:
                # Default to -1 if not specified
                option.effects["action_points"] = -1

            # Ensure effects are reasonable
            for key in ["energy", "mood", "knowledge"]:
                if key in option.effects:
                    value = option.effects[key]
                    if abs(value) > 50:  # Sanity check
                        logger.warning(f"Large effect value for {key}: {value}")

        # Check for trade-offs (not all options should be clearly better)
        total_effects = []
        for option in event.options:
            total = sum(
                [
                    abs(option.effects.get("energy", 0)),
                    abs(option.effects.get("mood", 0)),
                    abs(option.effects.get("knowledge", 0)),
                    abs(option.effects.get("wealth", 0)) / 1000,  # Normalize wealth
                ]
            )
            total_effects.append(total)

        if max(total_effects) - min(total_effects) < 5:
            logger.warning("Event options may not present clear trade-offs")

    def validate_options_consistency(
        self,
        event: GameEvent,
        story_description: str,
        available_people: Optional[List[str]] = None,
        language: str = "zh",
    ) -> List[str]:
        """
        Validate that options are consistent with the story.

        Checks:
        1. Options relate to the story's decision point
        2. Character names in effects are valid
        3. Effects values are reasonable

        Args:
            event: GameEvent to validate
            story_description: The story text
            available_people: List of allowed character names
            language: Language code

        Returns:
            List of issues found (empty if all valid)
        """
        issues = []

        # 使用共享常量
        generic_options = GENERIC_OPTION_TEXTS

        if not event.options or len(event.options) < 2:
            issues.append("Less than 2 options generated")
            return issues

        for i, option in enumerate(event.options):
            # 检查选项文本长度
            if len(option.text) > 50:
                if language == "zh":
                    issues.append(f"选项{i+1}文本过长({len(option.text)}字)，建议控制在15字内")
                else:
                    issues.append(
                        f"Option {i+1} text too long ({len(option.text)} chars), suggest max 15 words"
                    )

            # 检查是否是通用选项（与故事无关）
            normalized_option_text = _normalize_option_text(option.text)
            normalized_generic_options = [
                _normalize_option_text(g) for g in generic_options.get(language, [])
            ]
            if normalized_option_text in normalized_generic_options or any(
                generic in normalized_option_text for generic in normalized_generic_options
            ):
                if language == "zh":
                    issues.append(f"选项{i+1}「{option.text}」过于通用，应与故事情境相关")
                else:
                    issues.append(
                        f"Option {i+1} '{option.text}' is too generic, should relate to story"
                    )

        # 2. 检查人物名是否在允许列表中
        # 如果人物已在故事文本中出现，则允许其在 relationships 中使用
        story_text_lower = story_description.lower() if story_description else ""
        if available_people:
            for i, option in enumerate(event.options):
                relationships = option.effects.get("relationships", {})
                for name in relationships.keys():
                    if name not in available_people:
                        # 允许一些通用称谓
                        if name in GENERIC_CHARACTER_NAMES:
                            continue
                        # 允许故事中已经出现过的人物（AI 可能在之前的轮次中引入了该人物）
                        if name.lower() in story_text_lower or name in story_description:
                            logger.info(f"允许非列表人物「{name}」：已在故事文本中出现")
                            continue
                        # 其他情况记录警告，但不阻止生成
                        if language == "zh":
                            issues.append(f"选项{i+1}中人物「{name}」不在可用人物列表中")
                        else:
                            issues.append(
                                f"Option {i+1} character '{name}' not in available people list"
                            )

        # 3. 检查 effects 数值是否合理
        for i, option in enumerate(event.options):
            effects = option.effects

            # 检查极端数值
            for key in ["energy", "mood", "knowledge"]:
                value = effects.get(key, 0)
                if abs(value) > 30:
                    if language == "zh":
                        issues.append(f"选项{i+1}的{key}变化过大({value})，建议在-20到20之间")
                    else:
                        issues.append(
                            f"Option {i+1} {key} change too large ({value}), suggest -20 to 20"
                        )

            # 检查财富变化
            wealth_change = effects.get("wealth", 0)
            if abs(wealth_change) > 10000:
                if language == "zh":
                    issues.append(
                        f"选项{i+1}的财富变化过大({wealth_change})，建议在-5000到5000之间"
                    )
                else:
                    issues.append(
                        f"Option {i+1} wealth change too large ({wealth_change}), suggest -5000 to 5000"
                    )

        if issues:
            logger.warning(f"Options consistency issues: {issues}")

        return issues

    @staticmethod
    def ensure_options_consistency(
        event: GameEvent,
        story_description: str,
        available_people: Optional[List[str]] = None,
        language: str = "zh",
    ) -> None:
        """Raise when options are too generic or detached from the story."""
        validator = object.__new__(OptionGenerator)
        issues = OptionGenerator.validate_options_consistency(
            validator,
            event=event,
            story_description=story_description,
            available_people=available_people,
            language=language,
        )
        if issues:
            issue_text = "; ".join(issues)
            generic_markers = (
                "通用",
                "generic",
                "不在可用人物列表",
                "not in available",
            )
            if any(marker in issue_text for marker in generic_markers):
                raise ValueError(f"generic or inconsistent options: {issue_text}")

            raise ValueError(f"inconsistent options: {issue_text}")
