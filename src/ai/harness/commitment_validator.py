"""承诺履行验证器 - 验证到期承诺被处理、承诺不矛盾。

检查内容：
- CRITICAL承诺到期后必须在故事中被提及或处理
- 角色行为不应与活跃承诺相矛盾
"""

import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)

# 承诺处理相关关键词
FULFILLMENT_KEYWORDS = [
    "履行",
    "兑现",
    "完成",
    "做到",
    "遵守",
    "赴约",
    "如约",
    "答应过",
    "承诺",
    "约定",
    "保证",
    "守信",
    "践行",
]

# 承诺违反/打破关键词
BREACH_KEYWORDS = [
    "失约",
    "爽约",
    "食言",
    "违背",
    "毁约",
    "反悔",
    "没能",
    "未能",
    "无法",
    "忘了",
    "忘记",
    "抱歉.*没",
    "对不起.*没",
]

# 矛盾行为关键词模板 (verb patterns that indicate contradiction)
CONTRADICTION_PATTERNS = [
    r"(?:离开|远离|逃离|避开){target}",
    r"(?:拒绝|回绝|推辞|婉拒).*{target}",
    r"(?:背叛|出卖|欺骗).*{target}",
    r"(?:攻击|击打|伤害|杀|砍|刺|打).*{target}",
    r".*{target}.*(?:击倒|击杀|打倒|杀死|伤害)",
]


class CommitmentFulfillmentValidator:
    """承诺履行验证器。"""

    def validate(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """验证到期承诺被处理、承诺不矛盾。"""
        try:
            world_model = context.get("world_model")
            player_state = context.get("player_state", {})

            if not world_model or not hasattr(world_model, "active_commitments"):
                return True, "", {"skipped": True, "reason": "no world_model or commitments"}

            commitments = world_model.active_commitments
            if not commitments:
                return True, "", {"skipped": True, "reason": "no active commitments"}

            current_week = 0
            if hasattr(world_model, "current_week"):
                current_week = world_model.current_week
            elif isinstance(player_state, dict):
                current_week = player_state.get("week", 0)

            violations = []
            details = {
                "current_week": current_week,
                "total_commitments": len(commitments),
                "overdue_issues": [],
                "contradiction_issues": [],
            }

            # 1. 检查到期承诺
            overdue_issues = self.check_overdue_commitments(commitments, current_week, story_text)
            details["overdue_issues"] = overdue_issues
            for issue in overdue_issues:
                if issue.get("importance") == "critical":
                    violations.append(issue["message"])

            # 2. 检查承诺矛盾
            contradiction_issues = self.check_commitment_contradiction(story_text, commitments)
            details["contradiction_issues"] = contradiction_issues
            for issue in contradiction_issues:
                violations.append(issue["message"])

            if violations:
                return (
                    False,
                    f"承诺履行违规: {'; '.join(violations[:3])}",
                    {
                        **details,
                        "violations": violations,
                        "correction_hint": "请确保到期的CRITICAL承诺在故事中被提及或处理，"
                        "角色行为不应与已有承诺相矛盾",
                    },
                )

            return True, "", details

        except Exception as e:
            logger.warning(f"承诺履行验证异常: {e}")
            return True, "", {}

    def check_overdue_commitments(
        self, commitments: list, current_week: int, story_text: str
    ) -> list:
        """检查到期承诺是否在文本中被处理。"""
        issues = []
        for commitment in commitments:
            # 获取承诺属性（支持dataclass和dict两种格式）
            status = self._get_attr(commitment, "status", "pending")
            if status != "pending":
                continue

            deadline = self._get_attr(commitment, "deadline_week", -1)
            if deadline < 0 or deadline > current_week:
                continue  # 未到期或无截止时间

            description = self._get_attr(commitment, "description", "")
            importance = self._get_attr(commitment, "importance", "normal")
            parties = self._get_attr(commitment, "parties", [])

            # 检查承诺是否在文本中被提及
            mentioned = self._check_commitment_mentioned(description, parties, story_text)

            if not mentioned:
                issues.append(
                    {
                        "commitment": description[:50],
                        "importance": importance,
                        "deadline_week": deadline,
                        "current_week": current_week,
                        "message": (
                            f"CRITICAL承诺'{description[:30]}'已到期(第{deadline}周)但未在故事中处理"
                            if importance == "critical"
                            else f"承诺'{description[:30]}'已到期但未处理"
                        ),
                    }
                )

        return issues

    def check_commitment_contradiction(self, story_text: str, active_commitments: list) -> list:
        """检查行为是否与承诺矛盾。"""
        issues = []
        for commitment in active_commitments:
            status = self._get_attr(commitment, "status", "pending")
            if status != "pending":
                continue

            description = self._get_attr(commitment, "description", "")
            parties = self._get_attr(commitment, "parties", [])

            # 检查是否有明显违反承诺的行为
            for party in parties:
                if len(party) < 2:
                    continue
                for pattern_tmpl in CONTRADICTION_PATTERNS:
                    pattern = pattern_tmpl.replace("{target}", re.escape(party))
                    match = re.search(pattern, story_text)
                    if match:
                        context_start = max(0, match.start() - 20)
                        context_end = min(len(story_text), match.end() + 20)
                        issues.append(
                            {
                                "commitment": description[:50],
                                "contradiction": story_text[context_start:context_end],
                                "party": party,
                                "message": f"行为与承诺'{description[:30]}'矛盾: "
                                f"对{party}有违反行为",
                            }
                        )

        return issues

    def _check_commitment_mentioned(self, description: str, parties: list, story_text: str) -> bool:
        """检查承诺是否在故事文本中被提及。"""
        # 检查承诺描述中的关键词
        keywords = re.split(r"[，。、；\s]+", description)
        keywords = [kw for kw in keywords if len(kw) >= 2]
        if any(kw in story_text for kw in keywords):
            return True

        # 检查相关方名字
        if any(party in story_text for party in parties if len(party) >= 2):
            # 同时检查是否有履行/处理相关词汇
            has_action = any(kw in story_text for kw in FULFILLMENT_KEYWORDS + BREACH_KEYWORDS)
            if has_action:
                return True

        return False

    @staticmethod
    def _get_attr(obj, attr: str, default=None):
        """安全获取属性，支持dataclass和dict。"""
        if isinstance(obj, dict):
            return obj.get(attr, default)
        return getattr(obj, attr, default)


def validate_commitment_fulfillment(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """模块级验证函数。"""
    return CommitmentFulfillmentValidator().validate(story_text, context)
