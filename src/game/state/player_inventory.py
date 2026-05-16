"""玩家物品管理逻辑。

此模块定义了 PlayerState 的物品管理部分，作为 Mixin 类供 PlayerState 继承。
包含物品的添加、获取、更新、删除和上下文生成等方法。
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.game.state.item_state import ItemState

logger = logging.getLogger(__name__)


class PlayerInventoryMixin:
    """玩家物品管理 Mixin。

    包含重要物品的增删改查和上下文生成方法。
    """

    # 类型声明：这些属性由 PlayerDataMixin 定义，在组合类中可用
    items: Dict[str, Dict[str, Any]]

    def add_item(self, item: "ItemState") -> None:
        """
        添加或更新一个重要物品。

        Args:
            item: ItemState实例
        """

        self.items[item.name] = item.model_dump()
        logger.debug(f"Added item: {item.name} (importance: {item.importance})")

    def get_item(self, name: str) -> Optional["ItemState"]:
        """
        获取指定名称的物品。

        Args:
            name: 物品名称

        Returns:
            ItemState实例，不存在则返回None
        """
        from src.game.state.item_state import ItemState

        if name in self.items:
            return ItemState(**self.items[name])
        return None

    def get_all_items(self) -> List["ItemState"]:
        """
        获取所有重要物品。

        Returns:
            ItemState列表
        """
        from src.game.state.item_state import ItemState

        return [ItemState(**data) for data in self.items.values()]

    def get_key_items(self) -> List["ItemState"]:
        """
        获取所有关键物品。

        Returns:
            关键物品的ItemState列表
        """
        from src.game.state.item_state import ItemState

        return [ItemState(**data) for data in self.items.values() if data.get("is_key_item", False)]

    def update_item(self, name: str, **kwargs) -> bool:
        """
        更新指定物品的属性。

        Args:
            name: 物品名称
            **kwargs: 要更新的属性

        Returns:
            是否更新成功
        """
        if name not in self.items:
            logger.warning(f"Item not found: {name}")
            return False

        item_data = self.items[name]
        for key, value in kwargs.items():
            if key in item_data or key in [
                "image_url",
                "image_generated",
                "description",
                "description_generated",
            ]:
                item_data[key] = value

        self.items[name] = item_data
        return True

    def get_items_context(self) -> str:
        """
        生成用于AI上下文的物品描述。

        Returns:
            物品描述字符串
        """
        from src.game.state.item_state import ItemState

        if not self.items:
            return "无重要物品"

        item_strings = []
        for item_data in self.items.values():
            item = ItemState(**item_data)
            item_strings.append(item.to_context_string())

        return "\n\n".join(item_strings)

    def remove_item(self, name: str) -> bool:
        """删除指定名称的物品。

        Args:
            name: 物品名称

        Returns:
            是否删除成功
        """
        if name in self.items:
            del self.items[name]
            logger.info(f"Removed item: {name}")
            return True
        logger.warning(f"Item not found for removal: {name}")
        return False
