"""游戏状态管理模块。

此包提供玩家和NPC角色状态管理功能。

导出的类:
- PlayerState: 玩家核心状态管理
- CharacterState: NPC角色属性系统

向后兼容:
- `from src.game.state import PlayerState, CharacterState` 仍然有效
"""

from src.game.state.character_state import CharacterState
from src.game.state.player_state import PlayerState

__all__ = ["PlayerState", "CharacterState"]
