"""物品状态模型。

此模块定义了ItemState类，用于管理重要物品的状态。
"""

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ItemState(BaseModel):
    """重要物品状态。

    用于追踪故事中获得的重要物品，包括关键道具、纪念品、武器等。
    """

    # ===== 基础信息 =====
    name: str = Field(..., description="物品名称")
    description: str = Field(default="", description="物品描述")

    # ===== 分类信息 =====
    importance: str = Field(
        default="normal",
        description="重要程度：critical(关键物品)/important(重要物品)/normal(普通物品)",
    )
    category: str = Field(
        default="other",
        description="物品类别：weapon(武器)/tool(工具)/keepsake(纪念品)/treasure(宝物)/document(文件)/other(其他)",
    )

    # ===== 获得信息 =====
    acquired_week: int = Field(default=0, ge=0, description="获得周数")
    acquired_context: str = Field(default="", description="获得场景描述")

    # ===== 标记 =====
    is_key_item: bool = Field(default=False, description="是否关键物品")

    # ===== 元数据 =====
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="额外元数据（外观、特殊能力、来源等）"
    )

    # ===== 图片信息 =====
    image_url: Optional[str] = Field(default=None, description="物品图片URL")
    image_generated: bool = Field(default=False, description="是否已生成图片")

    # ===== 描述生成 =====
    description_generated: bool = Field(default=False, description="是否已AI生成描述")

    def to_context_string(self) -> str:
        """
        生成用于AI上下文的物品描述。

        Returns:
            物品描述字符串
        """
        parts = [f"【{self.name}】"]

        if self.description:
            parts.append(f"描述：{self.description}")

        if self.category != "other":
            category_names = {
                "weapon": "武器",
                "tool": "工具",
                "keepsake": "纪念品",
                "treasure": "宝物",
                "document": "文件",
            }
            parts.append(f"类型：{category_names.get(self.category, self.category)}")

        if self.is_key_item:
            parts.append("★ 关键物品")

        if self.acquired_context:
            parts.append(f"获得场景：{self.acquired_context}")

        return "\n".join(parts)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ItemState":
        """
        从字典创建ItemState实例。

        Args:
            data: 物品数据字典

        Returns:
            ItemState实例
        """
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式。

        Returns:
            物品数据字典
        """
        return self.model_dump()


# 物品类别映射
ITEM_CATEGORY_LABELS = {
    "weapon": {"zh": "武器", "en": "Weapon"},
    "tool": {"zh": "工具", "en": "Tool"},
    "keepsake": {"zh": "纪念品", "en": "Keepsake"},
    "treasure": {"zh": "宝物", "en": "Treasure"},
    "document": {"zh": "文件", "en": "Document"},
    "other": {"zh": "其他", "en": "Other"},
}

# 重要程度映射
ITEM_IMPORTANCE_LABELS = {
    "critical": {"zh": "关键", "en": "Critical"},
    "important": {"zh": "重要", "en": "Important"},
    "normal": {"zh": "普通", "en": "Normal"},
}
