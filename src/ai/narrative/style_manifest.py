"""叙事风格清单数据模型与加载器。

定义 StyleManifest 数据结构和 StyleLoader 加载器，
支持从 config/styles/ 目录扫描并解析 .style.json 文件。
提供缓存、热插拔、损坏文件跳过等能力。
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Compute the project root based on this file's location
# style_manifest.py is at src/ai/narrative/style_manifest.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_STYLES_DIR = str(_PROJECT_ROOT / "config" / "styles")

# ==================== Style Manifest Data Models ====================


@dataclass
class PhilosophyConfig:
    """叙事哲学配置。"""

    narrative_voice: str = ""
    thematic_core: List[str] = field(default_factory=list)
    worldview: str = ""


@dataclass
class ChapterRules:
    """章节规则配置。"""

    opening_style: str = ""
    closing_style: str = ""
    hook_types: List[str] = field(default_factory=list)
    avg_length: str = ""


@dataclass
class StructureConfig:
    """叙事结构配置。"""

    macro: str = ""
    chapter_rules: ChapterRules = field(default_factory=ChapterRules)
    arc: str = ""


@dataclass
class TechniqueConfig:
    """叙事技法配置。"""

    core_techniques: List[str] = field(default_factory=list)
    stylistic_devices: List[str] = field(default_factory=list)
    narrative_patterns: List[str] = field(default_factory=list)


@dataclass
class LanguageConfig:
    """语言风格配置。"""

    prose_style: str = ""
    dialogue: str = ""
    rhetoric: List[str] = field(default_factory=list)
    emotional_expression: str = ""


@dataclass
class GlobalParameters:
    """全局生成参数。"""

    temperature: float = 0.85
    top_p: float = 1.0
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    temperature_schedule: Dict[str, float] = field(default_factory=dict)


@dataclass
class StyleManifest:
    """叙事风格清单，定义一种完整的叙事风格。"""

    style_id: str = ""
    style_name: str = ""
    version: str = "1.0"
    description: str = ""
    philosophy: PhilosophyConfig = field(default_factory=PhilosophyConfig)
    structure: StructureConfig = field(default_factory=StructureConfig)
    techniques: TechniqueConfig = field(default_factory=TechniqueConfig)
    language: LanguageConfig = field(default_factory=LanguageConfig)
    global_parameters: GlobalParameters = field(default_factory=GlobalParameters)


# ==================== Required fields for validation ====================

_REQUIRED_FIELDS = {"style_id", "style_name"}


# ==================== StyleLoader ====================


class StyleLoader:
    """扫描 styles 目录，加载并缓存 .style.json 文件。"""

    def __init__(self, styles_dir: str = _DEFAULT_STYLES_DIR):
        self._styles_dir = Path(styles_dir)
        self._cache: Dict[str, StyleManifest] = {}
        self._loaded = False

    def load_all(self) -> None:
        """扫描 styles 目录，加载所有 .style.json 文件。"""
        self._cache.clear()

        if not self._styles_dir.exists():
            logger.warning("Styles directory not found: %s, creating it.", self._styles_dir)
            try:
                self._styles_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning("Failed to create styles directory: %s", e)
            self._loaded = True
            return

        for file_path in sorted(self._styles_dir.glob("*.style.json")):
            manifest = self._parse_style_file(file_path)
            if manifest and manifest.style_id:
                self._cache[manifest.style_id] = manifest

        self._loaded = True
        logger.info("Loaded %d style(s) from %s", len(self._cache), self._styles_dir)

    def get_style(self, style_id: str) -> Optional[StyleManifest]:
        """获取指定风格（自动触发首次加载）。"""
        if not self._loaded:
            self.load_all()
        return self._cache.get(style_id)

    def get_all_style_ids(self) -> List[str]:
        """返回所有可用风格ID。"""
        if not self._loaded:
            self.load_all()
        return list(self._cache.keys())

    def reload(self) -> None:
        """强制重新加载（热插拔支持）。"""
        self._loaded = False
        self.load_all()

    def _parse_style_file(self, file_path: Path) -> Optional[StyleManifest]:
        """解析单个 .style.json 文件。出错则 logger.warning 并跳过。"""
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read/parse style file %s: %s", file_path, e)
            return None

        if not isinstance(raw, dict):
            logger.warning("Style file %s does not contain a JSON object, skipping.", file_path)
            return None

        # 验证必填字段
        missing = _REQUIRED_FIELDS - set(raw.keys())
        if missing:
            logger.warning(
                "Style file %s missing required fields %s, skipping.",
                file_path,
                missing,
            )
            return None

        try:
            # 解析嵌套配置
            philosophy = _parse_philosophy(raw.get("philosophy", {}))
            structure = _parse_structure(raw.get("structure", {}))
            techniques = _parse_technique(raw.get("techniques", {}))
            language = _parse_language(raw.get("language", {}))
            global_params = _parse_global_parameters(raw.get("global_parameters", {}))

            return StyleManifest(
                style_id=raw.get("style_id", ""),
                style_name=raw.get("style_name", ""),
                version=str(raw.get("version", "1.0")),
                description=raw.get("description", ""),
                philosophy=philosophy,
                structure=structure,
                techniques=techniques,
                language=language,
                global_parameters=global_params,
            )
        except Exception as e:
            logger.warning("Error constructing StyleManifest from %s: %s", file_path, e)
            return None


# ==================== Parse helpers ====================


def _parse_philosophy(d: dict) -> PhilosophyConfig:
    if not isinstance(d, dict):
        return PhilosophyConfig()
    return PhilosophyConfig(
        narrative_voice=d.get("narrative_voice", ""),
        thematic_core=d.get("thematic_core", []),
        worldview=d.get("worldview", ""),
    )


def _parse_chapter_rules(d: dict) -> ChapterRules:
    if not isinstance(d, dict):
        return ChapterRules()
    return ChapterRules(
        opening_style=d.get("opening_style", ""),
        closing_style=d.get("closing_style", ""),
        hook_types=d.get("hook_types", []),
        avg_length=d.get("avg_length", ""),
    )


def _parse_structure(d: dict) -> StructureConfig:
    if not isinstance(d, dict):
        return StructureConfig()
    return StructureConfig(
        macro=d.get("macro", ""),
        chapter_rules=_parse_chapter_rules(d.get("chapter_rules", {})),
        arc=d.get("arc", ""),
    )


def _parse_technique(d: dict) -> TechniqueConfig:
    if not isinstance(d, dict):
        return TechniqueConfig()
    return TechniqueConfig(
        core_techniques=d.get("core_techniques", []),
        stylistic_devices=d.get("stylistic_devices", []),
        narrative_patterns=d.get("narrative_patterns", []),
    )


def _parse_language(d: dict) -> LanguageConfig:
    if not isinstance(d, dict):
        return LanguageConfig()
    return LanguageConfig(
        prose_style=d.get("prose_style", ""),
        dialogue=d.get("dialogue", ""),
        rhetoric=d.get("rhetoric", []),
        emotional_expression=d.get("emotional_expression", ""),
    )


def _parse_global_parameters(d: dict) -> GlobalParameters:
    if not isinstance(d, dict):
        return GlobalParameters()
    return GlobalParameters(
        temperature=float(d.get("temperature", 0.85)),
        top_p=float(d.get("top_p", 1.0)),
        presence_penalty=float(d.get("presence_penalty", 0.0)),
        frequency_penalty=float(d.get("frequency_penalty", 0.0)),
        temperature_schedule=d.get("temperature_schedule", {}),
    )


# ==================== Global singleton ====================

_default_loader: Optional[StyleLoader] = None


def get_default_loader() -> StyleLoader:
    """获取全局默认 StyleLoader 单例。"""
    global _default_loader
    if _default_loader is None:
        _default_loader = StyleLoader()
    return _default_loader


def get_style(style_id: str) -> Optional[StyleManifest]:
    """全局访问接口：根据 style_id 获取 StyleManifest。"""
    return get_default_loader().get_style(style_id)
