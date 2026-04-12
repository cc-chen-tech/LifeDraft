"""WorldBreathingEngine 世界呼吸引擎。

独立世界事件日历，背景事件自动推进。
信息渗透机制：将世界事件转化为场景描写片段。
风格感知：中国古典=江湖传闻/官府告示，西方=预言/旅人传说
"""

import logging
import random
from typing import Dict, List, Optional

from src.ai.narrative.style_manifest import StyleManifest

logger = logging.getLogger(__name__)

# ==================== Permeation Templates ====================

_PERMEATION_TEMPLATES = {
    "chinese_classic": {
        "季节变化": "路旁茶摊的老者摇头叹道：「{description}」旅人纷纷裹紧了衣裳。",
        "市场波动": "街头巷尾议论纷纷：「{description}」商贾们愁眉不展。",
        "政治动荡": "官府告示贴满了城墙——{description}",
        "自然灾害": "逃难的灾民涌入城中，带来了骇人的消息：「{description}」",
        "流言传播": "江湖中人传言——{description}",
        "default": "风声传来消息：{description}",
    },
    "western_fantasy": {
        "预言": "酒馆角落的吟游诗人低声唱道：「{description}」",
        "旅人传说": "一位风尘仆仆的旅人讲述了见闻：「{description}」",
        "default": "远方传来消息：{description}",
    },
    "default": {
        "default": "{description}",
    },
}


class WorldBreathingEngine:
    """独立的世界事件日历，背景事件自动发生。"""

    VALID_TYPES = {"季节变化", "市场波动", "政治动荡", "自然灾害", "流言传播", "预言", "旅人传说"}

    def __init__(self, style: Optional[StyleManifest] = None, era: str = "modern"):
        self.style = style
        self.era = era
        self._events: Dict[str, dict] = {}
        self._activated: Dict[str, bool] = {}

    def register_event(self, event: Optional[dict]) -> None:
        """注册世界事件到日历。"""
        try:
            if event is None or not isinstance(event, dict):
                logger.warning("Invalid event data, skipping registration.")
                return

            event_id = event.get("id", "")
            if not event_id:
                logger.warning("Event missing 'id', skipping.")
                return

            self._events[event_id] = dict(event)
            self._activated[event_id] = False
            logger.info("Registered world event: %s", event_id)
        except Exception as e:
            logger.warning("Error registering event: %s", e)

    def get_calendar(self) -> List[dict]:
        """获取事件日历，按触发周排序。"""
        try:
            events = list(self._events.values())
            events.sort(key=lambda e: e.get("trigger_week", 0))
            return events
        except Exception as e:
            logger.warning("Error getting calendar: %s", e)
            return []

    def advance_to_week(self, week: int) -> List[dict]:
        """推进到指定周，返回已触发的活跃事件。"""
        try:
            active = []
            for event_id, event in self._events.items():
                trigger_week = event.get("trigger_week", 0)
                if trigger_week <= week:
                    self._activated[event_id] = True
                    active.append(dict(event))
            return active
        except Exception as e:
            logger.warning("Error advancing to week %d: %s", week, e)
            return []

    def generate_permeation_snippet(
        self,
        event_id: str,
        scene_context: str = "",
        style: Optional[str] = None,
    ) -> str:
        """信息渗透机制：世界事件转化为描写片段。"""
        try:
            event = self._events.get(event_id)
            if not event:
                logger.warning("Event '%s' not found for permeation.", event_id)
                return ""

            description = event.get("description", "")
            event_type = event.get("type", "default")

            templates = _PERMEATION_TEMPLATES.get(style or "default", _PERMEATION_TEMPLATES["default"])
            template = templates.get(event_type, templates.get("default", "{description}"))

            snippet = template.format(description=description)
            return snippet
        except Exception as e:
            logger.warning("Error generating permeation snippet: %s", e)
            return ""

    def get_events_by_type(self, event_type: str) -> List[dict]:
        """按类型筛选事件。"""
        try:
            return [e for e in self._events.values() if e.get("type") == event_type]
        except Exception as e:
            logger.warning("Error filtering events by type: %s", e)
            return []

    def get_active_events(self, current_week: int, recent_n: int = 5) -> List[dict]:
        """获取最近的活跃事件。"""
        try:
            active = [
                e for e in self._events.values()
                if e.get("trigger_week", 0) <= current_week
            ]
            active.sort(key=lambda e: e.get("trigger_week", 0), reverse=True)
            return active[:recent_n]
        except Exception as e:
            logger.warning("Error getting active events: %s", e)
            return []

    def to_state_list(self) -> List[Dict]:
        """序列化为PlayerState.world_breathing_events格式。"""
        try:
            result = []
            for event_id, event in self._events.items():
                entry = dict(event)
                entry["activated"] = self._activated.get(event_id, False)
                result.append(entry)
            return result
        except Exception as e:
            logger.warning("Error serializing world breathing state: %s", e)
            return []

    @classmethod
    def from_state_list(
        cls,
        data: List[Dict],
        style: Optional[StyleManifest] = None,
        era: str = "modern",
    ) -> "WorldBreathingEngine":
        """从状态恢复。"""
        engine = cls(style=style, era=era)
        try:
            if not data or not isinstance(data, list):
                return engine
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                activated = entry.pop("activated", False)
                engine._events[entry.get("id", "")] = entry
                engine._activated[entry.get("id", "")] = activated
        except Exception as e:
            logger.warning("Error restoring world breathing state: %s", e)
        return engine
