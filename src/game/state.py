"""玩家状态管理 - 向后兼容模块。

此文件保留用于向后兼容。所有类已迁移到 src/game/state/ 包。

导入方式保持不变:
- from src.game.state import PlayerState, CharacterState

新的模块结构:
- src.game.state.character_state: CharacterState类
- src.game.state.player_state: PlayerState类
"""

# 从新位置导入，保持向后兼容
from src.game.state.character_state import CharacterState
from src.game.state.player_state import PlayerState

__all__ = ["PlayerState", "CharacterState"]
