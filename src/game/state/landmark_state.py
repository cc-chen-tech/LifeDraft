"""标志物状态模型。

此模块定义了LandmarkState类，用于管理重要地点/场景的状态。
"""

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LandmarkState(BaseModel):
    """重要地点/场景状态。

    用于追踪故事中反复出现的重要地点、场景、建筑等。
    """

    # ===== 基础信息 =====
    name: str = Field(..., description="地点名称")
    description: str = Field(default="", description="地点描述")

    # ===== 分类信息 =====
    category: str = Field(
        default="other",
        description="地点类别：building(建筑)/nature(自然景观)/room(房间)/area(区域)/other(其他)",
    )
    importance: str = Field(
        default="normal",
        description="重要程度：critical(关键地点)/important(重要地点)/normal(普通地点)",
    )

    # ===== 出现信息 =====
    first_appear_week: int = Field(default=0, ge=0, description="首次出现周数")
    appear_count: int = Field(default=1, ge=1, description="出现次数")
    last_appear_week: int = Field(default=0, ge=0, description="最近出现周数")

    # ===== 场景描述 =====
    context: str = Field(default="", description="场景描述")

    # ===== 标记 =====
    is_key_location: bool = Field(default=False, description="是否关键地点")

    # ===== 元数据 =====
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="额外元数据（氛围、特色、关联人物等）"
    )

    # ===== 图片信息 =====
    image_url: Optional[str] = Field(default=None, description="地点图片URL")
    image_generated: bool = Field(default=False, description="是否已生成图片")

    def to_context_string(self) -> str:
        """
        生成用于AI上下文的地点描述。

        Returns:
            地点描述字符串
        """
        parts = [f"【{self.name}】"]

        if self.description:
            parts.append(f"描述：{self.description}")

        if self.category != "other":
            category_names = {
                "building": "建筑",
                "nature": "自然景观",
                "room": "房间",
                "area": "区域",
            }
            parts.append(f"类型：{category_names.get(self.category, self.category)}")

        if self.is_key_location:
            parts.append("★ 关键地点")

        if self.context:
            parts.append(f"场景：{self.context}")

        if self.appear_count > 1:
            parts.append(f"出现次数：{self.appear_count}")

        return "\n".join(parts)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LandmarkState":
        """
        从字典创建LandmarkState实例。

        Args:
            data: 地点数据字典

        Returns:
            LandmarkState实例
        """
        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式。

        Returns:
            地点数据字典
        """
        return self.model_dump()


# 地点类别映射
LANDMARK_CATEGORY_LABELS = {
    "building": {"zh": "建筑", "en": "Building"},
    "nature": {"zh": "自然景观", "en": "Nature"},
    "room": {"zh": "房间", "en": "Room"},
    "area": {"zh": "区域", "en": "Area"},
    "other": {"zh": "其他", "en": "Other"},
}

# 重要程度映射
LANDMARK_IMPORTANCE_LABELS = {
    "critical": {"zh": "关键", "en": "Critical"},
    "important": {"zh": "重要", "en": "Important"},
    "normal": {"zh": "普通", "en": "Normal"},
}
