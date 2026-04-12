"""因果后果验证器 - 验证重大决策的后果在后续故事中体现。

检查内容：
- 重大决策应在后续故事中有后果体现
- 因果链不应断裂
"""

import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# 重大决策关键词（用于判断决策的重要性）
MAJOR_DECISION_INDICATORS = [
    "重要",
    "关键",
    "改变",
    "转折",
    "生死",
    "命运",
    "决裂",
    "背叛",
    "结盟",
    "放弃",
    "牺牲",
    "选择",
]

# 后果体现关键词
CONSEQUENCE_KEYWORDS = [
    "因为",
    "由于",
    "所以",
    "因此",
    "导致",
    "结果",
    "后果",
    "报应",
    "代价",
    "影响",
    "连锁",
    "波及",
    "那次",
    "上次",
    "之前的",
    "当初",
    "终于",
    "果然",
    "不出所料",
]

# 决策历史中值得追踪的最近轮数
MAX_DECISION_AGE_WEEKS = 12


class CauseEffectConsistencyValidator:
    """因果后果验证器。"""

    def validate(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """验证重大决策的后果在故事中体现。"""
        try:
            player_state = context.get("player_state", {})
            if not isinstance(player_state, dict):
                player_state = {}

            decision_history = player_state.get("decision_history", [])

            world_model = context.get("world_model")
            current_week = 0
            if world_model and hasattr(world_model, "current_week"):
                current_week = world_model.current_week
            elif isinstance(player_state, dict):
                current_week = player_state.get("week", 0)

            # 也使用 world_model 中的 causal_chains
            causal_chains: list = []
            if world_model and hasattr(world_model, "causal_chains"):
                causal_chains = world_model.causal_chains or []

            story_history = player_state.get("story_history", [])

            details: Dict = {
                "decisions_checked": 0,
                "pending_consequences": [],
                "reflected_consequences": [],
                "missing_consequences": [],
                "causal_chain_issues": [],
            }

            # 1. 检查因果链中的到期未体现后果
            chain_violations = self._check_causal_chains(causal_chains, current_week, story_text)
            details["causal_chain_issues"] = chain_violations
            if chain_violations:
                violation_msgs = [v["message"] for v in chain_violations]
                return (
                    False,
                    f"因果后果违规: {'; '.join(violation_msgs[:3])}",
                    {
                        **details,
                        "violations": violation_msgs,
                        "correction_hint": "重大事件的因果后果应在故事中体现",
                    },
                )

            # 2. 检查基于 decision_history 的后果
            if not decision_history:
                return True, "", details

            # 获取待体现后果的重大决策
            pending = self.get_pending_consequences(decision_history, story_history, current_week)
            details["pending_consequences"] = [
                {"decision": p.get("decision", "")[:50], "week": p.get("week", 0)} for p in pending
            ]
            details["decisions_checked"] = len(pending)

            # 检查每个待体现后果的决策
            for pending_item in pending:
                reflected = self.check_consequence_reflection(story_text, pending_item)
                if reflected:
                    details["reflected_consequences"].append(pending_item.get("decision", "")[:50])
                else:
                    details["missing_consequences"].append(pending_item.get("decision", "")[:50])

            # 因果验证相对宽松：只在有多个重大决策长期未体现时才警告
            long_overdue = [
                p
                for p in pending
                if current_week - p.get("week", current_week) > 6
                and p.get("decision", "")[:50] in details["missing_consequences"]
            ]

            if len(long_overdue) >= 2:
                violation_msgs = [
                    f"决策'{d.get('decision', '')[:30]}'(第{d.get('week', 0)}周)后果未体现"
                    for d in long_overdue[:3]
                ]
                return (
                    False,
                    f"因果后果违规: {'; '.join(violation_msgs)}",
                    {
                        **details,
                        "violations": violation_msgs,
                        "correction_hint": "以下重大决策的后果长期未在故事中体现: "
                        + "; ".join(f"'{d.get('decision', '')[:30]}'" for d in long_overdue[:3]),
                    },
                )

            return True, "", details

        except Exception as e:
            logger.warning(f"因果后果验证异常: {e}")
            return True, "", {}

    def get_pending_consequences(
        self, decision_history: list, story_history: list, current_week: int
    ) -> list:
        """获取尚未体现后果的重大决策。"""
        pending = []

        for decision in decision_history:
            if not isinstance(decision, dict):
                continue

            decision_text = decision.get("decision", "") or decision.get("choice", "")
            decision_week = decision.get("week", 0)

            # 只关注最近N周内的决策
            if current_week - decision_week > MAX_DECISION_AGE_WEEKS:
                continue

            # 判断是否为重大决策
            is_major = self._is_major_decision(decision_text, decision)
            if not is_major:
                continue

            # 检查决策后果是否已在之前的故事中被提及
            already_reflected = self._check_reflected_in_history(
                decision_text, story_history, decision_week
            )

            if not already_reflected:
                pending.append(
                    {
                        "decision": decision_text,
                        "week": decision_week,
                        "keywords": self._extract_decision_keywords(decision_text),
                    }
                )

        return pending

    def check_consequence_reflection(self, story_text: str, pending: dict) -> bool:
        """检查文本是否对该决策有后果体现。"""
        pending.get("decision", "")
        keywords = pending.get("keywords", [])

        if not keywords:
            return True  # 无法提取关键词，默认通过

        # 检查决策关键词是否在当前故事中出现
        keyword_found = any(kw in story_text for kw in keywords if len(kw) >= 2)

        # 检查是否有因果连接词配合出现
        has_consequence_link = any(kw in story_text for kw in CONSEQUENCE_KEYWORDS)

        # 关键词出现 + 有因果连接 → 认为后果已体现
        if keyword_found and has_consequence_link:
            return True

        # 仅关键词出现也算（可能是隐性后果）
        if keyword_found:
            return True

        return False

    def _is_major_decision(self, decision_text: str, decision: dict) -> bool:
        """判断是否为重大决策。"""
        if not decision_text:
            return False

        # 检查决策标记
        importance = decision.get("importance", "")
        if importance in ("critical", "major", "high"):
            return True

        # 检查关键词
        for indicator in MAJOR_DECISION_INDICATORS:
            if indicator in decision_text:
                return True

        # 决策文本较长（通常意味着更复杂的选择）
        if len(decision_text) > 20:
            return True

        return False

    def _check_reflected_in_history(
        self, decision_text: str, story_history: list, decision_week: int
    ) -> bool:
        """检查决策后果是否已在历史故事中体现。"""
        keywords = self._extract_decision_keywords(decision_text)
        if not keywords:
            return False

        for story in story_history:
            story_text = ""
            story_week = 0
            if isinstance(story, dict):
                story_text = story.get("text", "") or story.get("story", "")
                story_week = story.get("week", 0)
            elif isinstance(story, str):
                story_text = story

            # 只检查决策之后的故事
            if story_week <= decision_week:
                continue

            # 检查关键词出现
            if any(kw in story_text for kw in keywords if len(kw) >= 2):
                return True

        return False

    @staticmethod
    def _extract_decision_keywords(text: str) -> list:
        """从决策文本中提取关键词。"""
        stop_words = {
            "的",
            "了",
            "在",
            "是",
            "和",
            "与",
            "被",
            "将",
            "要",
            "会",
            "到",
            "从",
            "对",
            "向",
            "把",
            "让",
            "给",
            "也",
            "都",
            "又",
            "已",
            "还",
            "就",
            "而",
            "但",
            "却",
            "只",
            "很",
            "不",
            "选择",
        }
        # 先按标点分割
        segments = re.split(r"[，。！？、；：\s]+", text)
        keywords = []
        for seg in segments:
            if len(seg) >= 2 and seg not in stop_words:
                keywords.append(seg)
            # 对长段继续拆分（每2-4个字为一个关键词）
            if len(seg) > 4:
                # 尝试按常见连接词进一步拆分
                sub_segs = re.split(r"(?:在|偶遇|获得|前往|到达|进入|离开|帮助|寻找)", seg)
                for ss in sub_segs:
                    ss = ss.strip()
                    if len(ss) >= 2 and ss not in stop_words:
                        keywords.append(ss)
                # 对仍然较长的片段，尝试按2-3字滑动窗口提取
                if len(seg) > 6:
                    for i in range(0, len(seg) - 1, 2):
                        chunk = seg[i : i + 3] if i + 3 <= len(seg) else seg[i:]
                        if len(chunk) >= 2 and chunk not in stop_words:
                            keywords.append(chunk)
        return keywords

    def _check_causal_chains(self, causal_chains: list, current_week: int, story_text: str) -> list:
        """检查因果链中到期未体现的后果和矛盾。"""
        issues = []
        for chain in causal_chains:
            if not isinstance(chain, dict):
                continue

            status = chain.get("status", "")
            if status != "pending":
                continue

            trigger_week = chain.get("trigger_week", current_week)
            weeks_elapsed = current_week - trigger_week
            trigger_event = chain.get("trigger_event", "")
            expected_consequences = chain.get("expected_consequences", [])
            actual_consequences = chain.get("actual_consequences", [])

            # 超过3轮未体现后果
            if weeks_elapsed >= 3 and not actual_consequences:
                # 检查故事文本中是否有后果体现
                trigger_keywords = self._extract_decision_keywords(trigger_event)
                consequence_keywords = []
                for ec in expected_consequences:
                    consequence_keywords.extend(self._extract_decision_keywords(ec))

                # 需要触发事件和预期后果的关键词同时出现才算体现
                trigger_reflected = any(kw in story_text for kw in trigger_keywords if len(kw) >= 2)
                consequence_reflected = any(
                    kw in story_text for kw in consequence_keywords if len(kw) >= 2
                )

                if not (trigger_reflected and consequence_reflected) and not consequence_reflected:
                    issues.append(
                        {
                            "trigger_event": trigger_event,
                            "trigger_week": trigger_week,
                            "weeks_elapsed": weeks_elapsed,
                            "message": f"事件'{trigger_event[:30]}'(第{trigger_week}周)已过{weeks_elapsed}轮，"
                            f"后果未在故事中体现",
                        }
                    )

            # 检查因果矛盾：故事内容与预期后果相反
            if expected_consequences:
                for expected in expected_consequences:
                    # 检查文本中是否有与预期后果相反的描写
                    contradiction_found = self._check_consequence_contradiction(
                        story_text, trigger_event, expected
                    )
                    if contradiction_found:
                        issues.append(
                            {
                                "trigger_event": trigger_event,
                                "expected": expected,
                                "contradiction": contradiction_found,
                                "message": f"事件'{trigger_event[:30]}'的后果与预期'{expected}'矛盾: {contradiction_found}",
                            }
                        )

        return issues

    def _check_consequence_contradiction(
        self, story_text: str, trigger_event: str, expected_consequence: str
    ) -> str:
        """检查故事是否包含与预期后果矛盾的内容。"""
        # 提取触发事件和预期后果中的关键实体
        self._extract_decision_keywords(trigger_event)
        consequence_keywords = self._extract_decision_keywords(expected_consequence)

        # 查找正面预期的反面表达
        positive_negative_pairs = [
            ("感恩", "报复"),
            ("优待", "报复"),
            ("感谢", "报复"),
            ("帮助", "陷害"),
            ("恩情", "仇恨"),
            ("友好", "敌对"),
            ("保护", "攻击"),
            ("信任", "背叛"),
            ("合作", "对抗"),
        ]

        # 检查预期后果关键词和相反行为
        for pos, neg in positive_negative_pairs:
            for ckw in consequence_keywords:
                if pos in ckw or ckw in pos:
                    if neg in story_text:
                        return f"预期'{pos}'但出现'{neg}'"

        return ""


def validate_cause_effect_consistency(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """模块级验证函数。"""
    return CauseEffectConsistencyValidator().validate(story_text, context)
