"""Story rewriting service.

Handles segment-level story rewriting and full story regeneration.
"""

import json
import logging
from typing import Any, Callable, Dict, Optional

from config.prompts import get_story_only_prompt
from src.ai.client import AIClient
from src.ai.system_prompts import get_system_prompt

logger = logging.getLogger(__name__)


class StoryRewriter:
    """Rewrites or regenerates stories."""

    def __init__(self, client: AIClient):
        self.client = client

    # -------------------- Public API --------------------

    def rewrite_story_segment(
        self,
        full_story: str,
        segment_to_replace: str,
        user_instruction: str,
        character_settings: Optional[Dict[str, Any]],
        story_context: str,
        language: str = "zh",
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        world_model=None,
        player_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Rewrite a specified segment of the story.

        Args:
            full_story: Current complete story
            segment_to_replace: Segment to rewrite
            user_instruction: User's rewrite request
            character_settings: Character settings
            story_context: Previous story context (summary)
            language: Language code
            stream_callback: Optional streaming callback
            status_callback: Optional status callback for validation
            world_model: WorldModel for consistency validation
            player_state: Player state dict for validation

        Returns:
            Rewritten complete story
        """
        logger.info(f"Rewriting story segment: {len(segment_to_replace)} chars")

        if language == "zh":
            prompt = f"""你是一位才华横溢的小说家。请改写以下故事中的指定段落，同时保持故事的连贯性和逻辑一致性。

【当前完整故事】
{full_story}

【需要改写的段落】
{segment_to_replace}

【用户的改写要求】
{user_instruction}

【角色设定】
{json.dumps(character_settings, ensure_ascii=False, indent=2) if character_settings else '无'}

【之前的故事脉络】
{story_context if story_context else '无'}

请根据用户的要求改写指定段落，要求：
1. 满足用户的改写要求
2. 保持与前后文的逻辑一致性
3. 保持与角色设定的一致性
4. 保持故事的文学性和流畅性
5. 只返回改写后的完整故事，不要任何解释或JSON格式
"""
        else:
            prompt = f"""You are a talented novelist. Please rewrite the specified segment of the following story while maintaining narrative coherence and logical consistency.

[Current Full Story]
{full_story}

[Segment to Rewrite]
{segment_to_replace}

[User's Rewrite Request]
{user_instruction}

[Character Settings]
{json.dumps(character_settings, indent=2) if character_settings else 'None'}

[Previous Story Context]
{story_context if story_context else 'None'}

Please rewrite the specified segment according to the user's request:
1. Satisfy the user's rewrite requirements
2. Maintain logical consistency with the surrounding text
3. Maintain consistency with character settings
4. Keep the story's literary quality and flow
5. Return ONLY the complete rewritten story, no explanations or JSON format
"""

        sys_prompt = get_system_prompt("story_rewriter", language)

        try:
            rewritten_story = self.client.call(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.8,
                max_tokens=4096,
                stream_callback=stream_callback,
            )

            # ★ 一致性校验（如果有 world_model）- 复用 StoryGenerator 的方法
            if world_model and player_state:
                from src.ai.story_generator import StoryGenerator

                # 创建临时 StoryGenerator 实例来复用验证方法
                temp_generator = StoryGenerator(self.client)
                rewritten_story = temp_generator._validate_and_retry_story(
                    story_text=rewritten_story,
                    world_model=world_model,
                    player_state=player_state,
                    character_settings=character_settings or {},
                    language=language,
                    original_prompt=prompt,
                    sys_prompt=sys_prompt,
                    stream_callback=stream_callback,
                    status_callback=status_callback,
                )

            return rewritten_story

        except Exception as e:
            logger.error(f"Failed to rewrite story segment: {e}")
            # Return original story as fallback
            return full_story

    def regenerate_story(
        self,
        player_state: Dict[str, Any],
        character_settings: Optional[Dict[str, Any]],
        story_context: str,
        language: str = "zh",
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        world_model=None,
        opening_story: Optional[str] = None,
        last_event_description: Optional[str] = None,
    ) -> str:
        """
        Regenerate the entire round's story.

        Args:
            player_state: Current player state
            character_settings: Character settings
            story_context: Previous story context (summary)
            language: Language code
            stream_callback: Optional streaming callback
            status_callback: Optional status callback for validation
            world_model: WorldModel for consistency validation
            opening_story: Opening story for context
            last_event_description: Last event description

        Returns:
            Newly generated story text
        """
        logger.info("Regenerating entire story")

        # Determine life phase
        week = player_state.get("week", 0)
        if week < 24:
            current_phase = "early_career"
        elif week < 48:
            current_phase = "establishing"
        elif week < 72:
            current_phase = "growth"
        else:
            current_phase = "consolidation"

        # Derive context from parameters
        if not last_event_description:
            decision_history = player_state.get("decision_history", [])
            if decision_history:
                last_event_description = decision_history[-1].get("event")

        story_prompt = get_story_only_prompt(
            player_state,
            language,
            current_phase,
            character_settings,
            opening_story,
            last_event_description,
            None,
            None,
        )

        # Add previous story context
        if story_context:
            if language == "zh":
                story_prompt = f"""【之前的故事脉络】
{story_context}

{story_prompt}

请根据以上上下文，生成一个全新的故事，确保与之前的故事保持逻辑一致性。"""
            else:
                story_prompt = f"""[Previous Story Context]
{story_context}

{story_prompt}

Please generate a brand new story based on the above context, ensuring logical consistency with the previous story."""

        sys_prompt = get_system_prompt("story_novelist", language)

        try:
            regenerated_story = self.client.call(
                system_prompt=sys_prompt,
                user_prompt=story_prompt,
                temperature=0.75,  # 从 1.0 降至 0.75，减少幻觉
                max_tokens=4096,
                stream_callback=stream_callback,
            )

            # ★ 一致性校验（如果有 world_model）- 复用 StoryGenerator 的方法
            if world_model and player_state:
                from src.ai.story_generator import StoryGenerator

                # 创建临时 StoryGenerator 实例来复用验证方法
                temp_generator = StoryGenerator(self.client)
                regenerated_story = temp_generator._validate_and_retry_story(
                    story_text=regenerated_story,
                    world_model=world_model,
                    player_state=player_state,
                    character_settings=character_settings or {},
                    language=language,
                    original_prompt=story_prompt,
                    sys_prompt=sys_prompt,
                    stream_callback=stream_callback,
                    status_callback=status_callback,
                )

            return regenerated_story

        except Exception as e:
            logger.error(f"Failed to regenerate story: {e}")
            if language == "zh":
                return "生成故事失败，请重试。"
            else:
                return "Failed to generate story, please try again."
