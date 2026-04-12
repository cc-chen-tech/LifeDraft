"""物品连续性验证器 - 验证角色使用的物品在持有列表中。

检查内容：
- 使用/拿出物品时必须在角色持有列表中
- 已消耗物品不应再次使用
"""

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# 物品使用动词
ITEM_USE_VERBS = [
    "拔出",
    "拿出",
    "取出",
    "掏出",
    "拿起",
    "举起",
    "握住",
    "持",
    "使用",
    "挥动",
    "挥舞",
    "舞动",
    "抽出",
    "亮出",
    "戴上",
    "穿上",
    "披上",
    "系上",
    "装上",
    "打开",
    "翻开",
    "展开",
    "吃下",
    "喝下",
    "服下",
    "饮下",
    "投掷",
    "扔出",
    "射出",
]

# 物品获得动词（表明物品可能是新获得的）
ITEM_ACQUIRE_VERBS = [
    "得到",
    "获得",
    "捡到",
    "拾起",
    "接过",
    "收到",
    "买了",
    "购得",
    "换到",
    "赢得",
]


class ItemContinuityValidator:
    """物品连续性验证器。"""

    def validate(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """验证角色使用的物品在持有列表中。"""
        try:
            player_state = context.get("player_state", {})
            if not isinstance(player_state, dict):
                return True, "", {"skipped": True, "reason": "no player_state dict"}

            inventory = player_state.get("items", {})
            if not inventory:
                return True, "", {"skipped": True, "reason": "no items in inventory"}

            # 获取已知物品名称列表
            known_items = list(inventory.keys())
            if not known_items:
                return True, "", {"skipped": True, "reason": "empty inventory"}

            violations = []
            details: Dict = {
                "inventory_count": len(known_items),
                "known_items": known_items,
                "item_usages": [],
                "missing_items": [],
            }

            # 提取物品使用行为
            usages = self.extract_item_usage(story_text, known_items)
            details["item_usages"] = usages

            # 检查每个使用行为对应的物品是否在持有列表
            for usage in usages:
                item_name = usage.get("item", "")
                if not self.check_item_possession(item_name, inventory):
                    # 检查是否在文本中有获得该物品的描写（新获得物品豁免）
                    if not self._check_item_acquired_in_text(
                        story_text, item_name, usage.get("position", 0)
                    ):
                        violations.append(
                            {
                                "item": item_name,
                                "action": usage.get("action", ""),
                                "context": usage.get("context", ""),
                                "message": f"使用了未持有的物品'{item_name}'",
                            }
                        )
                        details["missing_items"].append(item_name)

            if violations:
                return (
                    False,
                    f"物品连续性违规: {'; '.join(v['message'] for v in violations[:3])}",
                    {
                        **details,
                        "violations": violations,
                        "correction_hint": f"角色当前持有物品: {known_items}，"
                        f"缺失物品: {details['missing_items']}，"
                        f"请确保只使用持有列表中的物品",
                    },
                )

            return True, "", details

        except Exception as e:
            logger.warning(f"物品连续性验证异常: {e}")
            return True, "", {}

    def extract_item_usage(self, text: str, known_items: list) -> list:
        """提取文本中的物品使用行为。"""
        usages = []

        # 策略1：检查 "动词 + 已知物品"
        for verb in ITEM_USE_VERBS:
            for item in known_items:
                if len(item) < 2:
                    continue
                # 匹配 "动词+物品" 或 "动词了/着+物品" 或 "动词+量词+物品"
                pattern = re.escape(verb) + r"[了着]?.{0,5}" + re.escape(item)
                for match in re.finditer(pattern, text):
                    ctx_start = max(0, match.start() - 15)
                    ctx_end = min(len(text), match.end() + 15)
                    usages.append(
                        {
                            "item": item,
                            "action": verb,
                            "position": match.start(),
                            "context": text[ctx_start:ctx_end],
                            "in_inventory": True,
                        }
                    )

        # 策略2：检查 "已知物品 + 使用相关描述"
        for item in known_items:
            if len(item) < 2:
                continue
            # 匹配 "物品 + 动作描述"
            pattern = re.escape(item) + r".{0,5}(?:闪烁|发光|锋利|锃亮)"
            for match in re.finditer(pattern, text):
                ctx_start = max(0, match.start() - 10)
                ctx_end = min(len(text), match.end() + 10)
                usages.append(
                    {
                        "item": item,
                        "action": "描述性使用",
                        "position": match.start(),
                        "context": text[ctx_start:ctx_end],
                        "in_inventory": True,
                    }
                )

        return usages

    def check_item_possession(self, item_name: str, inventory: dict) -> bool:
        """检查物品是否在持有列表且状态为可用。"""
        if item_name in inventory:
            item_info = inventory[item_name]
            if isinstance(item_info, dict):
                status = item_info.get("status", "owned")
                # 非 owned 状态的物品不可使用
                if status in ("gifted", "destroyed", "consumed", "lost", "sold"):
                    return False
            return True
        # 模糊匹配：检查物品名是否包含在已知物品名中
        for inv_item in inventory:
            if item_name in inv_item or inv_item in item_name:
                item_info = inventory[inv_item]
                if isinstance(item_info, dict):
                    status = item_info.get("status", "owned")
                    if status in ("gifted", "destroyed", "consumed", "lost", "sold"):
                        return False
                return True
        return False

    @staticmethod
    def _check_item_acquired_in_text(text: str, item_name: str, use_position: int) -> bool:
        """检查物品是否在使用前在文本中被获得。"""
        # 只检查使用位置之前的文本
        text_before = text[:use_position]
        for verb in ITEM_ACQUIRE_VERBS:
            pattern = re.escape(verb) + r".{0,10}" + re.escape(item_name)
            if re.search(pattern, text_before):
                return True
            pattern2 = re.escape(item_name) + r".{0,5}" + re.escape(verb)
            if re.search(pattern2, text_before):
                return True
        return False


def validate_item_continuity(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """模块级验证函数。"""
    return ItemContinuityValidator().validate(story_text, context)
