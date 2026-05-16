"""玩家地点管理逻辑。

此模块定义了 PlayerState 的地点/场景管理部分，作为 Mixin 类供 PlayerState 继承。
包含地点的添加、获取、更新、删除和上下文生成等方法。
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from src.game.state.landmark_state import LandmarkState

logger = logging.getLogger(__name__)


class PlayerLandmarksMixin:
    """玩家地点管理 Mixin。

    包含重要地点/场景的增删改查和上下文生成方法。
    """

    # 类型声明：这些属性由 PlayerDataMixin 定义，在组合类中可用
    landmarks: Dict[str, Dict[str, Any]]

    def add_landmark(self, landmark: "LandmarkState") -> None:
        """
        添加或更新一个重要地点/场景。

        Args:
            landmark: LandmarkState实例
        """

        self.landmarks[landmark.name] = landmark.model_dump()
        logger.debug(
            f"Added landmark: {landmark.name} (importance: {landmark.importance})"
        )

    def get_landmark(self, name: str) -> Optional["LandmarkState"]:
        """
        获取指定名称的地点/场景。

        Args:
            name: 地点名称

        Returns:
            LandmarkState实例，不存在则返回None
        """
        from src.game.state.landmark_state import LandmarkState

        if name in self.landmarks:
            return LandmarkState(**self.landmarks[name])
        return None

    def get_all_landmarks(self) -> List["LandmarkState"]:
        """
        获取所有重要地点/场景。

        Returns:
            LandmarkState列表
        """
        from src.game.state.landmark_state import LandmarkState

        return [LandmarkState(**data) for data in self.landmarks.values()]

    def get_key_landmarks(self) -> List["LandmarkState"]:
        """
        获取所有关键地点。

        Returns:
            关键地点的LandmarkState列表
        """
        from src.game.state.landmark_state import LandmarkState

        return [
            LandmarkState(**data)
            for data in self.landmarks.values()
            if data.get("is_key_location", False)
        ]

    def update_landmark(self, name: str, **kwargs) -> bool:
        """
        更新指定地点/场景的属性。

        Args:
            name: 地点名称
            **kwargs: 要更新的属性

        Returns:
            是否更新成功
        """
        if name not in self.landmarks:
            logger.warning(f"Landmark not found: {name}")
            return False

        landmark_data = self.landmarks[name]
        for key, value in kwargs.items():
            if key in landmark_data or key in [
                "image_url",
                "image_generated",
                "description",
                "appear_count",
                "last_appear_week",
            ]:
                landmark_data[key] = value

        self.landmarks[name] = landmark_data
        return True

    def get_landmarks_context(self) -> str:
        """
        生成用于AI上下文的地点/场景描述。

        Returns:
            地点/场景描述字符串
        """
        from src.game.state.landmark_state import LandmarkState

        if not self.landmarks:
            return "无重要地点"

        landmark_strings = []
        for landmark_data in self.landmarks.values():
            landmark = LandmarkState(**landmark_data)
            landmark_strings.append(landmark.to_context_string())

        return "\n\n".join(landmark_strings)

    def remove_landmark(self, name: str) -> bool:
        """删除指定名称的地点/场景。

        Args:
            name: 地点名称

        Returns:
            是否删除成功
        """
        if name in self.landmarks:
            del self.landmarks[name]
            logger.info(f"Removed landmark: {name}")
            return True
        logger.warning(f"Landmark not found for removal: {name}")
        return False
