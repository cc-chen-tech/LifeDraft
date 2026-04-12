"""创意增强模块。

提供情感弧线追踪、反套路检测、伏笔管理、玩家偏好学习等创意增强功能。
"""

from src.ai.creative.emotional_arc import EmotionalArcAnalyzer, EmotionalArcResult
from src.ai.creative.novelty_scorer import NoveltyScorer, NoveltyResult
from src.ai.creative.foreshadowing_tech import (
    ForeshadowingTechniqueLibrary,
    HookInjector,
    RecoveryTechnique,
)
from src.ai.creative.preference_learner import PreferenceLearner, PlayerPreferences

__all__ = [
    "EmotionalArcAnalyzer",
    "EmotionalArcResult",
    "NoveltyScorer",
    "NoveltyResult",
    "ForeshadowingTechniqueLibrary",
    "HookInjector",
    "RecoveryTechnique",
    "PreferenceLearner",
    "PlayerPreferences",
]
