"""PreferenceLearner 偏好适配层。

L3 创意增强层 - 从玩家决策历史中学习隐性偏好，
生成偏好引导 Prompt 片段，动态调节温度参数。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlayerPreferences:
    """玩家偏好模型。"""

    preference_vector: Dict[str, float] = field(default_factory=dict)
    primary_type: str = "balanced"  # adventure / social / investigation / balanced
    adventure_tendency: float = 0.5
    social_tendency: float = 0.5
    investigation_tendency: float = 0.5


class PreferenceLearner:
    """从决策历史中提取玩家隐性偏好。"""

    PREFERENCE_CATEGORIES = [
        "suspense",
        "romance",
        "adventure",
        "investigation",
        "social",
        "introspection",
    ]

    # 类型关键词映射(用于从 choice 文本推断类型)
    TYPE_KEYWORDS: Dict[str, List[str]] = {
        "adventure": [
            "冒险",
            "进入",
            "闯入",
            "跳下",
            "攀上",
            "挑战",
            "追击",
            "战斗",
            "探索",
            "寻宝",
        ],
        "social": [
            "邀请",
            "调解",
            "拜访",
            "组织",
            "交谈",
            "合作",
            "帮助",
            "村民",
            "朋友",
            "共进",
        ],
        "investigation": [
            "检查",
            "翻阅",
            "查找",
            "线索",
            "询问",
            "调查",
            "观察",
            "分析",
            "推理",
            "证据",
        ],
    }

    def learn(self, decision_history: Optional[List[Dict]]) -> PlayerPreferences:
        """从决策历史提取隐性偏好信号。"""
        try:
            if not decision_history:
                return PlayerPreferences()

            # 统计各类型权重（带时间衰减）
            type_weights: Dict[str, float] = {
                "adventure": 0.0,
                "social": 0.0,
                "investigation": 0.0,
            }
            max_week: float = 1

            # 找到最大 week 用于衰减计算
            for entry in decision_history:
                if not isinstance(entry, dict):
                    continue
                week = entry.get("week", 1)
                if isinstance(week, (int, float)) and week > max_week:
                    max_week = week

            total_weight = 0.0
            for entry in decision_history:
                if not isinstance(entry, dict):
                    continue

                # 确定类型
                entry_type = entry.get("type", "")
                choice_text = entry.get("choice", "")

                # 如果没有 type 字段，从文本推断
                if not entry_type:
                    entry_type = self._infer_type(choice_text)

                if entry_type not in type_weights:
                    continue

                # 时间衰减：越近的选择权重越高
                week = entry.get("week", 1)
                if not isinstance(week, (int, float)):
                    week = 1
                # 衰减因子：recency = 0.5 + 0.5 * (week / max_week)
                recency = 0.5 + 0.5 * (week / max_week) if max_week > 0 else 1.0

                type_weights[entry_type] += recency
                total_weight += recency

            if total_weight == 0:
                return PlayerPreferences()

            # 归一化
            for k in type_weights:
                type_weights[k] /= total_weight

            # 确定主要类型
            primary = max(type_weights, key=lambda k: type_weights[k])
            if type_weights[primary] < 0.35:
                primary = "balanced"

            return PlayerPreferences(
                preference_vector={
                    "adventure": type_weights.get("adventure", 0.0),
                    "social": type_weights.get("social", 0.0),
                    "investigation": type_weights.get("investigation", 0.0),
                },
                primary_type=primary,
                adventure_tendency=type_weights.get("adventure", 0.5),
                social_tendency=type_weights.get("social", 0.5),
                investigation_tendency=type_weights.get("investigation", 0.5),
            )

        except Exception as e:
            logger.warning("Error in learn: %s, returning default.", e)
            return PlayerPreferences()

    def build_preference_hint(
        self,
        prefs: PlayerPreferences,
        max_tokens: int = 50,
        style: Optional[str] = None,
    ) -> str:
        """生成偏好引导的 Prompt 片段 (~50 tokens)。"""
        try:
            parts = []

            if prefs.primary_type == "adventure":
                parts.append("玩家偏好冒险与行动，适当增加紧张刺激的情节元素")
            elif prefs.primary_type == "social":
                parts.append("玩家偏好社交互动，适当增加人物对话和关系发展")
            elif prefs.primary_type == "investigation":
                parts.append("玩家偏好探索调查，适当增加谜题线索和推理元素")
            else:
                parts.append("玩家偏好均衡，保持多元化的叙事元素")

            # 风格适配
            if style == "gothic":
                parts.append("在哥特式阴暗基调下融入上述偏好")
            elif style == "chinese_classic":
                parts.append("以古典叙事风格融入上述偏好")
            elif style == "comedy":
                parts.append("在轻松幽默的基调下融入上述偏好")

            hint = "，".join(parts) + "。"

            # 控制长度
            max_chars = min(max_tokens * 4, 300)
            if len(hint) > max_chars:
                hint = hint[: max_chars - 1] + "。"

            return hint

        except Exception as e:
            logger.warning("Error in build_preference_hint: %s", e)
            return "保持叙事多元化。"

    def adjust_temperature(
        self,
        base_temperature: float,
        recent_scores: Optional[List[float]] = None,
    ) -> float:
        """
        基于近期质量评分动态调节温度。
        评分下降→临时 +0.1~0.2 打破模式僵化。
        """
        try:
            if not recent_scores or len(recent_scores) < 2:
                return base_temperature

            # 计算趋势：线性回归斜率近似
            n = len(recent_scores)
            # 简单方法：比较前半段和后半段均值
            mid = n // 2
            first_half_avg = sum(recent_scores[:mid]) / mid if mid > 0 else 0
            second_half_avg = sum(recent_scores[mid:]) / (n - mid) if (n - mid) > 0 else 0

            decline = first_half_avg - second_half_avg

            if decline > 1.5:
                # 明显下降 → +0.2
                adjustment = 0.2
            elif decline > 0.5:
                # 轻微下降 → +0.1
                adjustment = 0.1
            elif decline > 0.2:
                # 微弱下降 → +0.05
                adjustment = 0.05
            else:
                # 稳定或上升 → 不调整
                adjustment = 0.0

            adjusted = base_temperature + adjustment
            # 限制在合理范围
            return min(1.5, max(0.1, adjusted))

        except Exception as e:
            logger.warning("Error in adjust_temperature: %s, returning base.", e)
            return base_temperature

    def _infer_type(self, text: str) -> str:
        """从选择文本推断类型。"""
        if not text:
            return ""

        scores = {}
        for type_name, keywords in self.TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[type_name] = score

        best = max(scores, key=lambda k: scores[k])
        if scores[best] > 0:
            return best
        return ""
