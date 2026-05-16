"""EmotionalArcAnalyzer 情感弧线分析器。

L3 创意增强层 - 基于关键词+规则的情感弧线追踪与干预。
不依赖 LLM，使用关键词匹配分析 valence / arousal。
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.ai.narrative.style_manifest import get_style

logger = logging.getLogger(__name__)


@dataclass
class EmotionalArcResult:
    """情感分析结果。"""

    valence: float = 0.0  # 正负情感 (-1到1)
    arousal: float = 0.0  # 激活度 (0到1)
    scene_type: str = "发展"  # 铺垫/发展/转折/高潮/收尾
    pattern: str = ""  # 情感模式描述
    flatline_warning: bool = False


class EmotionalArcAnalyzer:
    """关键词+规则驱动的情感弧线分析器。"""

    POSITIVE_KEYWORDS = [
        "喜悦",
        "欢笑",
        "幸福",
        "温暖",
        "希望",
        "庆祝",
        "成功",
        "胜利",
        "拥抱",
        "微笑",
        "阳光",
        "美好",
        "轻笑",
        "笑",
        "花",
        "梦",
        "快乐",
        "庆贺",
        "凯旋",
        "欢天喜地",
        "载歌载舞",
        "哈哈大笑",
    ]
    NEGATIVE_KEYWORDS = [
        "悲伤",
        "痛苦",
        "恐惧",
        "愤怒",
        "绝望",
        "失败",
        "死亡",
        "哭泣",
        "孤独",
        "背叛",
        "泪水",
        "恩怨",
        "阴冷",
        "嘶哑",
        "冷汗",
        "黑暗",
        "墓碑",
        "乌鸦",
        "枯树",
    ]
    HIGH_AROUSAL_KEYWORDS = [
        "战斗",
        "奔跑",
        "爆炸",
        "尖叫",
        "追逐",
        "冲突",
        "决斗",
        "逃亡",
        "危险",
        "紧急",
        "屏住呼吸",
        "脚步声",
        "转动",
        "追击",
        "攀上",
        "挑战",
        "闯入",
    ]

    # 铺垫/收尾相关词
    SETUP_KEYWORDS = ["走进", "坐下", "看了看", "翻了翻", "没什么", "喝了口"]
    CLIMAX_KEYWORDS = ["终于", "再也", "紧紧", "夺眶而出", "烟消云散"]

    def analyze(self, story_text: str, history: Optional[List[Dict]] = None) -> EmotionalArcResult:
        """分析故事文本的情感状态。"""
        try:
            if not story_text or not isinstance(story_text, str):
                logger.warning("Invalid story_text input, returning default EmotionalArcResult.")
                return EmotionalArcResult()

            valence = self._compute_valence(story_text)
            arousal = self._compute_arousal(story_text)
            scene_type = self._classify_scene(valence, arousal, story_text)

            return EmotionalArcResult(
                valence=valence,
                arousal=arousal,
                scene_type=scene_type,
                pattern="",
                flatline_warning=False,
            )
        except Exception as e:
            logger.warning("Error in analyze: %s, returning default.", e)
            return EmotionalArcResult()

    def analyze_arc(self, history: List[str]) -> EmotionalArcResult:
        """分析情感弧线(多段文本的情感变化模式)。"""
        try:
            if not history:
                return EmotionalArcResult(pattern="")

            results = [self.analyze(text) for text in history]
            pattern_labels = [r.scene_type for r in results]

            # 检测转折：valence 符号变化
            transitions = []
            for i in range(1, len(results)):
                prev_v = results[i - 1].valence
                curr_v = results[i].valence
                if prev_v * curr_v < 0:
                    transitions.append("转折")
                elif curr_v > prev_v + 0.1:
                    transitions.append("上升")
                elif curr_v < prev_v - 0.1:
                    transitions.append("下降")
                else:
                    transitions.append("平稳")

            pattern_str = "→".join(pattern_labels)

            return EmotionalArcResult(
                valence=results[-1].valence,
                arousal=results[-1].arousal,
                scene_type=results[-1].scene_type,
                pattern=pattern_str,
                flatline_warning=False,
            )
        except Exception as e:
            logger.warning("Error in analyze_arc: %s", e)
            return EmotionalArcResult(pattern="")

    def detect_flatline(self, history: List[str], style: Optional[str] = None) -> bool:
        """连续3段情感平坦时返回 True。"""
        try:
            if not history or len(history) < 3:
                return False

            # 取最后3段分析
            recent = history[-3:]
            results = [self.analyze(text) for text in recent]

            # gothic 风格允许持续低沉（负面 + 低激活度属于正常）
            if style == "gothic":
                # 如果全部是负面/阴暗，gothic 风格下不算 flatline
                all_negative = all(r.valence <= 0 for r in results)
                if all_negative:
                    return False

            # 检测情感平坦：valence 和 arousal 的方差都很小
            valences = [r.valence for r in results]
            arousals = [r.arousal for r in results]

            valence_range = max(valences) - min(valences)
            arousal_range = max(arousals) - min(arousals)

            # 所有值都接近 0（低情感强度）且变化很小
            avg_abs_valence = sum(abs(v) for v in valences) / len(valences)
            avg_arousal = sum(arousals) / len(arousals)

            is_flat = (
                valence_range < 0.3
                and arousal_range < 0.3
                and avg_abs_valence < 0.3
                and avg_arousal < 0.3
            )

            # comedy 风格对平淡更敏感
            if style == "comedy":
                is_flat = (
                    valence_range < 0.4
                    and arousal_range < 0.4
                    and avg_abs_valence < 0.4
                    and avg_arousal < 0.4
                )

            return is_flat
        except Exception as e:
            logger.warning("Error in detect_flatline: %s", e)
            return False

    def suggest_intervention(
        self,
        history: Optional[List[str]] = None,
        style: Optional[str] = None,
        arc_result: Optional[EmotionalArcResult] = None,
    ) -> str:
        """基于风格配置生成节奏干预建议。"""
        try:
            if style:
                get_style(style)

            # 基于风格生成建议
            if style == "gothic":
                return "在阴暗基调中引入一丝微光或意外的温情，以打破持续低沉的节奏，同时保持哥特式的张力。"
            elif style == "comedy":
                return "加入一个出人意料的误会或巧合，通过反差制造笑点，避免节奏过于平淡。"
            elif style == "chinese_classic":
                return "以一个含蓄的伏笔或象征意象打破平铺直叙，营造'山重水复疑无路'的转折感。"
            else:
                return "建议引入意外事件或情感转折，打破当前的叙事节奏单调，提升读者参与感。"
        except Exception as e:
            logger.warning("Error in suggest_intervention: %s", e)
            return "建议引入情感转折以打破当前节奏。"

    def classify_scene(self, story_text: str) -> str:
        """场景功能分类：铺垫/发展/转折/高潮/收尾。"""
        try:
            if not story_text or not isinstance(story_text, str):
                return "发展"

            result = self.analyze(story_text)
            return result.scene_type
        except Exception as e:
            logger.warning("Error in classify_scene: %s", e)
            return "发展"

    def _compute_valence(self, text: str) -> float:
        """计算情感正负极性 (-1 到 1)。"""
        pos_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
        neg_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)

        total = pos_count + neg_count
        if total == 0:
            return 0.0

        # 归一化到 [-1, 1]
        raw = (pos_count - neg_count) / total
        return max(-1.0, min(1.0, raw))

    def _compute_arousal(self, text: str) -> float:
        """计算激活度 (0 到 1)。"""
        arousal_count = sum(1 for kw in self.HIGH_AROUSAL_KEYWORDS if kw in text)
        # 正负情感关键词也贡献一定激活度
        emotional_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text) + sum(
            1 for kw in self.NEGATIVE_KEYWORDS if kw in text
        )

        # 综合计算
        raw = (arousal_count * 2 + emotional_count) / 10.0
        return max(0.0, min(1.0, raw))

    def _classify_scene(self, valence: float, arousal: float, text: str = "") -> str:
        """场景功能分类。"""
        # 检查特定关键词
        setup_count = sum(1 for kw in self.SETUP_KEYWORDS if kw in text)
        climax_count = sum(1 for kw in self.CLIMAX_KEYWORDS if kw in text)

        if climax_count >= 2:
            return "高潮"

        if arousal > 0.5:
            if abs(valence) > 0.5:
                return "高潮"
            return "转折"

        if setup_count >= 2 and abs(valence) < 0.2:
            return "铺垫"

        if abs(valence) < 0.15 and arousal < 0.15:
            return "铺垫"

        if valence > 0.3 and arousal < 0.3:
            return "收尾"

        return "发展"
