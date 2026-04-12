"""实体识别服务。

从历史故事中识别重复出现的物品、人物、地点。
"""

import logging
from typing import Any, Dict, List, Optional

from src.services.base_extraction import BaseExtractionService

logger = logging.getLogger(__name__)


class EntityRecognitionService(BaseExtractionService):
    """从历史故事中识别实体的服务。"""

    # 继承 BaseExtractionService.__init__

    def recognize_from_history(
        self,
        round_history: List[Dict[str, Any]],
        existing_items: List[str],
        existing_characters: List[str],
        existing_landmarks: List[str],
        min_appearances: int = 3,
        language: str = "zh",
    ) -> Dict[str, List[Dict[str, Any]]]:
        """从历史记录中识别实体。

        Args:
            round_history: 回合历史记录列表
            existing_items: 已存在的物品名称列表
            existing_characters: 已存在的人物名称列表
            existing_landmarks: 已存在的地点名称列表
            min_appearances: 最少出现次数（默认3次）
            language: 语言代码

        Returns:
            {"items": [...], "characters": [...], "landmarks": [...]}
        """
        if not round_history:
            return {"items": [], "characters": [], "landmarks": []}

        try:
            # 构建完整故事文本
            story_text = self._build_story_text(round_history)

            # 使用基类的截断逻辑
            story_text = self._truncate_story(story_text)

            # 统计有效事件数量
            valid_events = sum(
                1 for entry in round_history
                if entry.get("event_description") or entry.get("story_continuation") or entry.get("summary")
            )
            logger.info(
                f"Entity recognition: {len(round_history)} rounds, "
                f"{valid_events} valid events, story text {len(story_text)} chars, "
                f"min_appearances={min_appearances}"
            )

            from config.prompts.entity_recognition_prompt import \
                get_entity_recognition_prompt

            prompt = get_entity_recognition_prompt(
                story_text=story_text,
                existing_items=existing_items,
                existing_characters=existing_characters,
                existing_landmarks=existing_landmarks,
                min_appearances=min_appearances,
                language=language,
            )

            sys_prompt = self._get_system_prompt("story_analyzer", language)

            response = self._call_ai(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=2048,
            )

            logger.info(f"AI raw response (first 500 chars): {response[:500]}")

            result = self._parse_recognition_response(response)
            logger.info(
                f"Parsed entities: {len(result.get('items', []))} items, "
                f"{len(result.get('characters', []))} characters, "
                f"{len(result.get('landmarks', []))} landmarks"
            )
            return result

        except Exception as e:
            logger.error(f"Entity recognition failed: {e}", exc_info=True)
            return {"items": [], "characters": [], "landmarks": []}

    def extract_item_description(
        self,
        item_name: str,
        round_history: List[Dict[str, Any]],
        language: str = "zh",
    ) -> Optional[Dict[str, Any]]:
        """从历史中提取特定物品的描述。

        Args:
            item_name: 物品名称
            round_history: 回合历史记录
            language: 语言代码

        Returns:
            物品信息字典，失败返回None
        """
        try:
            # 收集包含该物品的上下文
            contexts = []
            for entry in round_history:
                text_parts = []
                if entry.get("event_description"):
                    text_parts.append(entry["event_description"])
                if entry.get("story_continuation"):
                    text_parts.append(entry["story_continuation"])

                text = " ".join(text_parts)
                if item_name in text:
                    contexts.append(text[:800])  # 截取相关片段

            if not contexts:
                return None

            # 限制上下文数量
            contexts = contexts[:5]
            story_text = "\n\n---\n\n".join(contexts)

            from config.prompts.entity_recognition_prompt import \
                get_item_description_extraction_prompt

            prompt = get_item_description_extraction_prompt(
                item_name=item_name,
                story_text=story_text,
                language=language,
            )

            sys_prompt = self._get_system_prompt("story_analyzer", language)

            response = self._call_ai(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.5,
                max_tokens=2048,
            )

            data = self._parse_json_response(response)
            if data and "name" in data:
                return {
                    "name": data["name"],
                    "description": data.get("description", ""),
                    "category": data.get("category", "other"),
                    "importance": data.get("importance", "normal"),
                    "acquired_context": contexts[0][:200] if contexts else "",
                    "is_key_item": data.get("importance") == "critical",
                }

            return None

        except Exception as e:
            logger.error(f"Failed to extract item description: {e}")
            return None

    def _build_story_text(self, round_history: List[Dict[str, Any]]) -> str:
        """将round_history构建成完整的故事文本。

        即使 event_description 缺失，也会从 story_continuation、summary、
        choice 等字段中尽可能构建完整的上下文。

        Args:
            round_history: 回合历史记录

        Returns:
            格式化的故事文本
        """
        story_parts = []

        # 按周和回合排序
        sorted_history = sorted(round_history, key=lambda x: (x.get("week", 0), x.get("round", 0)))

        for entry in sorted_history:
            week = entry.get("week", 0) + 1
            round_num = entry.get("round", 0)
            round_names = ["周一", "周中", "周末"]
            round_name = round_names[round_num] if round_num < 3 else f"回合{round_num}"

            # 收集本回合所有文本片段
            parts = []

            if entry.get("event_description"):
                parts.append(f"事件：{entry['event_description']}")

            if entry.get("choice"):
                parts.append(f"选择：{entry['choice']}")

            if entry.get("story_continuation"):
                parts.append(f"结果：{entry['story_continuation']}")

            if entry.get("summary"):
                parts.append(f"总结：{entry['summary']}")

            # 仅当有实际内容时才添加该回合
            if parts:
                story_parts.append(f"\n=== 第{week}周 {round_name} ===\n")
                story_parts.extend(parts)

        return "\n".join(story_parts)

    def _parse_recognition_response(self, response: str) -> Dict[str, List[Dict[str, Any]]]:
        """解析AI识别响应。

        Args:
            response: AI响应文本

        Returns:
            解析后的实体字典
        """
        try:
            data = self._parse_json_response(response)
            if not data:
                return {"items": [], "characters": [], "landmarks": []}

            result: dict[str, Any] = {"items": [], "characters": [], "landmarks": []}

            # 解析物品
            for item in data.get("items", []):
                if self._validate_entity(item):
                    result["items"].append(item)

            # 解析人物
            for char in data.get("characters", []):
                if self._validate_entity(char):
                    result["characters"].append(char)

            # 解析地点
            for landmark in data.get("landmarks", []):
                if self._validate_entity(landmark):
                    result["landmarks"].append(landmark)

            logger.info(
                f"Entity recognition completed: {len(result['items'])} items, "
                f"{len(result['characters'])} characters, "
                f"{len(result['landmarks'])} landmarks"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to parse recognition response: {e}")
            return {"items": [], "characters": [], "landmarks": []}

    def _validate_entity(self, entity: Dict[str, Any]) -> bool:
        """验证实体数据是否有效。

        Args:
            entity: 实体数据字典

        Returns:
            是否有效
        """
        if not entity.get("name"):
            return False

        # 使用基类的验证方法
        entity["importance"] = self._validate_importance(entity.get("importance", "normal"))

        # 验证出现次数
        appear_count = entity.get("appear_count", 0)
        if not isinstance(appear_count, int) or appear_count < 1:
            entity["appear_count"] = 1

        # 确保appear_contexts是列表
        if "appear_contexts" not in entity or not isinstance(entity["appear_contexts"], list):
            entity["appear_contexts"] = []

        return True
