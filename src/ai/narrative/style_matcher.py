"""风格自动匹配引擎。

根据游戏的 character_settings 自动选择最合适的叙事风格。
采用四层级评分体系：时代(ERA)、世界观(WORLD)、人物特质(TRAITS)、文化倾向(CULTURE)，
对所有已注册风格进行加权打分，返回最佳匹配及置信度。
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 项目根目录（style_matcher.py 位于 src/ai/narrative/）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_STYLES_DIR = _PROJECT_ROOT / "config" / "styles"

# 默认回退风格
# ★ Bug #12 修复：默认风格与前端显示一致（魔幻现实主义），避免未指定风格时默认使用章回体
_DEFAULT_STYLE_ID = "magical_realism"


# ==================== 匹配结果 ====================


@dataclass
class StyleMatchResult:
    """风格匹配结果。

    Attributes:
        style_id: 最佳匹配的风格 ID。
        confidence: 置信度，范围 0.0 ~ 1.0。
        all_scores: 所有风格的评分字典 {style_id: score}。
    """

    style_id: str
    confidence: float  # 0.0 ~ 1.0
    all_scores: Dict[str, float] = field(default_factory=dict)


# ==================== 匹配引擎 ====================


class StyleMatcher:
    """四层级风格自动匹配引擎。

    通过将 character_settings 中的文本与每个风格的 matching_keywords
    进行关键词匹配，按四个维度加权计算总分，选出最佳匹配风格。

    四层级权重：
        - ERA (时代年份)   : 0.35
        - WORLD (世界观/主题): 0.30
        - TRAITS (人物特质)  : 0.20
        - CULTURE (文化倾向) : 0.15
    """

    # 权重配置
    ERA_WEIGHT = 0.35
    WORLD_WEIGHT = 0.30
    TRAITS_WEIGHT = 0.20
    CULTURE_WEIGHT = 0.15

    def __init__(self, styles_dir: Optional[Path] = None):
        self._styles_dir = styles_dir or _STYLES_DIR
        self._keywords: Dict[str, dict] = {}  # style_id -> matching_keywords
        self._load_keywords()

    # -------------------- 加载 --------------------

    def _load_keywords(self) -> None:
        """从 config/styles/*.style.json 加载所有风格的 matching_keywords。

        直接使用 json.load 读取，不依赖 StyleLoader，避免循环依赖。
        损坏或缺少 matching_keywords 的文件会被跳过并记录警告。
        """
        if not self._styles_dir.exists():
            logger.warning("Styles directory not found: %s", self._styles_dir)
            return

        count = 0
        for file_path in sorted(self._styles_dir.glob("*.style.json")):
            try:
                raw = json.loads(file_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read style file %s: %s", file_path.name, e)
                continue

            if not isinstance(raw, dict):
                logger.warning(
                    "Style file %s is not a JSON object, skipping.", file_path.name
                )
                continue

            style_id = raw.get("style_id")
            matching_keywords = raw.get("matching_keywords")

            if not style_id:
                logger.warning(
                    "Style file %s missing style_id, skipping.", file_path.name
                )
                continue

            if not isinstance(matching_keywords, dict):
                logger.debug(
                    "Style %s has no matching_keywords, skipping for matching.",
                    style_id,
                )
                continue

            self._keywords[style_id] = matching_keywords
            count += 1

        logger.info(
            "StyleMatcher loaded matching_keywords for %d style(s) from %s",
            count,
            self._styles_dir,
        )

    # -------------------- 公开接口 --------------------

    def match(self, character_settings: dict) -> StyleMatchResult:
        """返回最佳匹配风格及置信度。

        Args:
            character_settings: 游戏角色设定字典，包含 era/world/traits 等。

        Returns:
            StyleMatchResult，包含最佳风格 ID、置信度和全部评分。
            空输入或无法匹配时返回默认风格，confidence=0.0。
        """
        if not character_settings:
            return StyleMatchResult(style_id=_DEFAULT_STYLE_ID, confidence=0.0)

        scores: Dict[str, float] = {}
        for style_id, keywords in self._keywords.items():
            scores[style_id] = (
                self._score_era(character_settings, keywords) * self.ERA_WEIGHT
                + self._score_world(character_settings, keywords) * self.WORLD_WEIGHT
                + self._score_traits(character_settings, keywords) * self.TRAITS_WEIGHT
                + self._score_culture(character_settings, keywords)
                * self.CULTURE_WEIGHT
            )

        if not scores:
            return StyleMatchResult(style_id=_DEFAULT_STYLE_ID, confidence=0.0)

        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        return StyleMatchResult(
            style_id=best, confidence=scores[best], all_scores=scores
        )

    def match_top_n(
        self, character_settings: dict, n: int = 3
    ) -> List[StyleMatchResult]:
        """返回 Top N 候选风格。

        Args:
            character_settings: 游戏角色设定字典。
            n: 返回的候选数量，默认 3。

        Returns:
            按置信度降序排列的 StyleMatchResult 列表。
        """
        result = self.match(character_settings)
        sorted_styles = sorted(
            result.all_scores.items(), key=lambda x: x[1], reverse=True
        )
        return [
            StyleMatchResult(
                style_id=sid, confidence=score, all_scores=result.all_scores
            )
            for sid, score in sorted_styles[:n]
        ]

    # -------------------- L1: 时代年份匹配 --------------------

    def _score_era(self, settings: dict, keywords: dict) -> float:
        """从 settings.era 中提取时代文本，与 era_hints 关键词匹配。

        提取字段：era.year, era.era_description, era.world_context
        命中 30% 的 hints 即可得满分 1.0。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        era = settings.get("era", {})
        texts: List[str] = []
        if isinstance(era, dict):
            texts.append(str(era.get("era_description", "")))
            texts.append(str(era.get("world_context", "")))
            year = era.get("year")
            if year is not None:
                texts.append(str(year))

        combined = " ".join(texts)
        if not combined.strip():
            return 0.0

        hints = keywords.get("era_hints", [])
        if not hints:
            return 0.0

        hits = sum(1 for h in hints if h in combined)
        return min(hits / max(len(hints) * 0.3, 1), 1.0)

    # -------------------- L2: 世界观/主题匹配 --------------------

    def _score_world(self, settings: dict, keywords: dict) -> float:
        """从 settings.world 中提取世界观文本，与 theme_hints + technology_hints 匹配。

        提取字段：world.world_description, technology_level, social_system, economy
        命中 30% 的 hints 即可得满分 1.0。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        world = settings.get("world", {})
        texts: List[str] = []
        if isinstance(world, dict):
            texts.append(str(world.get("world_description", "")))
            texts.append(str(world.get("technology_level", "")))
            texts.append(str(world.get("social_system", "")))
            texts.append(str(world.get("economy", "")))

        combined = " ".join(texts)
        if not combined.strip():
            return 0.0

        theme_hints = keywords.get("theme_hints", [])
        tech_hints = keywords.get("technology_hints", [])

        theme_hits = sum(1 for h in theme_hints if h in combined)
        tech_hits = sum(1 for h in tech_hints if h in combined)

        total_hints = len(theme_hints) + len(tech_hints)
        total_hits = theme_hits + tech_hits

        if total_hints == 0:
            return 0.0
        return min(total_hits / max(total_hints * 0.3, 1), 1.0)

    # -------------------- L3: 人物特质匹配 --------------------

    def _score_traits(self, settings: dict, keywords: dict) -> float:
        """从 settings.traits 中提取人物特质文本，与 personality_hints 匹配。

        提取字段：traits.personality, traits_description, abilities, interests
        命中 30% 的 hints 即可得满分 1.0。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        traits = settings.get("traits", {})
        texts: List[str] = []
        if isinstance(traits, dict):
            # personality 是列表
            personality = traits.get("personality", [])
            if isinstance(personality, list):
                texts.extend(str(p) for p in personality)
            texts.append(str(traits.get("traits_description", "")))
            abilities = traits.get("abilities", [])
            if isinstance(abilities, list):
                texts.extend(str(a) for a in abilities)
            interests = traits.get("interests", [])
            if isinstance(interests, list):
                texts.extend(str(i) for i in interests)

        combined = " ".join(texts)
        if not combined.strip():
            return 0.0

        hints = keywords.get("personality_hints", [])
        if not hints:
            return 0.0

        hits = sum(1 for h in hints if h in combined)
        return min(hits / max(len(hints) * 0.3, 1), 1.0)

    # -------------------- L4: 文化倾向检测 --------------------

    def _score_culture(self, settings: dict, keywords: dict) -> float:
        """综合所有文本字段，检测文化倾向。

        将 settings 中所有字符串值扁平提取，与所有 hints 进行全文匹配。
        命中 20% 的 hints 即可得满分 1.0。

        Returns:
            0.0 ~ 1.0 的评分。
        """
        all_text = self._extract_all_text(settings)
        if not all_text:
            return 0.0

        # 合并所有 hints 做全文匹配
        all_hints = (
            keywords.get("era_hints", [])
            + keywords.get("theme_hints", [])
            + keywords.get("personality_hints", [])
            + keywords.get("technology_hints", [])
        )

        if not all_hints:
            return 0.0

        hits = sum(1 for h in all_hints if h in all_text)
        return min(hits / max(len(all_hints) * 0.2, 1), 1.0)

    @staticmethod
    def _extract_all_text(settings: dict) -> str:
        """递归提取 settings 中所有字符串值，拼接为单一文本。

        Args:
            settings: 任意嵌套的字典/列表结构。

        Returns:
            所有字符串值用空格连接的文本。
        """
        texts: List[str] = []

        def _extract(obj: object) -> None:
            if isinstance(obj, str):
                texts.append(obj)
            elif isinstance(obj, list):
                for item in obj:
                    _extract(item)
            elif isinstance(obj, dict):
                for v in obj.values():
                    _extract(v)

        _extract(settings)
        return " ".join(texts)


# ==================== 模块级便捷函数 ====================

_matcher_instance: Optional[StyleMatcher] = None


def auto_match_style(character_settings: dict) -> StyleMatchResult:
    """便捷函数：自动匹配风格。

    使用模块级单例 StyleMatcher，首次调用时自动初始化。

    Args:
        character_settings: 游戏角色设定字典。

    Returns:
        StyleMatchResult，包含最佳匹配风格 ID 和置信度。
    """
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = StyleMatcher()
    return _matcher_instance.match(character_settings)
