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
        from config.feature_flags import get_feature
        from src.game.daily_timeline import migrate_legacy_state
        from src.utils.financial_narrative import (
            sanitize_authoritative_fact_records,
            sanitize_world_model_financial_authority,
        )
        from src.utils.legacy_data import strip_retired_wealth_keys

        cleaned_data = strip_retired_wealth_keys(data)
        cleaned_data["established_facts"] = sanitize_authoritative_fact_records(
            cleaned_data.get("established_facts")
        )
        wm_data = sanitize_world_model_financial_authority(
            cleaned_data.get("world_model_data")
        )
        if wm_data == {} and "world_model_data" not in cleaned_data:
            # 旧档缺少该字段：交给 pydantic 默认结构填充，
            # 不要用 sanitize 的空结果覆盖默认的 character_locations 等子字段。
            cleaned_data.pop("world_model_data", None)
        else:
            cleaned_data["world_model_data"] = wm_data

        if (
            isinstance(cleaned_data.get("timeline"), dict)
            or get_feature("daily_timeline_v2")
        ):
            cleaned_data = migrate_legacy_state(cleaned_data)
        if cleaned_data.get("last_round_full_story") is None:
            cleaned_data["last_round_full_story"] = ""
        return cls(**cleaned_data)
