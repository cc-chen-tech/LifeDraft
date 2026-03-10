"""标志物提取服务。

从故事中提取重要地点/场景，并更新到玩家状态中。
"""

import logging
from typing import Any, Dict, List, Optional

from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json
from src.game.state.landmark_state import LandmarkState

logger = logging.getLogger(__name__)


class LandmarkExtractionService:
    """从故事中提取重要地点/场景的服务。

    复用 StoryAnalyzer 的模式，专门用于提取标志物信息。
    """

    def __init__(self, ai_client):
        """
        Args:
            ai_client: AIClient 实例
        """
        self.ai_client = ai_client

    def extract_landmarks_from_story(
        self,
        story_text: str,
        existing_landmarks: Dict[str, Dict[str, Any]],
        character_settings: Dict[str, Any],
        current_week: int,
        language: str = "zh",
    ) -> List[Dict[str, Any]]:
        """从故事中提取重要地点/场景。

        Args:
            story_text: 故事文本
            existing_landmarks: 已存在的标志物字典 {name: LandmarkState_dict}
            character_settings: 角色设定
            current_week: 当前周数
            language: 语言代码

        Returns:
            包含新标志物和更新信息的列表，格式为:
            [{"action": "new", "landmark": LandmarkState}, {"action": "update", "name": "..."}]
        """
        if not story_text:
            return []

        try:
            from config.prompts.landmark_extraction_prompt import \
                get_landmark_extraction_prompt

            # 构建已存在标志物列表
            existing_landmarks_list = (
                list(existing_landmarks.values()) if existing_landmarks else []
            )

            prompt = get_landmark_extraction_prompt(
                story_text=story_text,
                existing_landmarks=existing_landmarks_list,
                character_settings=character_settings,
                current_week=current_week,
                language=language,
            )

            sys_prompt = get_system_prompt("story_analyzer", language)

            response = self.ai_client.call(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=2048,
            )

            return self._parse_extraction_response(
                response=response,
                current_week=current_week,
                existing_landmarks=existing_landmarks,
            )

        except Exception as e:
            logger.error(f"标志物提取失败: {e}")
            return []

    def _parse_extraction_response(
        self,
        response: str,
        current_week: int,
        existing_landmarks: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """解析AI响应，提取标志物信息。

        Args:
            response: AI响应文本
            current_week: 当前周数
            existing_landmarks: 已存在的标志物

        Returns:
            包含新标志物和更新信息的列表
        """
        try:
            data = extract_json(response)
            if not data:
                logger.warning("无法解析标志物提取响应为JSON")
                return []

            raw_landmarks = data.get("landmarks", [])
            results: List[Dict[str, Any]] = []

            for raw in raw_landmarks:
                action = raw.get("action", "new")
                name = raw.get("name", "")

                if not name:
                    continue

                if action == "update":
                    # 更新已存在的标志物
                    if name in existing_landmarks:
                        results.append({"action": "update", "name": name})
                        logger.info(f"📍 标志物再次出现: {name}")
                    continue

                if action == "new":
                    # 验证重要程度
                    importance = raw.get("importance", "normal")
                    if importance not in ("critical", "important", "normal"):
                        importance = "normal"

                    # 验证类别
                    category = raw.get("category", "other")
                    if category not in ("building", "nature", "room", "area", "other"):
                        category = "other"

                    landmark = LandmarkState(
                        name=name,
                        description=raw.get("description", ""),
                        category=category,
                        importance=importance,
                        first_appear_week=current_week,
                        appear_count=1,
                        last_appear_week=current_week,
                        context=raw.get("context", ""),
                        is_key_location=raw.get("is_key_location", False),
                        metadata=raw.get("metadata", {}),
                        image_generated=False,
                    )

                    results.append({"action": "new", "landmark": landmark})
                    logger.info(f"📍 提取到新标志物: {name} ({category}/{importance})")

            return results

        except Exception as e:
            logger.error(f"解析标志物提取响应失败: {e}")
            return []

    def generate_landmark_description(
        self,
        landmark_name: str,
        landmark_category: str,
        context: str,
        story_context: str,
        language: str = "zh",
    ) -> Optional[str]:
        """为地点/场景生成详细描述。

        Args:
            landmark_name: 地点名称
            landmark_category: 地点类别
            context: 场景描述
            story_context: 相关故事上下文
            language: 语言代码

        Returns:
            生成的描述，失败返回None
        """
        try:
            from config.prompts.landmark_extraction_prompt import \
                get_landmark_description_generation_prompt

            prompt = get_landmark_description_generation_prompt(
                landmark_name=landmark_name,
                landmark_category=landmark_category,
                context=context,
                story_context=story_context,
                language=language,
            )

            sys_prompt = get_system_prompt("story_analyzer", language)

            response = self.ai_client.call(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.7,
                max_tokens=1024,
            )

            data = extract_json(response)
            if data and "description" in data:
                return data["description"]

            return None

        except Exception as e:
            logger.error(f"生成标志物描述失败: {e}")
            return None
