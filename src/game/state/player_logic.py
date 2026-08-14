"""玩家核心业务逻辑。

此模块定义了 PlayerState 的核心业务逻辑部分，作为 Mixin 类供 PlayerState 继承。
包含状态更新、时间推进、轮次管理和上下文构建等方法。
"""

import re
from typing import Any, Dict, List, Optional

from config.settings import settings


def _extract_start_year_from_era(era: Dict[str, Any]) -> int:
    """Return the configured start year, including legacy text-only era settings."""
    year = era.get("year")
    if isinstance(year, bool):
        year = None
    if isinstance(year, (int, float)):
        numeric_year = int(year)
        if 1 <= numeric_year <= 3999:
            return numeric_year
    if isinstance(year, str):
        match = re.search(r"\b([1-3][0-9]{3})\b", year)
        if match:
            return int(match.group(1))

    text = " ".join(
        str(era.get(key) or "")
        for key in ("era_name", "era_description", "world_context")
    )
    match = re.search(r"(?<!\d)([1-3][0-9]{3})(?!\d)", text)
    if match:
        return int(match.group(1))

    return 2024


class PlayerLogicMixin:
    """玩家核心业务逻辑 Mixin。

    包含状态更新、时间管理、游戏进度等核心逻辑。
    """

    # 类型声明：这些属性由 PlayerDataMixin 定义，在组合类中可用
    energy: int
    mood: int
    knowledge: int
    relationships: Dict[str, int]
    week: int
    age: int
    current_round: int
    rounds_per_week: int
    character_settings: Dict[str, Any]
    round_history: List[Dict[str, Any]]

    def update(
        self,
        energy: Optional[int] = None,
        mood: Optional[int] = None,
        knowledge: Optional[int] = None,
        relationships: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Update player state with new values.

        Args:
            energy: Change in energy (can be negative)
            mood: Change in mood (can be negative)
            knowledge: Change in knowledge (can be negative)
            relationships: Dict of relationship changes {name: change}
        """
        if energy is not None:
            self.energy = max(
                settings.MIN_RESOURCE, min(settings.MAX_RESOURCE, self.energy + energy)
            )

        if mood is not None:
            self.mood = max(settings.MIN_RESOURCE, min(settings.MAX_RESOURCE, self.mood + mood))

        if knowledge is not None:
            self.knowledge = max(
                settings.MIN_RESOURCE,
                min(settings.MAX_RESOURCE, self.knowledge + knowledge),
            )

        if relationships is not None:
            for name, change in relationships.items():
                current = self.relationships.get(name, 50)  # Default to neutral
                self.relationships[name] = max(
                    settings.MIN_RESOURCE, min(settings.MAX_RESOURCE, current + change)
                )

    def advance_week(self) -> None:
        """Advance to the next week."""
        self.week += 1
        # Reset round counter for new week
        self.current_round = 0
        # Update age: every 52 weeks = 1 year
        # Get the starting age from character settings if available
        starting_age = self.character_settings.get("age", {}).get("age", settings.STARTING_AGE)
        self.age = starting_age + int(self.week / settings.WEEKS_PER_YEAR)

    def advance_round(self) -> bool:
        """
        Advance to the next round within the week.

        Returns:
            True if all rounds complete (need weekly summary), False otherwise
        """
        self.current_round += 1
        if self.current_round >= self.rounds_per_week:
            # All rounds complete, need to generate weekly summary
            return True
        return False

    def is_week_complete(self) -> bool:
        """
        Check if all rounds for current week are complete.

        Returns:
            True if current week's rounds are all done
        """
        current_week_rounds = self.get_current_week_rounds()
        return len(current_week_rounds) >= self.rounds_per_week

    def get_current_week_rounds(self) -> list:
        """
        Get all round records for the current week.

        Returns:
            List of round records for current week
        """
        return [r for r in self.round_history if r.get("week") == self.week]

    def get_game_date_info(self) -> Dict[str, Any]:
        """
        基于 era.year + week 计算游戏内日期信息。

        Returns:
            包含年、月、周等时间信息的字典
        """
        era = self.character_settings.get("era", {})
        start_year = _extract_start_year_from_era(era) if isinstance(era, dict) else 2024
        years_passed = self.week // 52
        current_year = start_year + years_passed
        week_in_year = self.week % 52
        current_month = week_in_year // 4 + 1
        week_in_month = week_in_year % 4 + 1

        # 计算大致季节
        if 3 <= current_month <= 5:
            season = "春"
        elif 6 <= current_month <= 8:
            season = "夏"
        elif 9 <= current_month <= 11:
            season = "秋"
        else:
            season = "冬"

        return {
            "year": current_year,
            "month": current_month,
            "week_in_month": week_in_month,
            "season": season,
            "total_week": self.week + 1,  # ★ week 从0开始，显示时+1，与前端一致
            "age": self.age,
            "date_string": f"{current_year}年{current_month}月第{week_in_month}周",
            "date_string_en": f"Year {current_year}, Month {current_month}, Week {week_in_month}",
        }

    def get_round_context(self) -> str:
        """
        Build context string from previous rounds in current week.
        Uses full story text for richer narrative continuity.
        Skips the last round since it's covered by continuation_mandate.

        Returns:
            Formatted string of previous rounds' full stories and choices
        """
        week_rounds = self.get_current_week_rounds()
        if not week_rounds:
            return ""

        # Skip the last round — it's already passed via continuation_mandate
        # to avoid duplication and save tokens
        earlier_rounds = week_rounds[:-1]
        if not earlier_rounds:
            return ""

        round_names = ["周一", "周中", "周末"]
        context_parts = []
        for r in earlier_rounds:
            round_idx = r.get("round", 0)
            round_name = (
                round_names[round_idx] if round_idx < len(round_names) else f"第{round_idx+1}轮"
            )
            date_str = r.get("date_info", {}).get("date_string", "")
            date_prefix = f"({date_str}) " if date_str else ""
            event_concluded = r.get("event_concluded", True)
            concluded_marker = "" if event_concluded else " ⚠️未完结"
            choice = r.get("choice", "")

            # Use full event_description for richer context; fallback to summary
            full_story = r.get("event_description", "") or r.get("summary", "")
            continuation = r.get("story_continuation", "")

            parts = [f"【{round_name}】{date_prefix}{concluded_marker}"]
            parts.append(full_story)
            parts.append(f"(选择了: {choice})")
            if continuation:
                parts.append(f"→ 后续发展: {continuation}")
            context_parts.append("\n".join(parts))

        # 在最后一轮的文本后添加场景提示，帮助AI保持场景连贯性
        if earlier_rounds:
            last_round = earlier_rounds[-1]
            last_story = last_round.get("story_continuation", "") or last_round.get(
                "event_description", ""
            )
            if last_story:
                last_sentences = last_story.strip().split("。")[-3:]
                scene_hint = "。".join(s for s in last_sentences if s.strip())
                if scene_hint:
                    context_parts.append(f"\n【上一轮结束场景】{scene_hint}")

        return "\n\n".join(context_parts)

    def is_game_over(self) -> bool:
        """Check if game has ended."""
        from src.game.daily_timeline import is_daily_timeline, normalize_daily_timeline

        if is_daily_timeline(self):
            timeline = normalize_daily_timeline(self.timeline)
            return bool(timeline.get("game_over")) or int(
                timeline.get("completed_days", 0)
            ) >= int(timeline.get("total_days", 672))
        # Game ends after TOTAL_WEEKS weeks
        return self.week >= settings.TOTAL_WEEKS

    def get_current_phase(self) -> str:
        """Get current life phase based on week."""
        if self.week < 24:
            return "early_career"
        elif self.week < 48:
            return "establishing"
        elif self.week < 72:
            return "growth"
        else:
            return "consolidation"

    def get_round_name(self, language: str = "zh") -> str:
        """
        Get display name for current round.

        Args:
            language: 'zh' or 'en'

        Returns:
            Round name string
        """
        if language == "zh":
            names = ["周一", "周中", "周末"]
        else:
            names = ["Monday", "Midweek", "Weekend"]

        if self.current_round < len(names):
            return names[self.current_round]
        return f"Round {self.current_round + 1}"
