"""FateEchoDatabase 宿命回响数据库。

存储隐含因果命题，管理远期回响。
跨卷宗强制编织：严重逾期的命题强制回响。
风格感知：中国古典=因果报应/天命应验，西方=预言实现/选择后果
"""

import logging
from typing import Dict, List, Optional

from src.ai.narrative.style_manifest import StyleManifest

logger = logging.getLogger(__name__)

# ==================== Echo Hint Templates ====================

_ECHO_HINT_TEMPLATES = {
    "chinese_classic": {
        "因果报应": "因果循环，报应不爽——{cause}，如今{expected_effect}。",
        "天命应验": "天命昭昭，不可违逆——{cause}，终于应验：{expected_effect}。",
        "default": "冥冥之中自有定数——{cause}，如今{expected_effect}。",
    },
    "western": {
        "预言实现": "古老的预言终于应验——{cause}，如今{expected_effect}。",
        "选择后果": "过去的选择终于带来了后果——{cause}，如今{expected_effect}。",
        "default": "命运的齿轮转动——{cause}，而今{expected_effect}。",
    },
    "default": {
        "default": "过去的因种下了果——{cause}，如今{expected_effect}。",
    },
}


class FateEchoDatabase:
    """存储隐含因果命题，管理远期回响。"""

    def __init__(self, style: Optional[StyleManifest] = None):
        self.style = style
        self._entries: Dict[str, dict] = {}

    def register(self, proposition: Optional[dict]) -> None:
        """注册因果命题。"""
        try:
            if proposition is None or not isinstance(proposition, dict):
                logger.warning("Invalid proposition data, skipping registration.")
                return

            prop_id = proposition.get("id", "")
            if not prop_id:
                logger.warning("Proposition missing 'id', skipping.")
                return

            entry = dict(proposition)
            entry.setdefault("resolved", False)
            self._entries[prop_id] = entry
            logger.info("Registered fate proposition: %s", prop_id)
        except Exception as e:
            logger.warning("Error registering proposition: %s", e)

    def get_all(self) -> List[dict]:
        """获取所有命题。"""
        try:
            return list(self._entries.values())
        except Exception as e:
            logger.warning("Error getting all propositions: %s", e)
            return []

    def check_triggers(self, context: dict) -> List[dict]:
        """检查当前状态是否满足回响条件，返回应触发的命题列表。"""
        try:
            if not context or not isinstance(context, dict):
                return []

            current_week = context.get("current_week", 0)
            encountered = set(context.get("encountered_characters", []))
            current_volume = context.get("current_volume", 1)
            triggered = []

            for entry in self._entries.values():
                if entry.get("resolved", False):
                    continue

                conditions = entry.get("trigger_conditions", {})
                min_week = conditions.get("min_week", 0)

                if current_week < min_week:
                    continue

                # Check max_week (for expired detection, not trigger blocking)
                max_week = conditions.get("max_week")
                if max_week is not None and current_week > max_week:
                    continue

                # Check requires_encounter
                requires_encounter = conditions.get("requires_encounter")
                if requires_encounter and requires_encounter not in encountered:
                    continue

                # Check requires_item (always pass for now since we don't track items)
                # Check volume condition
                required_volume = conditions.get("volume")
                if required_volume and current_volume < required_volume:
                    continue

                triggered.append(dict(entry))

            return triggered
        except Exception as e:
            logger.warning("Error checking triggers: %s", e)
            return []

    def get_pending_echoes(self, current_week: int) -> List[dict]:
        """获取所有未解决的命题。"""
        try:
            return [dict(e) for e in self._entries.values() if not e.get("resolved", False)]
        except Exception as e:
            logger.warning("Error getting pending echoes: %s", e)
            return []

    def cleanup_expired(self, current_week: int) -> None:
        """清理过期回响。"""
        try:
            to_remove = []
            for prop_id, entry in self._entries.items():
                conditions = entry.get("trigger_conditions", {})
                max_week = conditions.get("max_week")
                if max_week is not None and current_week > max_week:
                    to_remove.append(prop_id)

            for prop_id in to_remove:
                del self._entries[prop_id]
                logger.info("Cleaned up expired proposition: %s", prop_id)
        except Exception as e:
            logger.warning("Error cleaning up expired echoes: %s", e)

    def resolve_echo(self, prop_id: str, resolved_week: int) -> None:
        """标记命题已回响。"""
        try:
            entry = self._entries.get(prop_id)
            if entry:
                entry["resolved"] = True
                entry["resolved_week"] = resolved_week
                logger.info("Resolved echo: %s at week %d", prop_id, resolved_week)
        except Exception as e:
            logger.warning("Error resolving echo: %s", e)

    def generate_echo_hint(self, proposition_id: str, style: Optional[str] = None) -> str:
        """生成回响提示注入Prompt。"""
        try:
            entry = self._entries.get(proposition_id)
            if not entry:
                logger.warning("Proposition '%s' not found for hint generation.", proposition_id)
                return ""

            cause = entry.get("cause", "")
            expected_effect = entry.get("expected_effect", "")
            prop_type = entry.get("type", "default")

            templates = _ECHO_HINT_TEMPLATES.get(
                style or "default", _ECHO_HINT_TEMPLATES["default"]
            )
            template = templates.get(
                prop_type, templates.get("default", "{cause} → {expected_effect}")
            )

            return template.format(cause=cause, expected_effect=expected_effect)
        except Exception as e:
            logger.warning("Error generating echo hint: %s", e)
            return ""

    def to_state_list(self) -> List[Dict]:
        """序列化为PlayerState.fate_entries格式。"""
        try:
            return list(self._entries.values())
        except Exception as e:
            logger.warning("Error serializing fate echo state: %s", e)
            return []

    @classmethod
    def from_state_list(
        cls, data: List[Dict], style: Optional[StyleManifest] = None
    ) -> "FateEchoDatabase":
        """从状态恢复。"""
        db = cls(style=style)
        try:
            if not data or not isinstance(data, list):
                return db
            for entry in data:
                if isinstance(entry, dict) and entry.get("id"):
                    db._entries[entry["id"]] = dict(entry)
        except Exception as e:
            logger.warning("Error restoring fate echo state: %s", e)
        return db
