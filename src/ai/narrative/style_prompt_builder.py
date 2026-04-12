"""风格感知提示构建器。

将 StyleManifest 配置转化为可注入 Prompt 的约束指令和写作建议，
供故事生成时使用。
"""

import logging
from typing import Optional

from src.ai.narrative.style_manifest import StyleManifest

logger = logging.getLogger(__name__)


class StyleAwarePromptBuilder:
    """将风格配置转化为 Prompt 约束指令。"""

    def __init__(self, style: Optional[StyleManifest] = None, max_tokens: int = 0):
        self.style = style
        self.max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> str:
        """统一入口：组合硬约束 + 软建议为完整的风格约束文本。

        无风格时返回空字符串。
        """
        if not self.style:
            return ""

        parts = []
        hard = self.build_style_hard_constraints()
        if hard:
            parts.append(hard)
        soft = self.build_style_soft_suggestions()
        if soft:
            parts.append(soft)

        # 注入 temperature 信息
        try:
            temp = self.style.global_parameters.temperature
            parts.append(f"[创作参数] temperature={temp}")
        except Exception:
            pass

        result = "\n".join(parts)
        # 如果设置了 max_tokens 预算，截断到合理长度
        if self.max_tokens > 0:
            budget_chars = self.max_tokens * 2  # 粗估 1 token ≈ 2 字符
            if len(result) > budget_chars:
                result = result[:budget_chars]
        return result

    def build_style_hard_constraints(self) -> str:
        """生成 [MUST] 级别的风格强制约束（~200 tokens）。

        基于 philosophy.narrative_voice + structure.macro + structure.arc 生成。
        无风格时返回空字符串。
        """
        if not self.style:
            return ""

        try:
            parts: list[str] = []
            phil = self.style.philosophy
            struct = self.style.structure

            if phil.narrative_voice:
                parts.append(f"[MUST] 叙事视角: 采用{phil.narrative_voice}进行叙述")

            if struct.macro:
                parts.append(f"[MUST] 宏观结构: 遵循{struct.macro}的叙事框架")

            if struct.arc:
                parts.append(f"[MUST] 故事弧线: 按照{struct.arc}的节奏推进情节")

            if phil.thematic_core:
                themes = "、".join(phil.thematic_core)
                parts.append(f"[MUST] 主题内核: 围绕「{themes}」展开叙事")

            if phil.worldview:
                parts.append(f"[MUST] 世界观基调: {phil.worldview}")

            return "\n".join(parts)
        except Exception as e:
            logger.warning("build_style_hard_constraints failed: %s", e)
            return ""

    def build_style_soft_suggestions(self) -> str:
        """生成 [SHOULD] 级别的风格写作建议（~150 tokens）。

        基于 techniques + language 生成。
        无风格时返回空字符串。
        """
        if not self.style:
            return ""

        try:
            parts: list[str] = []
            tech = self.style.techniques
            lang = self.style.language

            if tech.core_techniques:
                techniques_str = "、".join(tech.core_techniques)
                parts.append(f"[SHOULD] 核心技法: 运用{techniques_str}等叙事技法")

            if tech.stylistic_devices:
                devices_str = "、".join(tech.stylistic_devices)
                parts.append(f"[SHOULD] 修辞手法: 适当使用{devices_str}")

            if tech.narrative_patterns:
                patterns_str = "、".join(tech.narrative_patterns)
                parts.append(f"[SHOULD] 叙事模式: 参考{patterns_str}的表现方式")

            if lang.prose_style:
                parts.append(f"[SHOULD] 语言风格: {lang.prose_style}")

            if lang.dialogue:
                parts.append(f"[SHOULD] 对话风格: {lang.dialogue}")

            if lang.rhetoric:
                rhetoric_str = "、".join(lang.rhetoric)
                parts.append(f"[SHOULD] 修辞偏好: 偏好使用{rhetoric_str}")

            if lang.emotional_expression:
                parts.append(f"[SHOULD] 情感表达: {lang.emotional_expression}")

            return "\n".join(parts)
        except Exception as e:
            logger.warning("build_style_soft_suggestions failed: %s", e)
            return ""

    def build_chapter_opening(self, previous_summary: str = "") -> str:
        """基于 structure.chapter_rules.opening_style 生成章节开头模板。

        无风格或无 opening_style 时返回空字符串。
        """
        if not self.style:
            return ""

        try:
            opening_style = self.style.structure.chapter_rules.opening_style
            if not opening_style:
                return ""

            lines = [f"[章节开头指引] 本章开头应采用「{opening_style}」的方式展开。"]

            if previous_summary:
                lines.append(f"上一章概要: {previous_summary}")
                lines.append("请在承接上文的基础上，以指定的开头风格自然过渡。")

            return "\n".join(lines)
        except Exception as e:
            logger.warning("build_chapter_opening failed: %s", e)
            return ""

    def build_chapter_ending_hint(self) -> str:
        """基于 structure.chapter_rules.hook_types 生成结尾 hook 提示。

        无风格或无 hook_types 时返回空字符串。
        """
        if not self.style:
            return ""

        try:
            hook_types = self.style.structure.chapter_rules.hook_types
            if not hook_types:
                return ""

            hooks_str = "、".join(hook_types)
            closing_style = self.style.structure.chapter_rules.closing_style

            parts = [f"[章节结尾指引] 结尾应设置悬念钩子，可选类型: {hooks_str}。"]
            if closing_style:
                parts.append(f"结尾风格要求: {closing_style}")

            return "\n".join(parts)
        except Exception as e:
            logger.warning("build_chapter_ending_hint failed: %s", e)
            return ""

    def get_scene_temperature(self, scene_type: str = "") -> float:
        """基于 global_parameters.temperature_schedule 返回场景温度。

        如果 scene_type 在 temperature_schedule 中有对应值则返回该值，
        否则返回 global_parameters.temperature 基础温度。
        无风格时返回 0.85 默认值。
        """
        if not self.style:
            return 0.85

        try:
            schedule = self.style.global_parameters.temperature_schedule
            if scene_type in schedule:
                return float(schedule[scene_type])
            return self.style.global_parameters.temperature
        except Exception as e:
            logger.warning("get_scene_temperature failed: %s", e)
            return 0.85
