"""角色状态连续性验证器 - 验证角色行为与状态一致。

检查内容：
- 已死亡角色不应有主动行为（回忆/梦境豁免）
- 重伤角色不应有剧烈行动
- 被囚禁角色不应自由行动
"""

import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# 豁免关键词：在这些语境中，死亡/受伤角色的出现是合理的
EXEMPTION_KEYWORDS = [
    "回忆",
    "梦境",
    "幻觉",
    "梦中",
    "记忆中",
    "往事",
    "曾经",
    "想起",
    "梦里",
    "幻影",
]

# 主动行为动词（用于检测死亡角色不应有的行为）
ACTIVE_ACTION_VERBS = [
    "说道",
    "说",
    "笑道",
    "叹道",
    "喊道",
    "问道",
    "答道",
    "道",
    "走",
    "跑",
    "骑",
    "飞",
    "来到",
    "赶到",
    "出现在",
    "踏入",
    "拿起",
    "拔出",
    "挥动",
    "举起",
    "扔",
    "推",
    "拉",
    "打",
    "砍",
    "刺",
    "击",
    "攻",
    "挡",
    "闪",
    "吃",
    "喝",
    "坐",
    "站",
    "躺",
    "决定",
    "选择",
    "同意",
    "拒绝",
    "答应",
]

# 剧烈行动词（重伤角色不应有的行为）
VIGOROUS_ACTION_VERBS = [
    "奔跑",
    "飞奔",
    "疾驰",
    "冲锋",
    "跳跃",
    "翻滚",
    "搏斗",
    "激战",
    "厮杀",
    "格斗",
    "挥刀",
    "舞剑",
    "攀爬",
    "翻墙",
    "跳下",
    "飞身",
    "举起重物",
    "搬运",
    "扛",
    "抱起",
    "举过",
    "全力",
    "拼命",
    "猛",
    "双手",
    "双臂",
]

# 自由行动词（被囚禁角色不应有的行为）
FREE_MOVEMENT_VERBS = [
    "自由地",
    "随意地",
    "悠闲地",
    "逛街",
    "散步",
    "游玩",
    "旅行",
    "前往",
    "赶往",
    "出城",
    "离开",
    "在街上",
    "在市场",
    "在酒楼",
    "在广场",
]

# 死亡状态关键词
DEAD_CONDITIONS = ["死亡", "已死", "身亡", "过世", "去世", "亡故", "殉", "战死", "病逝"]

# 重伤状态关键词
SEVERE_CONDITIONS = ["重伤", "昏迷", "瘫痪", "残疾", "断腿", "断臂", "骨折"]

# 囚禁状态关键词
IMPRISONED_CONDITIONS = ["囚禁", "关押", "入狱", "被捕", "软禁", "被困", "监禁", "牢狱"]


class CharacterStateContinuityValidator:
    """角色状态连续性验证器。"""

    def validate(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """验证角色行为与状态(alive/dead/injured/imprisoned)一致。"""
        try:
            world_model = context.get("world_model")
            if not world_model or not hasattr(world_model, "physical_states"):
                return True, "", {"skipped": True, "reason": "no world_model or physical_states"}

            physical_states = world_model.physical_states
            if not physical_states:
                return True, "", {"skipped": True, "reason": "no physical_states data"}

            violations = []
            details: Dict = {
                "characters_checked": len(physical_states),
                "dead_violations": [],
                "injury_violations": [],
                "imprisoned_violations": [],
            }

            # 构建角色状态映射
            character_states = self._categorize_states(physical_states)

            # 1. 死亡角色检查
            dead_issues = self.check_dead_character_action(story_text, character_states)
            details["dead_violations"] = dead_issues
            violations.extend(dead_issues)

            # 2. 重伤角色检查
            injury_issues = self.check_injured_ability(story_text, character_states)
            details["injury_violations"] = injury_issues
            violations.extend(injury_issues)

            # 3. 囚禁角色检查
            prison_issues = self.check_imprisoned_freedom(story_text, character_states)
            details["imprisoned_violations"] = prison_issues
            violations.extend(prison_issues)

            if violations:
                hint_parts = []
                for v in violations[:3]:
                    hint_parts.append(v.get("hint", ""))
                return (
                    False,
                    f"角色状态连续性违规: {'; '.join(v.get('message', '') for v in violations[:3])}",
                    {
                        **details,
                        "violations": violations,
                        "correction_hint": "; ".join(hint_parts),
                    },
                )

            return True, "", details

        except Exception as e:
            logger.warning(f"角色状态连续性验证异常: {e}")
            return True, "", {}

    def check_dead_character_action(self, text: str, character_states: dict) -> list:
        """已死亡角色不应有主动行为（回忆/梦境豁免）。"""
        issues = []
        dead_chars = character_states.get("dead", {})

        for name, state_info in dead_chars.items():
            if len(name) < 2 or name not in text:
                continue

            # 检查是否在豁免语境中
            if self._is_in_exemption_context(text, name):
                continue

            # 检查是否有主动行为
            for verb in ACTIVE_ACTION_VERBS:
                # 匹配 "角色名 + ...（0-10字）+ 动词"
                pattern = re.escape(name) + r".{0,10}" + re.escape(verb)
                match = re.search(pattern, text)
                if match:
                    ctx_start = max(0, match.start() - 10)
                    ctx_end = min(len(text), match.end() + 10)
                    issues.append(
                        {
                            "character": name,
                            "status": "dead",
                            "action": verb,
                            "context": text[ctx_start:ctx_end],
                            "message": f"已死亡角色'{name}'出现主动行为'{verb}'",
                            "hint": f"角色{name}当前状态为死亡({state_info})，不应有主动行为'{verb}'",
                        }
                    )
                    break  # 每个角色只报告第一个违规

        return issues

    def check_injured_ability(self, text: str, character_states: dict) -> list:
        """重伤角色不应有剧烈行动。"""
        issues = []
        injured_chars = character_states.get("severe_injury", {})

        for name, state_info in injured_chars.items():
            if len(name) < 2 or name not in text:
                continue

            if self._is_in_exemption_context(text, name):
                continue

            for verb in VIGOROUS_ACTION_VERBS:
                pattern = re.escape(name) + r".{0,15}" + re.escape(verb)
                match = re.search(pattern, text)
                if match:
                    ctx_start = max(0, match.start() - 10)
                    ctx_end = min(len(text), match.end() + 10)
                    issues.append(
                        {
                            "character": name,
                            "status": "severe_injury",
                            "condition": state_info,
                            "action": verb,
                            "context": text[ctx_start:ctx_end],
                            "message": f"重伤角色'{name}'({state_info})出现剧烈行动'{verb}'",
                            "hint": f"角色{name}当前为重伤状态({state_info})，不应有剧烈行动'{verb}'",
                        }
                    )
                    break

        return issues

    def check_imprisoned_freedom(self, text: str, character_states: dict) -> list:
        """被囚禁角色不应自由行动。"""
        issues = []
        imprisoned_chars = character_states.get("imprisoned", {})

        for name, state_info in imprisoned_chars.items():
            if len(name) < 2 or name not in text:
                continue

            if self._is_in_exemption_context(text, name):
                continue

            for verb in FREE_MOVEMENT_VERBS:
                pattern = re.escape(name) + r".{0,15}" + re.escape(verb)
                match = re.search(pattern, text)
                if match:
                    ctx_start = max(0, match.start() - 10)
                    ctx_end = min(len(text), match.end() + 10)
                    issues.append(
                        {
                            "character": name,
                            "status": "imprisoned",
                            "condition": state_info,
                            "action": verb,
                            "context": text[ctx_start:ctx_end],
                            "message": f"被囚禁角色'{name}'出现自由行动'{verb}'",
                            "hint": f"角色{name}当前为囚禁状态({state_info})，不应自由行动'{verb}'",
                        }
                    )
                    break

        return issues

    def _categorize_states(self, physical_states: dict) -> dict:
        """将物理状态分类为 dead/severe_injury/imprisoned。"""
        categories: Dict[str, Dict[str, str]] = {
            "dead": {},
            "severe_injury": {},
            "imprisoned": {},
        }

        for name, state in physical_states.items():
            condition = ""
            severity = "moderate"
            if hasattr(state, "condition"):
                condition = state.condition
                severity = getattr(state, "severity", "moderate")
            elif isinstance(state, dict):
                condition = state.get("condition", "")
                # 也支持 conditions 列表格式
                conditions_list = state.get("conditions", [])
                if not condition and conditions_list:
                    condition = (
                        " ".join(conditions_list)
                        if isinstance(conditions_list, list)
                        else str(conditions_list)
                    )
                severity = state.get("severity", "moderate")
                # 从 status 字段推断分类
                status = state.get("status", "")
                if status == "dead":
                    categories["dead"][name] = condition or status
                    continue
                elif status == "imprisoned":
                    categories["imprisoned"][name] = condition or status
                    continue
                elif status in ("severe_injury", "injured"):
                    categories["severe_injury"][name] = condition or status
                    continue

            condition_lower = condition.lower() if condition else ""

            # 判断死亡
            if any(kw in condition_lower for kw in DEAD_CONDITIONS):
                categories["dead"][name] = condition
            # 判断囚禁
            elif any(kw in condition_lower for kw in IMPRISONED_CONDITIONS):
                categories["imprisoned"][name] = condition
            # 判断重伤
            elif severity == "severe" or any(kw in condition_lower for kw in SEVERE_CONDITIONS):
                categories["severe_injury"][name] = condition

        return categories

    @staticmethod
    def _is_in_exemption_context(text: str, character_name: str) -> bool:
        """检查角色名出现是否在豁免语境中（回忆/梦境等）。"""
        # 查找角色名在文本中的所有位置
        for match in re.finditer(re.escape(character_name), text):
            pos = match.start()
            # 取角色名前后50字作为上下文
            context_start = max(0, pos - 50)
            context_end = min(len(text), pos + len(character_name) + 50)
            local_context = text[context_start:context_end]

            # 如果有任何非豁免出现，则不豁免
            has_exemption = any(kw in local_context for kw in EXEMPTION_KEYWORDS)
            if not has_exemption:
                return False

        # 所有出现都在豁免语境中
        return True


def validate_character_state_continuity(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """模块级验证函数。"""
    return CharacterStateContinuityValidator().validate(story_text, context)
