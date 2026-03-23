"""自适应提示词增强器 - 根据反馈优化提示词.

学习用户的反馈历史，自动增强提示词以提高生成质量和一致性。
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptFeedback:
    """提示词反馈记录."""

    image_id: int
    feedback_text: str
    is_positive: bool  # 是否正面反馈
    timestamp: datetime
    character_name: str = ""


@dataclass
class EnhancementRule:
    """提示词增强规则."""

    trigger_keywords: List[str]  # 触发关键词
    enhancement_text: str  # 增强文本
    priority: int = 1  # 优先级
    apply_count: int = 0  # 应用次数
    success_count: int = 0  # 成功次数


class PromptEnhancer:
    """自适应提示词增强器.

    跟踪生成历史和用户反馈，自动学习并应用提示词增强策略。
    """

    # 预定义增强规则
    DEFAULT_RULES = [
        EnhancementRule(
            trigger_keywords=["不像", "不是", "变了", "换人", "认不出"],
            enhancement_text="""
严格要求：
- 人物五官比例必须与原始设定完全一致
- 不得改变发型和发色
- 保持相同的面部轮廓和特征
- 这是同一个人，在不同场景下的连续表现
""",
            priority=10,
        ),
        EnhancementRule(
            trigger_keywords=["模糊", "不清楚", "细节少", "粗糙"],
            enhancement_text="""
质量要求：
- 细节丰富，纹理清晰
- 高分辨率渲染
- 面部特征精细刻画
- 服装材质清晰可见
""",
            priority=8,
        ),
        EnhancementRule(
            trigger_keywords=["光线", "太暗", "太亮", "曝光", "阴影"],
            enhancement_text="""
光线控制：
- 光线柔和自然，避免过曝
- 阴影层次分明但不压抑
- 面部光照均匀，特征清晰可见
- 整体色调协调统一
""",
            priority=7,
        ),
        EnhancementRule(
            trigger_keywords=["表情", "神态", "不像", "气质"],
            enhancement_text="""
神态要求：
- 保持角色的常设表情特征
- 眼神要有神，符合人物性格
- 气质与角色设定一致
- 表情自然，不生硬
""",
            priority=9,
        ),
        EnhancementRule(
            trigger_keywords=["服装", "衣服", "穿着", "搭配"],
            enhancement_text="""
服装要求：
- 服装风格符合时代背景
- 服装款式、颜色、材质清晰可辨
- 褶皱自然，贴合身体
- 配饰细节完整
""",
            priority=6,
        ),
        EnhancementRule(
            trigger_keywords=["姿势", "动作", "姿态", "僵硬"],
            enhancement_text="""
姿态要求：
- 动作自然流畅，符合人体工学
- 姿态与场景情境匹配
- 避免僵硬的姿势
- 动态感与静态平衡得当
""",
            priority=5,
        ),
        EnhancementRule(
            trigger_keywords=["背景", "场景", "环境", "融合"],
            enhancement_text="""
场景融合：
- 人物与背景光影一致
- 透视关系正确
- 色调与场景协调
- 人物在场景中有合理的投影
""",
            priority=7,
        ),
    ]

    def __init__(self, storage_path: Optional[str] = None):
        """初始化增强器.

        Args:
            storage_path: 规则持久化存储路径
        """
        self.rules: List[EnhancementRule] = list(self.DEFAULT_RULES)
        self.feedback_history: List[PromptFeedback] = []
        self.character_feedback: Dict[str, List[PromptFeedback]] = {}  # 按角色分组
        self.storage_path = storage_path

        # 加载已保存的规则
        if storage_path:
            self._load_rules()

    def record_feedback(
        self,
        image_id: int,
        character_name: str,
        feedback_text: str,
        is_positive: bool = False,
    ):
        """记录用户反馈.

        Args:
            image_id: 图片ID
            character_name: 角色名称
            feedback_text: 反馈文本
            is_positive: 是否为正面反馈
        """
        feedback = PromptFeedback(
            image_id=image_id,
            character_name=character_name,
            feedback_text=feedback_text,
            is_positive=is_positive,
            timestamp=datetime.utcnow(),
        )

        self.feedback_history.append(feedback)

        # 按角色分组
        if character_name not in self.character_feedback:
            self.character_feedback[character_name] = []
        self.character_feedback[character_name].append(feedback)

        logger.info(f"Recorded feedback for {character_name}: {feedback_text[:50]}...")

        # 更新规则成功率
        self._update_rule_stats(feedback)

    def _update_rule_stats(self, feedback: PromptFeedback):
        """更新规则统计信息."""
        if feedback.is_positive:
            # 正面反馈，可能某些规则生效了
            for rule in self.rules:
                if any(kw in feedback.feedback_text for kw in rule.trigger_keywords):
                    rule.success_count += 1

    def enhance(
        self,
        base_prompt: str,
        character_name: str = "",
        image_type: str = "character",  # character 或 scene
    ) -> str:
        """增强提示词.

        Args:
            base_prompt: 基础提示词
            character_name: 角色名称（用于查询历史反馈）
            image_type: 图片类型

        Returns:
            增强后的提示词
        """
        enhancements = []

        # 1. 基于角色历史反馈应用增强
        if character_name and character_name in self.character_feedback:
            recent_feedback = self._get_recent_feedback(character_name, limit=5)
            negative_feedback = [f for f in recent_feedback if not f.is_positive]

            # 如果负面反馈较多，增加严格约束
            if len(negative_feedback) >= 2:
                enhancements.append(
                    """
【重要】该角色近期生成质量不稳定，请严格遵循以下要求：
- 仔细参照角色的外貌锚点描述
- 保持面部特征的高度一致性
- 确保与之前成功生成的形象一致
"""
                )

            # 基于反馈内容匹配规则
            for feedback in negative_feedback:
                matched_rules = self._match_rules(feedback.feedback_text)
                for rule in matched_rules:
                    if rule.enhancement_text not in enhancements:
                        enhancements.append(rule.enhancement_text)
                        rule.apply_count += 1

        # 2. 基于图片类型添加通用增强
        if image_type == "character":
            enhancements.append(self._get_character_enhancement())
        elif image_type == "scene":
            enhancements.append(self._get_scene_enhancement())

        # 3. 组合提示词
        if enhancements:
            newline = "\n"
            enhanced_prompt = f"""{base_prompt}

【增强要求】
{newline.join(enhancements)}
"""
            return enhanced_prompt

        return base_prompt

    def _get_recent_feedback(
        self,
        character_name: str,
        limit: int = 5,
    ) -> List[PromptFeedback]:
        """获取最近的反馈."""
        feedbacks = self.character_feedback.get(character_name, [])
        # 按时间倒序，取最近limit条
        sorted_feedbacks = sorted(feedbacks, key=lambda f: f.timestamp, reverse=True)
        return sorted_feedbacks[:limit]

    def _match_rules(self, feedback_text: str) -> List[EnhancementRule]:
        """根据反馈文本匹配增强规则."""
        matched = []
        for rule in self.rules:
            if any(kw in feedback_text for kw in rule.trigger_keywords):
                matched.append(rule)

        # 按优先级排序
        matched.sort(key=lambda r: r.priority, reverse=True)
        return matched[:3]  # 最多返回3条规则

    def _get_character_enhancement(self) -> str:
        """获取人物生成的通用增强."""
        return """
人物生成质量要求：
- 全身像构图完整，头部到脚部完整展示
- 面部特征清晰可辨，五官比例协调
- 服装细节丰富，符合时代背景
- 光影自然，立体感强
"""

    def _get_scene_enhancement(self) -> str:
        """获取场景生成的通用增强."""
        return """
场景生成质量要求：
- 场景构图有电影感，视觉焦点明确
- 光影氛围与故事情境匹配
- 人物与环境融合自然，投影正确
- 色彩调性统一，整体协调
"""

    def learn_from_success(self, prompt: str, character_name: str):
        """从成功案例中学习.

        分析高质量的生成结果，提取成功的提示词模式。

        Args:
            prompt: 成功的提示词
            character_name: 角色名称
        """
        # TODO: 实现提示词模式提取和学习
        # 可以分析成功提示词的共同特征，形成新的增强规则
        logger.info(f"Learning from successful prompt for {character_name}")

    def get_character_quality_score(self, character_name: str) -> float:
        """获取角色的生成质量评分.

        Args:
            character_name: 角色名称

        Returns:
            质量评分 0.0-1.0
        """
        feedbacks = self.character_feedback.get(character_name, [])
        if not feedbacks:
            return 1.0  # 没有反馈默认满分

        recent = self._get_recent_feedback(character_name, limit=10)
        positive_count = sum(1 for f in recent if f.is_positive)

        return positive_count / len(recent) if recent else 1.0

    def should_increase_constraints(self, character_name: str) -> bool:
        """判断是否需要增加约束.

        Args:
            character_name: 角色名称

        Returns:
            是否需要增加约束
        """
        score = self.get_character_quality_score(character_name)
        return score < 0.6  # 质量评分低于60%时增加约束

    def _load_rules(self):
        """从文件加载规则."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 加载自定义规则（保留默认规则）
                for rule_data in data.get("custom_rules", []):
                    self.rules.append(EnhancementRule(**rule_data))
                logger.info(f"Loaded {len(data.get('custom_rules', []))} custom rules")
        except FileNotFoundError:
            logger.info("No existing rules file found, using default rules")
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")

    def save_rules(self):
        """保存规则到文件."""
        if not self.storage_path:
            return

        try:
            # 只保存非默认的自定义规则
            custom_rules = [
                {
                    "trigger_keywords": rule.trigger_keywords,
                    "enhancement_text": rule.enhancement_text,
                    "priority": rule.priority,
                    "apply_count": rule.apply_count,
                    "success_count": rule.success_count,
                }
                for rule in self.rules
                if rule not in self.DEFAULT_RULES
            ]

            data = {
                "custom_rules": custom_rules,
                "last_updated": datetime.utcnow().isoformat(),
            }

            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved {len(custom_rules)} custom rules")
        except Exception as e:
            logger.error(f"Failed to save rules: {e}")

    def get_stats(self) -> Dict:
        """获取增强器统计信息."""
        return {
            "total_feedback": len(self.feedback_history),
            "characters_tracked": len(self.character_feedback),
            "rules_count": len(self.rules),
            "top_rules": sorted(
                [
                    (r.trigger_keywords[0], r.apply_count, r.success_count)
                    for r in self.rules
                ],
                key=lambda x: x[1],
                reverse=True,
            )[:5],
        }


# 全局增强器实例
prompt_enhancer = PromptEnhancer()
