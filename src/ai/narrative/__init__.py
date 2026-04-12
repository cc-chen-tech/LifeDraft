"""叙事引擎模块。

提供风格清单、风格感知提示构建、风格验证等叙事相关功能。
"""

from .style_manifest import (
    ChapterRules,
    GlobalParameters,
    LanguageConfig,
    PhilosophyConfig,
    StructureConfig,
    StyleLoader,
    StyleManifest,
    TechniqueConfig,
    get_default_loader,
    get_style,
)
from .style_prompt_builder import StyleAwarePromptBuilder
from .style_validator import StyleAwareValidator

from .character_arc import CharacterArcEngine, CharacterArc, ArcPhase
from .world_breathing import WorldBreathingEngine
from .conflict_tower import ConflictTower
from .fate_echo import FateEchoDatabase

__all__ = [
    "StyleManifest",
    "PhilosophyConfig",
    "StructureConfig",
    "ChapterRules",
    "TechniqueConfig",
    "LanguageConfig",
    "GlobalParameters",
    "StyleLoader",
    "get_style",
    "get_default_loader",
    "StyleAwarePromptBuilder",
    "StyleAwareValidator",
    "CharacterArcEngine",
    "CharacterArc",
    "ArcPhase",
    "WorldBreathingEngine",
    "ConflictTower",
    "FateEchoDatabase",
]
