"""ConflictTower 冲突升级塔。

T1日常/T2区域/T3史诗 三级池冲突管理。
主线引力算法、阶段性Boss战调度。
风格感知：中国古典=劫难递增/章回Boss，西方=学年大考/终极对决
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ==================== Style Tier Configs ====================

_STYLE_TIER_CONFIGS = {
    "chinese_classic": {
        "style": "chinese_classic",
        "tier_names": {1: "江湖小事", 2: "门派劫难", 3: "天下浩劫"},
        "escalation_label": "劫难递增",
        "boss_label": "章回Boss",
    },
    "western": {
        "style": "western",
        "tier_names": {1: "日常考验", 2: "区域对决", 3: "终极决战"},
        "escalation_label": "学年大考",
        "boss_label": "终极对决",
    },
}

_DEFAULT_TIER_CONFIG = {
    "style": "default",
    "tier_names": {1: "日常冲突", 2: "区域冲突", 3: "史诗冲突"},
    "escalation_label": "冲突升级",
    "boss_label": "Boss战",
}

# Escalation threshold: consecutive weeks of T1 activity to unlock T2
_ESCALATION_THRESHOLD = 4


class ConflictTower:
    """T1日常/T2区域/T3史诗 三级池冲突管理。"""

    def __init__(self, style: Optional[str] = None):
        self.style = style
        self._tiers: Dict[int, List[dict]] = {1: [], 2: [], 3: []}
        self._main_storyline: Optional[dict] = None
        self._weekly_activity: Dict[int, List[str]] = {}
        self._unlocked_t2: bool = False

    def add_conflict(self, conflict: Optional[dict]) -> None:
        """添加冲突到对应tier池。"""
        try:
            if conflict is None or not isinstance(conflict, dict):
                logger.warning("Invalid conflict data, skipping.")
                return

            tier = conflict.get("tier", 1)
            if tier not in self._tiers:
                self._tiers[tier] = []
            self._tiers[tier].append(dict(conflict))
            logger.info("Added conflict '%s' to tier %d", conflict.get("id", "?"), tier)
        except Exception as e:
            logger.warning("Error adding conflict: %s", e)

    def get_tier(self, tier: int) -> List[dict]:
        """获取指定tier的冲突列表。"""
        try:
            return list(self._tiers.get(tier, []))
        except Exception as e:
            logger.warning("Error getting tier %d: %s", tier, e)
            return []

    def record_weekly_activity(self, week: int, active_conflicts: List[str]) -> None:
        """记录每周活跃冲突。"""
        try:
            self._weekly_activity[week] = list(active_conflicts)
        except Exception as e:
            logger.warning("Error recording weekly activity: %s", e)

    def check_escalation(self) -> List[dict]:
        """冲突升级判定：连续N周T1活跃→解锁T2。"""
        try:
            if not self._weekly_activity:
                return []

            # Check for consecutive weeks of T1 activity
            sorted_weeks = sorted(self._weekly_activity.keys())
            consecutive = 0
            t1_ids = {c.get("id") for c in self._tiers.get(1, [])}

            for i, week in enumerate(sorted_weeks):
                actives = set(self._weekly_activity[week])
                if actives & t1_ids:
                    consecutive += 1
                else:
                    consecutive = 0

                if consecutive >= _ESCALATION_THRESHOLD:
                    # Unlock T2 conflicts
                    unlocked = list(self._tiers.get(2, []))
                    if unlocked:
                        self._unlocked_t2 = True
                        logger.info("T2 conflicts unlocked after %d consecutive weeks", consecutive)
                        return unlocked

            return []
        except Exception as e:
            logger.warning("Error checking escalation: %s", e)
            return []

    def set_main_storyline(self, storyline: dict) -> None:
        """设置主线剧情。"""
        try:
            self._main_storyline = dict(storyline) if storyline else None
        except Exception as e:
            logger.warning("Error setting main storyline: %s", e)

    def compute_deviation(self, player_progress: dict) -> float:
        """主线引力算法：计算偏离核心冲突的程度(0-1)。"""
        try:
            if not self._main_storyline or not player_progress:
                return 0.0

            current_focus = player_progress.get("current_focus", "")
            main_name = self._main_storyline.get("name", "")
            main_desc = self._main_storyline.get("description", "")
            milestones = self._main_storyline.get("milestones", [])
            current_milestone = player_progress.get("main_quest_milestone", "")

            # Simple heuristic: if current focus contains main quest keywords, low deviation
            main_keywords = set(main_name) | set(main_desc)
            focus_keywords = set(current_focus)
            overlap = len(main_keywords & focus_keywords)

            # Check if focusing on a side quest (T1 conflict)
            t1_names = [c.get("name", "") for c in self._tiers.get(1, [])]
            is_side_quest = any(name in current_focus for name in t1_names if name)

            if is_side_quest:
                deviation = 0.7
            elif overlap > 5:
                deviation = 0.2
            else:
                deviation = 0.5

            # Adjust based on milestone progress
            if current_milestone and milestones:
                try:
                    idx = milestones.index(current_milestone)
                    progress = idx / max(len(milestones) - 1, 1)
                    deviation = max(0.0, deviation - progress * 0.2)
                except ValueError:
                    pass

            return max(0.0, min(1.0, deviation))
        except Exception as e:
            logger.warning("Error computing deviation: %s", e)
            return 0.0

    def check_boss_trigger(
        self,
        current_week: int,
        milestone: str = "",
        tier_2_resolved: int = 0,
    ) -> Optional[dict]:
        """阶段性Boss战触发条件。"""
        try:
            t3_conflicts = self._tiers.get(3, [])
            if not t3_conflicts:
                return None

            milestones = self._main_storyline.get("milestones", []) if self._main_storyline else []

            # Boss trigger conditions:
            # 1. Milestone is at least "集齐神器" (3rd milestone or later)
            # 2. At least 2 T2 conflicts resolved
            if milestones and milestone in milestones:
                milestone_idx = milestones.index(milestone)
                if milestone_idx >= 2 and tier_2_resolved >= 2:
                    boss = t3_conflicts[0]
                    return {
                        "conflict_id": boss.get("id", ""),
                        "boss": boss.get("name", ""),
                        "description": boss.get("description", ""),
                        "triggered_week": current_week,
                    }

            return None
        except Exception as e:
            logger.warning("Error checking boss trigger: %s", e)
            return None

    def get_tier_config(self) -> dict:
        """获取当前风格的层级配置。"""
        try:
            if self.style and self.style in _STYLE_TIER_CONFIGS:
                return dict(_STYLE_TIER_CONFIGS[self.style])
            return dict(_DEFAULT_TIER_CONFIG)
        except Exception as e:
            logger.warning("Error getting tier config: %s", e)
            return dict(_DEFAULT_TIER_CONFIG)

    def get_conflict_directive(self) -> str:
        """生成冲突级别约束注入Prompt。"""
        try:
            active_t1 = len(self._tiers.get(1, []))
            active_t2 = len(self._tiers.get(2, []))
            active_t3 = len(self._tiers.get(3, []))

            config = self.get_tier_config()
            tier_names = config.get("tier_names", {})

            parts = ["【冲突层级约束】"]
            if active_t1:
                parts.append(f"{tier_names.get(1, 'T1')}冲突: {active_t1}个活跃")
            if active_t2:
                parts.append(f"{tier_names.get(2, 'T2')}冲突: {active_t2}个活跃")
            if active_t3:
                parts.append(f"{tier_names.get(3, 'T3')}冲突: {active_t3}个活跃")

            return " ".join(parts)
        except Exception as e:
            logger.warning("Error generating conflict directive: %s", e)
            return ""

    def to_state_dict(self) -> Dict:
        """序列化为PlayerState.conflict_levels格式。"""
        try:
            return {
                "style": self.style,
                "tiers": {str(k): v for k, v in self._tiers.items()},
                "main_storyline": self._main_storyline,
                "weekly_activity": {str(k): v for k, v in self._weekly_activity.items()},
                "unlocked_t2": self._unlocked_t2,
            }
        except Exception as e:
            logger.warning("Error serializing conflict tower: %s", e)
            return {}

    @classmethod
    def from_state_dict(cls, data: Dict, style: Optional[str] = None) -> "ConflictTower":
        """从状态恢复。"""
        tower = cls(style=style or (data.get("style") if data else None))
        try:
            if not data or not isinstance(data, dict):
                return tower

            tiers_data = data.get("tiers", {})
            for tier_str, conflicts in tiers_data.items():
                try:
                    tier_num = int(tier_str)
                    tower._tiers[tier_num] = list(conflicts)
                except (ValueError, TypeError):
                    pass

            tower._main_storyline = data.get("main_storyline")
            weekly = data.get("weekly_activity", {})
            for week_str, actives in weekly.items():
                try:
                    tower._weekly_activity[int(week_str)] = actives
                except (ValueError, TypeError):
                    pass

            tower._unlocked_t2 = data.get("unlocked_t2", False)
        except Exception as e:
            logger.warning("Error restoring conflict tower: %s", e)
        return tower
