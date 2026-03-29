"""玩家角色管理逻辑。

此模块定义了 PlayerState 的角色管理部分，作为 Mixin 类供 PlayerState 继承。
包含角色的添加、获取、更新、删除和关系管理等方法。
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.game.state.character_state import CharacterState
    from src.game.state.player_state import PlayerState

logger = logging.getLogger(__name__)


class PlayerCharactersMixin:
    """玩家角色管理 Mixin。

    包含 NPC 角色的增删改查和关系同步方法。
    """

    # 类型声明：这些属性由 PlayerDataMixin 定义，在组合类中可用
    characters: Dict[str, Dict[str, Any]]
    relationships: Dict[str, int]

    def add_character(self, character: "CharacterState") -> None:
        """
        添加或更新一个NPC角色。
        同时同步到relationships字典保持兼容性。

        Args:
            character: CharacterState实例
        """
        self.characters[character.name] = character.model_dump()
        # 同步到relationships字典
        self.relationships[character.name] = character.affinity
        logger.debug(f"Added character: {character.name} with affinity {character.affinity}")

    def get_character(self, name: str) -> Optional["CharacterState"]:
        """
        获取指定名字的NPC角色。

        Args:
            name: 角色名字

        Returns:
            CharacterState实例，不存在则返回None
        """
        from src.game.state.character_state import CharacterState

        if name in self.characters:
            return CharacterState(**self.characters[name])
        return None

    def get_all_characters(self) -> List["CharacterState"]:
        """
        获取所有NPC角色。

        Returns:
            CharacterState列表
        """
        from src.game.state.character_state import CharacterState

        return [CharacterState(**data) for data in self.characters.values()]

    def update_character(self, name: str, **kwargs) -> bool:
        """
        更新指定角色的属性。

        Args:
            name: 角色名字
            **kwargs: 要更新的属性

        Returns:
            是否更新成功
        """
        if name not in self.characters:
            logger.warning(f"Character not found: {name}")
            return False

        character_data = self.characters[name]
        for key, value in kwargs.items():
            if key in character_data:
                character_data[key] = value

        self.characters[name] = character_data

        # 如果更新了affinity，同步到relationships
        if "affinity" in kwargs:
            self.relationships[name] = kwargs["affinity"]

        return True

    def update_character_relationship(
        self,
        name: str,
        affinity_change: int = 0,
        trust_change: int = 0,
        respect_change: int = 0,
        mood_change: int = 0,
        interaction_summary: str = "",
    ) -> bool:
        """Update character relationship. Delegates to PlayerService."""
        # Cast self to PlayerState for type checking
        from typing import cast

        from src.game.player_service import PlayerService

        if TYPE_CHECKING:
            from src.game.state.player_state import PlayerState
        return PlayerService.update_character_relationship(
            cast("PlayerState", self),
            name,
            affinity_change,
            trust_change,
            respect_change,
            mood_change,
            interaction_summary,
        )

    def sync_relationships_to_characters(self) -> None:
        """
        将relationships字典的变化同步到characters。
        用于处理通过旧API更新的关系值。
        """
        for name, affinity in self.relationships.items():
            if name in self.characters:
                self.characters[name]["affinity"] = affinity

    def sync_characters_to_relationships(self) -> None:
        """
        将characters的affinity同步到relationships。
        """
        for name, char_data in self.characters.items():
            self.relationships[name] = char_data.get("affinity", 50)

    def get_characters_context(self) -> str:
        """Generate AI context string for all characters. Delegates to PlayerService."""
        from typing import cast

        from src.game.player_service import PlayerService

        if TYPE_CHECKING:
            from src.game.state.player_state import PlayerState
        return PlayerService.get_characters_context(cast("PlayerState", self))

    def check_character_events(self) -> List[Dict[str, Any]]:
        """Check all characters for special event triggers. Delegates to PlayerService."""
        from typing import cast

        from src.game.player_service import PlayerService

        if TYPE_CHECKING:
            from src.game.state.player_state import PlayerState
        return PlayerService.check_character_events(cast("PlayerState", self))

    def initialize_characters_from_settings(self) -> None:
        """Initialize character system from character_settings. Delegates to PlayerService."""
        from typing import cast

        from src.game.player_service import PlayerService

        if TYPE_CHECKING:
            from src.game.state.player_state import PlayerState
        PlayerService.initialize_characters_from_settings(cast("PlayerState", self))

    def remove_character(self, name: str) -> bool:
        """删除指定名称的角色。

        Args:
            name: 角色名称

        Returns:
            是否删除成功
        """
        if name in self.characters:
            del self.characters[name]
            # 同时从relationships中删除
            if name in self.relationships:
                del self.relationships[name]
            logger.info(f"Removed character: {name}")
            return True
        logger.warning(f"Character not found for removal: {name}")
        return False
