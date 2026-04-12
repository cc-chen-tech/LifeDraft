"""Character creation and world setup system."""

import json
import logging
import random
from typing import Any, Dict, List, Optional

from config.prompts import (
    get_character_setting_prompt,
    get_initial_attributes_prompt,
    get_opening_story_prompt,
    get_relationship_person_prompt,
    get_relationships_summary_prompt,
)
from src.ai.generator import EventGenerator
from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)


def assign_sexual_orientation() -> str:
    """
    根据概率分配性倾向（基于统计数据）

    Returns:
        性倾向字符串
    """
    weights = {
        "heterosexual": 0.90,
        "homosexual": 0.04,
        "bisexual": 0.05,
        "asexual": 0.01,
    }
    return random.choices(list(weights.keys()), weights=list(weights.values()))[0]


class CharacterCreator:
    """Handles character and world creation using AI."""

    def __init__(self, ai_generator: Optional[EventGenerator] = None, language: str = "zh"):
        """
        Initialize character creator.

        Args:
            ai_generator: AI event generator
            language: Language code
        """
        self.ai_generator = ai_generator or EventGenerator()
        self.language = language

    def generate_setting(
        self,
        setting_type: str,
        player_name: str,
        life_vision: str,
        previous_settings: Dict[str, Any],
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a specific setting using AI.

        Args:
            setting_type: Type of setting to generate (era, age, gender, world, family, relationships, traits)
            player_name: Player's name
            life_vision: Player's life vision/desire
            previous_settings: Previously generated settings
            feedback: Optional feedback if regenerating

        Returns:
            Generated setting dictionary
        """
        prompt = get_character_setting_prompt(
            setting_type,
            player_name,
            life_vision,
            previous_settings,
            language=self.language,
            feedback=feedback,
        )

        # Allow more retries for all setting types
        max_retries = 3

        for attempt in range(max_retries):
            try:
                content = self.ai_generator.generate_completion(
                    prompt=prompt,
                    system_prompt=get_system_prompt("world_building", "en"),
                    temperature=1.0,  # Use 1.0 for better JSON stability with DeepSeek
                    max_tokens=4096,  # Increased to avoid truncation for traits/wealth
                )

                # Unified JSON extraction (handles code blocks, regex fallback, etc.)
                result = extract_json(content)
                if result is None:
                    raise ValueError(f"Failed to extract JSON from response: {content[:200]}")

                # Validate wealth if it's the wealth setting
                if setting_type == "wealth":
                    wealth = result.get("wealth", 0)
                    # If wealth is 0 or missing, retry API call
                    if wealth == 0 or wealth is None:
                        if attempt < max_retries - 1:
                            logger.warning(
                                f"Generated wealth is 0 or missing (attempt {attempt + 1}/{max_retries}), retrying API call..."
                            )
                            # Add more explicit instruction to the prompt for retry
                            if self.language == "zh":
                                prompt += "\n\n**重要：请确保 wealth 字段是一个正整数（1000-1000000），绝对不能为 0。如果角色来自贫困家庭，财富至少应为 1000-5000。**"
                            else:
                                prompt += "\n\n**IMPORTANT: Please ensure the wealth field is a positive integer (1000-1000000), and must NEVER be 0. If the character comes from a poor family, wealth should be at least 1000-5000.**"
                            continue  # Retry API call
                        else:
                            # Last attempt failed, use fallback
                            logger.error(
                                f"Failed to generate valid wealth after {max_retries} attempts, using fallback"
                            )
                            fallback = self._get_fallback_setting(setting_type)
                            if fallback.get("wealth", 0) == 0:
                                fallback["wealth"] = 30000
                            return fallback
                    elif wealth < 1000:
                        # If wealth is too low (but not 0), ensure minimum
                        result["wealth"] = max(1000, wealth)
                        logger.warning(
                            f"Generated wealth {wealth} is too low, adjusted to {result['wealth']}"
                        )

                # Validate and calculate birth_year for age setting
                if setting_type == "age":
                    age = result.get("age", 22)
                    # Get era year from previous_settings
                    era_year = previous_settings.get("era", {}).get("year", 2024)
                    # Calculate correct birth_year
                    correct_birth_year = era_year - age
                    generated_birth_year = result.get("birth_year")

                    # If birth_year is missing or incorrect, fix it
                    if generated_birth_year is None or generated_birth_year != correct_birth_year:
                        if generated_birth_year is not None:
                            logger.warning(
                                f"Birth year mismatch: AI generated {generated_birth_year}, should be {correct_birth_year}. Correcting..."
                            )
                        result["birth_year"] = correct_birth_year
                        logger.debug(
                            f"Set birth_year to {correct_birth_year} (era: {era_year}, age: {age})"
                        )

                return result

            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to generate {setting_type} (attempt {attempt + 1}/{max_retries}): {e}, retrying..."
                    )
                    continue
                else:
                    logger.error(
                        f"Failed to generate {setting_type} after {max_retries} attempts: {e}"
                    )
                    logger.error(f"Error type: {type(e).__name__}, Error details: {str(e)}")
                    fallback = self._get_fallback_setting(setting_type)
                    # Ensure wealth fallback is not 0
                    if setting_type == "wealth" and fallback.get("wealth", 0) == 0:
                        fallback["wealth"] = 30000
                    # Mark as fallback for debugging
                    fallback["_is_fallback"] = True
                    fallback["_error"] = f"{type(e).__name__}: {str(e)}"
                    logger.warning(f"Using fallback for {setting_type}: {fallback}")
                    return fallback
            except Exception as e:
                # Unexpected error - log with stack trace
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to generate {setting_type} (attempt {attempt + 1}/{max_retries}): {e}, retrying..."
                    )
                    continue
                else:
                    logger.exception(
                        f"Unexpected error generating {setting_type} after {max_retries} attempts: {e}"
                    )
                    logger.error(f"Error type: {type(e).__name__}, Error details: {str(e)}")
                    fallback = self._get_fallback_setting(setting_type)
                    # Ensure wealth fallback is not 0
                    if setting_type == "wealth" and fallback.get("wealth", 0) == 0:
                        fallback["wealth"] = 30000
                    # Mark as fallback for debugging
                    fallback["_is_fallback"] = True
                    fallback["_error"] = f"{type(e).__name__}: {str(e)}"
                    logger.warning(f"Using fallback for {setting_type}: {fallback}")
                    return fallback

        # Should not reach here, but just in case
        fallback = self._get_fallback_setting(setting_type)
        if setting_type == "wealth" and fallback.get("wealth", 0) == 0:
            fallback["wealth"] = 30000
        return fallback

    def generate_single_relationship_person(
        self,
        player_name: str,
        life_vision: str,
        previous_settings: Dict[str, Any],
        existing_people: List[Dict[str, Any]],
        person_index: int,
        total_needed: int,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a single relationship person with rich attributes.

        Args:
            player_name: Player's name
            life_vision: Player's life vision
            previous_settings: Previously generated settings
            existing_people: List of already generated people
            person_index: Current person index (0-based)
            total_needed: Total number of people needed
            feedback: Optional feedback for regeneration

        Returns:
            Rich character dictionary with full CharacterState attributes
        """
        max_retries = 3
        last_error = ""
        is_zh = self.language == "zh"

        for attempt in range(max_retries):
            try:
                # 构建 prompt，如果有上次失败信息则注入
                prompt = get_relationship_person_prompt(
                    player_name=player_name,
                    life_vision=life_vision,
                    previous_settings=previous_settings,
                    existing_people=existing_people,
                    person_index=person_index,
                    total_needed=total_needed,
                    language=self.language,
                    feedback=feedback,
                )

                # ★ 错误反馈注入：重试时追加上次失败原因
                if attempt > 0 and last_error:
                    if is_zh:
                        error_feedback = f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题，确保输出格式正确。】"
                    else:
                        error_feedback = f"\n\n[Previous generation failed. Reason: {last_error}. Please avoid the same issue and ensure correct output format.]"
                    prompt += error_feedback

                result = self.ai_generator.generate_completion_json(
                    prompt=prompt,
                    system_prompt=get_system_prompt("relationship_designer", "en"),
                    temperature=0.9,
                    max_tokens=4096,  # Increased for richer attributes
                )

                if not result:
                    raise ValueError("AI returned no valid JSON")

                # Validate required fields
                if not result.get("name") or not result.get("role"):
                    raise ValueError("Missing required fields: name or role")

                # Ensure backward compatibility - add 'relationship' field
                if "relationship_desc" in result and "relationship" not in result:
                    result["relationship"] = result["relationship_desc"]
                elif "relationship" in result and "relationship_desc" not in result:
                    result["relationship_desc"] = result["relationship"]

                # Set defaults for missing optional fields
                result.setdefault("age", 25)
                result.setdefault("gender", "")
                result.setdefault("occupation", "")
                result.setdefault("personality_traits", [])
                result.setdefault("temperament", "balanced")
                result.setdefault("mood", 60)
                result.setdefault("mood_stability", 70)
                result.setdefault("social_status", "ordinary")
                result.setdefault("influence", 30)
                result.setdefault("competence", 50)
                result.setdefault("specialty", [])
                result.setdefault("affinity", 55)
                result.setdefault("trust", 50)
                result.setdefault("respect", 50)

                # 自动分配隐藏属性（不暴露给用户）
                result.setdefault("sexual_orientation", assign_sexual_orientation())
                result.setdefault("relationship_status", "single")
                result.setdefault("romantic_interest", "")
                result.setdefault("has_external_obstacle", False)
                result.setdefault("peak_affinity", result.get("affinity", 55))
                result.setdefault("triggered_events", [])

                # Check for forbidden phrases
                forbidden_phrases = [
                    "有一些朋友",
                    "几个朋友",
                    "一些朋友",
                    "some friends",
                    "a few friends",
                ]
                relationship_text = result.get("relationship_desc", "").lower()
                if any(phrase in relationship_text for phrase in forbidden_phrases):
                    raise ValueError("Contains forbidden vague phrases")

                # ★ 成功生成，返回结果
                logger.debug(
                    f"Successfully generated relationship person {person_index + 1} on attempt {attempt + 1}"
                )
                return result

            except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to generate relationship person {person_index + 1} (attempt {attempt + 1}/{max_retries}): {e}, retrying..."
                    )
                    continue
                else:
                    logger.error(
                        f"Failed to generate relationship person {person_index + 1} after {max_retries} attempts: {e}"
                    )
                    # Return a fallback with rich attributes
                    return {
                        "name": (
                            f"人物{person_index + 1}" if is_zh else f"Person{person_index + 1}"
                        ),
                        "role": "朋友" if is_zh else "Friend",
                        "relationship": (
                            "与玩家关系密切，经常交流互动。"
                            if is_zh
                            else "Close relationship with the player, frequent interaction."
                        ),
                        "relationship_desc": (
                            "与玩家关系密切，经常交流互动。"
                            if is_zh
                            else "Close relationship with the player, frequent interaction."
                        ),
                        "age": 25,
                        "gender": "",
                        "occupation": "",
                        "personality_traits": (
                            ["友善", "热心"] if is_zh else ["friendly", "helpful"]
                        ),
                        "temperament": "balanced",
                        "mood": 60,
                        "mood_stability": 70,
                        "social_status": "ordinary",
                        "influence": 30,
                        "competence": 50,
                        "specialty": [],
                        "affinity": 55,
                        "trust": 50,
                        "respect": 50,
                        "sexual_orientation": assign_sexual_orientation(),
                        "relationship_status": "single",
                        "romantic_interest": "",
                        "has_external_obstacle": False,
                        "peak_affinity": 55,
                        "triggered_events": [],
                    }
            except Exception as e:
                # Unexpected error - log with stack trace
                last_error = str(e)
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Failed to generate relationship person {person_index + 1} (attempt {attempt + 1}/{max_retries}): {e}, retrying..."
                    )
                    continue
                else:
                    logger.exception(
                        f"Unexpected error generating relationship person {person_index + 1} after {max_retries} attempts: {e}"
                    )
                    # Return a fallback with rich attributes
                    return {
                        "name": (
                            f"人物{person_index + 1}" if is_zh else f"Person{person_index + 1}"
                        ),
                        "role": "朋友" if is_zh else "Friend",
                        "relationship": (
                            "与玩家关系密切，经常交流互动。"
                            if is_zh
                            else "Close relationship with the player, frequent interaction."
                        ),
                        "relationship_desc": (
                            "与玩家关系密切，经常交流互动。"
                            if is_zh
                            else "Close relationship with the player, frequent interaction."
                        ),
                        "age": 25,
                        "gender": "",
                        "occupation": "",
                        "personality_traits": (
                            ["友善", "热心"] if is_zh else ["friendly", "helpful"]
                        ),
                        "temperament": "balanced",
                        "mood": 60,
                        "mood_stability": 70,
                        "social_status": "ordinary",
                        "influence": 30,
                        "competence": 50,
                        "specialty": [],
                        "affinity": 55,
                        "trust": 50,
                        "respect": 50,
                        "sexual_orientation": assign_sexual_orientation(),
                        "relationship_status": "single",
                        "romantic_interest": "",
                        "has_external_obstacle": False,
                        "peak_affinity": 55,
                        "triggered_events": [],
                    }
        # This should never be reached, but mypy requires it
        return {}  # type: ignore[return-value]

    def generate_relationships_summary(
        self,
        player_name: str,
        life_vision: str,
        previous_settings: Dict[str, Any],
        key_people: List[Dict[str, Any]],
    ) -> str:
        """
        Generate relationships_description summary after all people are generated.

        Args:
            player_name: Player's name
            life_vision: Player's life vision
            previous_settings: Previously generated settings
            key_people: List of all generated people

        Returns:
            Detailed relationships description (100-150 words)
        """
        prompt = get_relationships_summary_prompt(
            player_name=player_name,
            life_vision=life_vision,
            previous_settings=previous_settings,
            key_people=key_people,
            language=self.language,
        )

        try:
            result = self.ai_generator.generate_completion_json(
                prompt=prompt,
                system_prompt=get_system_prompt("narrative_writer", "en"),
                temperature=0.8,
                max_tokens=4096,
            )

            if result:
                return result.get("relationships_description", "")  # type: ignore[no-any-return]
            raise ValueError("AI returned no valid JSON for relationships summary")
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"Failed to generate relationships summary: {e}")
            # Fall through to generate fallback summary
        except Exception as e:
            logger.exception(f"Unexpected error generating relationships summary: {e}")

        # Generate fallback summary from key_people
        if self.language == "zh":
            if key_people:
                names = [p.get("name", "") for p in key_people if p.get("name")]
                roles = [p.get("role", "") for p in key_people if p.get("role")]
                return f"玩家与{len(key_people)}位关键人物建立了密切关系：{', '.join([f'{name}({role})' for name, role in zip(names[:3], roles[:3])])}等。这些关系对玩家的人生发展有重要影响。"
            else:
                return "玩家在社会中建立了多种关系，这些关系对玩家的发展有重要影响。"
        else:
            if key_people:
                names = [p.get("name", "") for p in key_people if p.get("name")]
                roles = [p.get("role", "") for p in key_people if p.get("role")]
                return f"The player has established close relationships with {len(key_people)} key people: {', '.join([f'{name}({role})' for name, role in zip(names[:3], roles[:3])])}, etc. These relationships have important impacts on the player's life development."
            else:
                return "The player has established various relationships in society, which have important impacts on development."

    def generate_initial_attributes(
        self, character_settings: Dict[str, Any], language: str = "zh"
    ) -> Dict[str, int]:
        """
        Generate initial core attributes (energy, mood, knowledge, wealth) based on character traits.

        Args:
            character_settings: Complete character settings dictionary
            language: Language code

        Returns:
            Dictionary with energy, mood, knowledge, wealth values
        """
        prompt = get_initial_attributes_prompt(character_settings, language)

        try:
            age = character_settings.get("age", {}).get("age", 22)
            family_economy = character_settings.get("family", {}).get("family_economy", "")
            logger.debug(f"开始生成初始属性: age={age}, family_economy={family_economy}")
            result = self.ai_generator.generate_completion_json(
                prompt=prompt,
                system_prompt=get_system_prompt("attribute_generator", "en"),
                temperature=0.7,
                max_tokens=4096,
            )

            if not result:
                raise ValueError("AI returned no valid JSON for attributes")

            logger.debug(f"AI属性生成响应: {result}")

            # Validate and clamp values
            energy = max(0, min(100, result.get("energy", 70)))
            mood = max(0, min(100, result.get("mood", 60)))
            knowledge = max(0, min(100, result.get("knowledge", 50)))
            wealth = max(0, min(1000000, result.get("wealth", 10000)))

            return {
                "energy": energy,
                "mood": mood,
                "knowledge": knowledge,
                "wealth": wealth,
            }
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"AI生成初始属性失败: {e}")
            # Fall through to rule-based generation
        except Exception as e:
            logger.exception(f"AI生成初始属性失败 (unexpected): {e}")

        # Fallback: use rule-based generation
        traits = character_settings.get("traits", {})
        logger.debug(
            f"Fallback到规则生成, traits类型: {type(traits)}, keys: {list(traits.keys()) if isinstance(traits, dict) else 'N/A'}"
        )
        return self._generate_attributes_from_traits_rules(traits, character_settings)

    def _generate_attributes_from_traits_rules(
        self,
        traits: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        """
        Generate attributes using rule-based approach as fallback.

        Args:
            traits: Character traits dictionary
            character_settings: Complete character settings (optional, for wealth generation)

        Returns:
            Dictionary with energy, mood, knowledge, wealth values
        """
        logger.debug(f"规则生成属性开始: traits_type={type(traits)}")
        # Default values
        energy = 70
        mood = 60
        knowledge = 50
        wealth = 10000

        # 辅助函数：将 traits 值转换为小写字符串
        def to_lower_str(value) -> str:
            if isinstance(value, list):
                return " ".join(str(v).lower() for v in value)
            elif isinstance(value, str):
                return value.lower()
            else:
                return str(value).lower() if value else ""

        personality = to_lower_str(traits.get("personality", ""))
        abilities = to_lower_str(traits.get("abilities", ""))
        strengths = to_lower_str(traits.get("strengths", ""))
        weaknesses = to_lower_str(traits.get("weaknesses", ""))
        logger.debug(
            f"规则生成参数: personality={personality[:50]}..., abilities={abilities[:50]}..."
        )

        # Rule-based adjustments
        # Energy: based on age and physical traits
        if any(word in personality for word in ["活力", "精力充沛", "active", "energetic"]):
            energy += 10
        if any(word in personality for word in ["体弱", "虚弱", "weak", "frail"]):
            energy -= 15

        # Mood: based on personality
        if any(
            word in personality
            for word in ["乐观", "开朗", "积极", "optimistic", "cheerful", "positive"]
        ):
            mood += 15
        if any(
            word in personality
            for word in [
                "悲观",
                "内向",
                "消极",
                "pessimistic",
                "introverted",
                "negative",
            ]
        ):
            mood -= 15
        if any(word in strengths for word in ["自信", "自信", "confident"]):
            mood += 10

        # Knowledge: based on abilities and traits
        if any(
            word in abilities
            for word in ["聪明", "智慧", "博学", "smart", "intelligent", "learned"]
        ):
            knowledge += 20
        if any(word in abilities for word in ["天才", "天赋", "genius", "talented"]):
            knowledge += 15
        if any(
            word in weaknesses for word in ["缺乏经验", "无知", "lack of experience", "ignorant"]
        ):
            knowledge -= 20

        # Wealth: based on family background, era, and abilities
        if character_settings:
            family = character_settings.get("family", {})
            family_economy = family.get("family_economy", "").lower()
            family.get("family_description", "").lower()

            era = character_settings.get("era", {})
            era_description = era.get("era_description", "").lower()
            era.get("world_context", "").lower()

            age_info = character_settings.get("age", {})
            age = age_info.get("age", 22)

            # Family economy adjustments
            if any(
                word in family_economy for word in ["富裕", "富有", "wealthy", "rich", "affluent"]
            ):
                wealth += 50000
            elif any(word in family_economy for word in ["中产", "中等", "middle", "moderate"]):
                wealth += 20000
            elif any(word in family_economy for word in ["贫困", "贫穷", "poor", "poverty"]):
                wealth -= 5000

            # Era adjustments
            if any(word in era_description for word in ["现代", "当代", "modern", "contemporary"]):
                wealth += 10000
            elif any(word in era_description for word in ["古代", "ancient", "medieval"]):
                wealth -= 5000

            # Age adjustments (older characters may have more savings)
            if age >= 30:
                wealth += 15000
            elif age >= 25:
                wealth += 5000

            # Ability adjustments
            if any(
                word in abilities
                for word in ["商业", "投资", "business", "investment", "entrepreneur"]
            ):
                wealth += 20000

        # Clamp values
        energy = max(30, min(100, energy))
        mood = max(30, min(100, mood))
        knowledge = max(20, min(100, knowledge))
        wealth = max(0, min(1000000, wealth))

        result = {
            "energy": energy,
            "mood": mood,
            "knowledge": knowledge,
            "wealth": wealth,
        }
        logger.debug(f"规则生成属性完成: {result}")
        return result

    @staticmethod
    def _format_family_members(members: list, language: str = "zh") -> str:
        """Format family_members list, handling both str and dict formats."""
        if not members:
            return "无" if language == "zh" else "None"
        sep = "、" if language == "zh" else ", "
        if isinstance(members[0], dict):
            parts = [
                (
                    f"{m.get('name', '')}（{m.get('role', '')}）"
                    if language == "zh"
                    else f"{m.get('name', '')} ({m.get('role', '')})"
                )
                for m in members
                if m.get("name")
            ]
            return sep.join(parts) if parts else ("无" if language == "zh" else "None")
        return sep.join(str(m) for m in members)

    def _get_fallback_setting(self, setting_type: str) -> Dict[str, Any]:
        """Get fallback setting if AI generation fails."""
        if self.language == "zh":
            fallbacks = {
                "era": {
                    "year": 2024,
                    "era_description": "现代",
                    "world_context": "现代社会",
                },
                "age": {"age": 22, "birth_year": 2002, "age_description": "青年"},
                "gender": {"gender": "男", "gender_description": "男性"},
                "world": {
                    "world_description": "现代社会",
                    "technology_level": "现代科技",
                    "social_system": "现代社会制度",
                    "economy": "市场经济",
                },
                "family": {
                    "family_description": "普通家庭",
                    "family_members": ["父母"],
                    "family_economy": "中等",
                    "family_relationships": "和睦",
                },
                "relationships": {
                    "relationships_description": "玩家在社会中建立了多种关系，包括大学室友、导师、同事等关键人物，这些关系对玩家的发展有重要影响。",
                    "key_people": [
                        {
                            "name": "张明",
                            "role": "大学室友",
                            "relationship": "大学四年同住一室，性格互补，经常一起讨论人生规划",
                        },
                        {
                            "name": "李华",
                            "role": "高中同学",
                            "relationship": "高中时期的好友，现在在同一城市工作，周末常聚",
                        },
                        {
                            "name": "王教授",
                            "role": "大学导师",
                            "relationship": "在专业领域给予指导，对玩家的职业发展有重要影响",
                        },
                    ],
                },
                "traits": {
                    "traits_description": "普通青年",
                    "personality": "开朗",
                    "abilities": "学习能力强",
                    "interests": "广泛",
                    "strengths": "适应力强",
                    "weaknesses": "经验不足",
                },
                "wealth": {
                    "wealth": 30000,
                    "currency": "¥",
                    "currency_name": "人民币",
                    "wealth_description": "普通家庭的初始财富，主要来自家庭支持和少量个人积蓄。",
                },
            }
        else:
            fallbacks = {
                "era": {
                    "year": 2024,
                    "era_description": "Modern era",
                    "world_context": "Modern world",
                },
                "age": {
                    "age": 22,
                    "birth_year": 2002,
                    "age_description": "Young adult",
                },
                "gender": {"gender": "Male", "gender_description": "Male"},
                "world": {
                    "world_description": "Modern society",
                    "technology_level": "Modern technology",
                    "social_system": "Modern social system",
                    "economy": "Market economy",
                },
                "family": {
                    "family_description": "Average family",
                    "family_members": ["Parents"],
                    "family_economy": "Middle class",
                    "family_relationships": "Harmonious",
                },
                "relationships": {
                    "relationships_description": "The player has established various relationships in society, including college roommates, mentors, colleagues and other key people, which have important impacts on development.",
                    "key_people": [
                        {
                            "name": "Zhang Ming",
                            "role": "College Roommate",
                            "relationship": "Lived together for four years in college, complementary personalities, often discuss life plans",
                        },
                        {
                            "name": "Li Hua",
                            "role": "High School Classmate",
                            "relationship": "Friend from high school, now working in the same city, meet on weekends",
                        },
                        {
                            "name": "Professor Wang",
                            "role": "College Mentor",
                            "relationship": "Provides guidance in professional field, has important impact on career development",
                        },
                    ],
                },
                "traits": {
                    "traits_description": "Average young adult",
                    "personality": "Cheerful",
                    "abilities": "Strong learning ability",
                    "interests": "Wide range",
                    "strengths": "Strong adaptability",
                    "weaknesses": "Lack of experience",
                },
                "wealth": {
                    "wealth": 30000,
                    "currency": "$",
                    "currency_name": "Dollar",
                    "wealth_description": "Initial wealth from average family, mainly from family support and small personal savings.",
                },
            }

        return fallbacks.get(setting_type, {})  # type: ignore[return-value]

    def generate_opening_story(
        self, character_settings: Dict[str, Any], player_name: str, life_vision: str
    ) -> str:
        """
        Generate an opening story based on all character settings.
        Uses streaming to return story text progressively.

        Args:
            character_settings: All character settings
            player_name: Player's name
            life_vision: Player's life vision

        Returns:
            Opening story text (will be streamed in UI)
        """
        era = character_settings.get("era", {})
        age_info = character_settings.get("age", {})
        gender = character_settings.get("gender", {})
        family = character_settings.get("family", {})

        formatted_members = self._format_family_members(
            family.get("family_members", []), self.language
        )
        prompt = get_opening_story_prompt(
            character_settings=character_settings,
            player_name=player_name,
            life_vision=life_vision,
            formatted_family_members=formatted_members,
            language=self.language,
        )

        try:
            # Use generate_stream for raw streaming (returns stream object to UI)
            response = self.ai_generator.generate_stream(
                prompt=prompt,
                system_prompt="You are a skilled storyteller. Create engaging narrative openings based on character backgrounds.",
                temperature=0.9,
                max_tokens=4096,  # Maximum tokens - no truncation
            )

            return response  # type: ignore[return-value, no-any-return]  # Return the stream object
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Failed to generate opening story: {e}")
            # Fall through to fallback
        except Exception as e:
            logger.exception(f"Unexpected error generating opening story: {e}")

        # Return a fallback story
        if self.language == "zh":
            return iter(  # type: ignore[return-value]
                [
                    f"在{era.get('year', '某个')}年的{era.get('era_description', '某个时代')}，{player_name}站在人生的十字路口。{age_info.get('age', '年轻')}岁的{gender.get('gender', 'TA')}，心中怀揣着{life_vision}的梦想，即将开启一段全新的人生旅程..."
                ]
            )
        else:
            return iter(  # type: ignore[return-value]
                [
                    f"In the year {era.get('year', 'of a certain era')}, {player_name} stands at a crossroads. At {age_info.get('age', 'young')} years old, with a dream of {life_vision}, {gender.get('gender', 'they')} are about to embark on a new life journey..."
                ]
            )

    def generate_family_members_details(
        self, old_format_members: list, character_settings: dict, player_name: str
    ) -> list:
        """
        将旧格式的家庭成员列表升级为新格式。

        Args:
            old_format_members: 旧格式的家庭成员列表，如 ["父母", "弟弟"]
            character_settings: 角色设定字典
            player_name: 玩家名称

        Returns:
            新格式的家庭成员列表，包含 name, role, relationship
        """
        era_info = character_settings.get("era", {})
        family_desc = character_settings.get("family", {}).get("family_description", "")

        prompt = f"""请为以下家庭成员生成具体姓名。

主角姓名：{player_name}
时代背景：{era_info.get('era_description', '现代')}
家庭描述：{family_desc}
家庭成员：{', '.join(old_format_members)}

请为每个家庭成员生成具体姓名，返回JSON格式：
{{{{
    "members": [
        {{"name": "全名", "role": "角色（如父亲、母亲）", "relationship": "与主角的关系描述"}}
    ]
}}}}

**⚠️ 命名规则 - 必须严格匹配时代和地域文化：**
- 古代中国：使用古风名字，如"李青云"、"王婉儿"、"赵明轩"
- 现代中国：使用现代中文名字，如"张伟"、"李娜"、"王明"
- 民国时期：使用民国风格名字，如"林徽音"、"陈独秀"
- 欧美西方：使用英文名字，如"John Smith"、"Emma Watson"
- 日本：使用日文名字，如"田中一郎"、"佐藤美咲"
- 韩国：使用韩文名字，如"金智秀"、"朴俊浩"

注意：
- 姓名必须严格符合时代背景和地域文化
- 如果主角有姓，父母应该同姓（除非母亲娘家姓）
- 只返回JSON，不要其他内容"""

        try:
            data = self.ai_generator.generate_completion_json(
                prompt=prompt,
                system_prompt="你是一个人物信息生成器，生成符合背景设定的具体人物信息。",
                temperature=0.7,
                max_tokens=4096,  # Increased for detailed family info
            )
            if data:
                return data.get("members", [])  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"生成家庭成员详情失败: {e}")
        except Exception as e:
            logger.exception(f"生成家庭成员详情失败 (unexpected): {e}")

        return []

    def check_and_fix_missing_attributes(self, player_state) -> None:
        """
        检测并修复角色设定中缺失的属性。

        检测项目：
        1. family_members - 旧格式（字符串数组）需要升级为新格式（对象数组，包含具体姓名）
        2. birth_year - 如果缺失，根据 era.year 和 age.age 计算

        Args:
            player_state: PlayerState 实例
        """
        if not player_state or not player_state.character_settings:
            return

        character_settings = player_state.character_settings
        fixed_any = False

        # 1. 检查并修复 birth_year
        if "age" in character_settings:
            age_info = character_settings["age"]
            if "birth_year" not in age_info or age_info["birth_year"] is None:
                era_year = character_settings.get("era", {}).get("year", 2024)
                age = age_info.get("age", 22)
                birth_year = era_year - age
                age_info["birth_year"] = birth_year
                fixed_any = True
                logger.debug(f"修复缺失的 birth_year: {birth_year} (时代: {era_year}, 年龄: {age})")

        # 2. 检查并修复 family_members 格式
        if "family" in character_settings:
            family = character_settings["family"]
            raw_members = family.get("family_members", [])

            if raw_members and isinstance(raw_members[0], str):
                logger.debug(f"检测到旧格式 family_members: {raw_members}，尝试升级...")

                try:
                    player_name = player_state.player_name or "主角"
                    new_members = self.generate_family_members_details(
                        raw_members, character_settings, player_name
                    )
                    if new_members:
                        family["family_members"] = new_members
                        fixed_any = True
                        logger.debug(
                            f"升级 family_members 成功: {[m.get('name') for m in new_members]}"
                        )

                        for member in new_members:
                            name = member.get("name", "")
                            if name and name not in player_state.relationships:
                                player_state.relationships[name] = 60
                                logger.debug(f"添加家庭成员到关系列表: {name}")
                except (json.JSONDecodeError, ValueError, TypeError, KeyError) as e:
                    logger.warning(f"升级 family_members 失败: {e}")
                except Exception as e:
                    logger.exception(f"升级 family_members 失败 (unexpected): {e}")

        if fixed_any:
            logger.debug("角色设定属性已修复")
