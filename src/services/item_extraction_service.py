"""物品提取服务。

从故事中提取重要物品，并更新到玩家状态中。
"""

import logging
from typing import Any, Dict, List, Optional

from src.game.state.item_state import ItemState
from src.services.base_extraction import BaseExtractionService

logger = logging.getLogger(__name__)

# 物品有效类别
ITEM_CATEGORIES = ("weapon", "tool", "keepsake", "treasure", "document", "other")


class ItemExtractionService(BaseExtractionService):
    """从故事中提取重要物品的服务。

    复用 StoryAnalyzer 的模式，专门用于提取物品信息。
    """

    # 继承 BaseExtractionService.__init__

    def extract_items_from_story(
        self,
        story_text: str,
        existing_items: Dict[str, Dict[str, Any]],
        character_settings: Dict[str, Any],
        current_week: int,
        language: str = "zh",
    ) -> List[ItemState]:
        """从故事中提取重要物品。

        Args:
            story_text: 故事文本
            existing_items: 已存在的物品字典 {name: ItemState_dict}
            character_settings: 角色设定
            current_week: 当前周数
            language: 语言代码

        Returns:
            新提取的物品列表
        """
        if not story_text:
            return []

        try:
            from config.prompts.item_extraction_prompt import get_item_extraction_prompt

            # 构建已存在物品列表
            existing_items_list = (
                list(existing_items.values()) if existing_items else []
            )

            prompt = get_item_extraction_prompt(
                story_text=story_text,
                existing_items=existing_items_list,
                character_settings=character_settings,
                current_week=current_week,
                language=language,
            )

            sys_prompt = self._get_system_prompt("story_analyzer", language)

            response = self._call_ai(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=2048,
            )

            return self._parse_extraction_response(
                response=response,
                current_week=current_week,
            )

        except Exception as e:
            logger.error(f"物品提取失败: {e}")
            return []

    def _parse_extraction_response(
        self,
        response: str,
        current_week: int,
    ) -> List[ItemState]:
        """解析AI响应，提取物品信息。

        Args:
            response: AI响应文本
            current_week: 当前周数

        Returns:
            物品列表
        """
        try:
            data = self._parse_json_response(response)
            if not data:
                return []

            raw_items = data.get("items", [])
            results: List[ItemState] = []

            for raw in raw_items:
                action = raw.get("action", "new")
                if action != "new":
                    continue

                name = raw.get("name", "")
                if not name:
                    continue

                # 使用基类的验证方法
                importance = self._validate_importance(raw.get("importance", "normal"))

                # 验证类别
                category = self._validate_category(
                    raw.get("category", "other"),
                    ITEM_CATEGORIES,
                )

                item = ItemState(
                    name=name,
                    description=raw.get("description", ""),
                    importance=importance,
                    category=category,
                    acquired_week=current_week,
                    acquired_context=raw.get("acquired_context", ""),
                    is_key_item=raw.get("is_key_item", False),
                    metadata=raw.get("metadata", {}),
                    image_generated=False,
                    description_generated=False,
                )

                results.append(item)
                logger.info(f"📦 提取到新物品: {name} ({category}/{importance})")

            return results

        except Exception as e:
            logger.error(f"解析物品提取响应失败: {e}")
            return []

    def generate_item_description(
        self,
        item_name: str,
        item_category: str,
        acquired_context: str,
        story_context: str,
        language: str = "zh",
    ) -> Optional[str]:
        """为物品生成详细描述。

        Args:
            item_name: 物品名称
            item_category: 物品类别
            acquired_context: 获得场景
            story_context: 相关故事上下文
            language: 语言代码

        Returns:
            生成的描述，失败返回None
        """
        try:
            from config.prompts.item_extraction_prompt import (
                get_item_description_generation_prompt,
            )

            prompt = get_item_description_generation_prompt(
                item_name=item_name,
                item_category=item_category,
                acquired_context=acquired_context,
                story_context=story_context,
                language=language,
            )

            sys_prompt = self._get_system_prompt("story_analyzer", language)

            response = self._call_ai(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.7,
                max_tokens=1024,
            )

            data = self._parse_json_response(response)
            if data and "description" in data:
                return data["description"]

            return None

        except Exception as e:
            logger.error(f"生成物品描述失败: {e}")
            return None
