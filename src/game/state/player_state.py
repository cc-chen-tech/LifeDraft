"""玩家状态管理。

此模块定义了PlayerState类，用于管理玩家的核心状态。
PlayerState 通过 Mixin 模式组合了多个职责明确的子模块：
- PlayerDataMixin: 数据属性和序列化
- PlayerLogicMixin: 核心业务逻辑（时间推进、轮次管理）
- PlayerCharactersMixin: NPC角色管理
- PlayerInventoryMixin: 物品管理
- PlayerLandmarksMixin: 地点管理
- PlayerEventsMixin: 预定事件管理

向后兼容：所有现有的导入和 API 保持不变。
"""

from typing import Any, Dict

from pydantic import BaseModel

from src.game.state.player_characters import PlayerCharactersMixin

# 导入所有 Mixin
from src.game.state.player_data import PlayerDataMixin
from src.game.state.player_events import PlayerEventsMixin
from src.game.state.player_inventory import PlayerInventoryMixin
from src.game.state.player_landmarks import PlayerLandmarksMixin
from src.game.state.player_logic import PlayerLogicMixin


class PlayerState(
    PlayerDataMixin,
    PlayerLogicMixin,
    PlayerCharactersMixin,
    PlayerInventoryMixin,
    PlayerLandmarksMixin,
    PlayerEventsMixin,
    BaseModel,
):
    """Represents the player's current state in the game.

    此类通过多重继承组合了所有 Mixin 的功能，保持完全向后兼容。
    所有数据字段在 PlayerDataMixin 中定义。
    所有业务方法分布在各个 Mixin 中。
    """

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerState":
        """Create state from dictionary."""
        # ★ 处理可能为 None 的字符串字段，避免 Pydantic 验证错误
        # 这是为了兼容旧数据，这些字段在之前的 bug 中可能被设为 None
        cleaned_data = data.copy()
        if cleaned_data.get("last_round_full_story") is None:
            cleaned_data["last_round_full_story"] = ""
        return cls(**cleaned_data)
