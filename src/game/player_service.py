"""Player business logic service — extracted from PlayerState to separate data from behavior."""

import logging
from typing import Any, Dict, List

from src.game.state import CharacterState, PlayerState

logger = logging.getLogger(__name__)


class PlayerService:
    """Handles complex player-related business operations on PlayerState data."""

    @staticmethod
    def initialize_characters_from_settings(player_state: PlayerState) -> None:
        """
        从 character_settings 中初始化角色系统。
        将 key_people 转换为 CharacterState。
        保留已有的 relationships 值。

        Args:
            player_state: PlayerState 实例
        """
        if not player_state.character_settings:
            return

        relationships_data = player_state.character_settings.get("relationships", {})
        key_people = relationships_data.get("key_people", [])

        # 保存已有的关系值
        existing_relationships = player_state.relationships.copy()

        for person in key_people:
            if not person.get("name"):
                continue

            name = person.get("name")

            # 检查是否已经是完整的 CharacterState 格式
            if "affinity" in person and "personality_traits" in person:
                try:
                    character = CharacterState(**person)
                except Exception as e:
                    logger.warning(f"Failed to create CharacterState from rich data: {e}")
                    character = CharacterState.from_simple_dict(person)
            else:
                character = CharacterState.from_simple_dict(person)

            # 如果已有关系值，使用已有值而不是默认值
            if name in existing_relationships:
                character.affinity = existing_relationships[name]

            player_state.add_character(character)

        logger.info(f"Initialized {len(player_state.characters)} characters from settings")

    @staticmethod
    def update_character_relationship(
        player_state: PlayerState,
        name: str,
        affinity_change: int = 0,
        trust_change: int = 0,
        respect_change: int = 0,
        mood_change: int = 0,
        interaction_summary: str = "",
    ) -> bool:
        """
        更新角色与主角的关系属性。

        Args:
            player_state: PlayerState 实例
            name: 角色名字
            affinity_change: 亲密度变化
            trust_change: 信任度变化
            respect_change: 尊重度变化
            mood_change: 角色情绪变化
            interaction_summary: 互动简述

        Returns:
            是否更新成功
        """
        character = player_state.get_character(name)
        if not character:
            logger.warning(f"Character not found for relationship update: {name}")
            return False

        # 更新关系属性
        if affinity_change or trust_change or respect_change:
            character.update_relationship(affinity_change, trust_change, respect_change)

        # 更新情绪
        if mood_change:
            character.update_mood(mood_change)

        # 记录互动
        if interaction_summary:
            character.record_interaction(player_state.week, interaction_summary)

        # 保存回字典
        player_state.characters[name] = character.model_dump()

        # 同步affinity到relationships
        player_state.relationships[name] = character.affinity

        return True

    @staticmethod
    def check_character_events(player_state: PlayerState) -> List[Dict[str, Any]]:
        """
        检查所有角色是否触发特殊事件。

        Args:
            player_state: PlayerState 实例

        Returns:
            触发的事件列表 [{"name": ..., "event_type": ..., "character": ...}]
        """
        triggered_events = []
        event_types = [
            "deep_friendship",
            "conflict",
            "help_request",
            "secret_sharing",
            "betrayal_risk",
        ]

        for char_data in player_state.characters.values():
            character = CharacterState(**char_data)
            for event_type in event_types:
                if character.check_event_trigger(event_type):
                    triggered_events.append(
                        {
                            "name": character.name,
                            "event_type": event_type,
                            "character": character,
                        }
                    )

        return triggered_events

    @staticmethod
    def get_characters_context(player_state: PlayerState) -> str:
        """
        生成用于AI上下文的所有角色描述。

        Args:
            player_state: PlayerState 实例

        Returns:
            所有角色的上下文字符串
        """
        if not player_state.characters:
            return ""

        context_parts = ["【重要人物】"]
        for char_data in player_state.characters.values():
            character = CharacterState(**char_data)
            context_parts.append(character.to_context_string())

        return "\n\n".join(context_parts)

    @staticmethod
    def check_event_trigger(character: CharacterState, event_type: str) -> bool:
        """
        检查角色是否满足特殊事件触发条件。

        Args:
            character: CharacterState 实例
            event_type: 事件类型

        Returns:
            是否满足触发条件
        """
        threshold = character.event_triggers.get(event_type)
        if threshold is None:
            return False

        if event_type in ["deep_friendship", "secret_sharing"]:
            return character.affinity >= threshold and character.trust >= threshold - 10
        elif event_type in ["conflict", "betrayal_risk"]:
            return character.affinity <= threshold or character.trust <= threshold
        elif event_type == "help_request":
            return character.affinity >= threshold

        return False
