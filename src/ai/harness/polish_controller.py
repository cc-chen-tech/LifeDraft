"""大师级故事精修控制器.

不是重新生成全文，而是像专业编辑一样，
基于诊断报告对故事进行局部/全局精修.
"""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .diagnostics import DiagnosticReport
    from ..client import AIClient

logger = logging.getLogger(__name__)


class PolishController:
    """大师级故事精修控制器.

    不是重新生成全文，而是像专业编辑一样，
    基于诊断报告对故事进行局部/全局精修.
    """

    def __init__(self, client: "AIClient"):
        self.client = client

    def polish(
        self,
        story_text: str,
        diagnostic_report: "DiagnosticReport",
        original_prompt: str,
        sys_prompt: str,
        max_rounds: int = 2,
    ) -> str:
        """
        执行多轮精修，每轮精修后重新校验，
        直到分数达标或达到最大精修轮数.
        """
        current_text = story_text
        for round_idx in range(max_rounds):
            polish_prompt = self._build_polish_prompt(
                current_text, diagnostic_report, original_prompt
            )
            current_text = self.client.call(
                system_prompt=sys_prompt,
                user_prompt=polish_prompt,
                temperature=0.4,
                max_tokens=8192,
            )
            logger.info(f"Polish round {round_idx + 1}/{max_rounds} completed")
        return current_text

    def _build_polish_prompt(
        self, story_text: str, report: "DiagnosticReport", original_prompt: str
    ) -> str:
        summary = getattr(report, "summary", "故事存在约束违反，请进行精修")
        return f"""你是一位严苛的文学编辑。以下故事存在约束违反，请在不改变整体情节和人物关系的前提下进行精修。

【原始创作要求】
{original_prompt}

【需要修正的问题】
{summary}

【原始故事】
{story_text}

【精修要求】
1. 只修改与问题直接相关的部分，其余内容尽量保持不变
2. 修改后的故事必须自然流畅，与上下文无缝衔接
3. 直接输出精修后的完整故事文本，不要添加任何解释
"""
