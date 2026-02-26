"""Historical summary selection: relevance-based and random fallback.

Extracted from game_loop.py to reduce God Class complexity.
All methods are static and accept a PlayerState instance.
"""
import logging
import math
import random
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class HistoricalSummarySelector:
    """Selects historical summaries for context injection into story generation."""

    @staticmethod
    def select_relevant_historical_summary(
        player_state,
    ) -> Tuple[Optional[str], Optional[str]]:
        """基于当前上下文相关性选择历史总结（替代纯随机选择）。

        从 pending_storylines、active_commitments、上一轮故事中提取关键词，
        对每条历史总结计算相关性分数，选择得分最高的。

        Returns:
            Tuple of (weekly_summary, yearly_summary)
        """
        if not player_state:
            return None, None

        current_week = player_state.week

        # 1. 提取上下文关键词
        keywords: set = set()

        # 从 pending_storylines 提取
        for sl in player_state.pending_storylines:
            desc = sl.get("description", "")
            if desc:
                keywords.add(desc)
            for char in sl.get("related_characters", []):
                keywords.add(char)

        # 从 active_commitments 提取
        wm_data = player_state.world_model_data
        for c in wm_data.get("active_commitments", []):
            if c.get("status") == "pending":
                keywords.add(c.get("description", ""))
                for party in c.get("parties", []):
                    keywords.add(party)

        # 从上一轮故事提取人物名
        last_story = player_state.last_round_full_story or ""
        if last_story and player_state.character_settings:
            all_people: list = []
            relationships = player_state.character_settings.get("relationships", {})
            for person in relationships.get("key_people", []):
                name = person.get("name", "")
                if name:
                    all_people.append(name)
            family = player_state.character_settings.get("family", {})
            for member in family.get("family_members", []):
                name = member.get("name", "") if isinstance(member, dict) else ""
                if name:
                    all_people.append(name)
            for name in all_people:
                if name in last_story:
                    keywords.add(name)

        # 从激活的伏笔种子提取
        for seed in player_state.foreshadowing_seeds:
            if seed.get("status") == "active":
                for char in seed.get("related_characters", []):
                    keywords.add(char)

        # 过滤空字符串
        keywords = {k for k in keywords if k and len(k) > 1}

        # 如果没有关键词，回退到随机选择
        if not keywords:
            return HistoricalSummarySelector.select_random_historical_summary_fallback(
                player_state
            )

        weekly_summary = None
        yearly_summary = None

        # 2. 对周总结评分并选择
        if player_state.weekly_summaries:
            best_score = 0
            best_summary = None
            for entry in player_state.weekly_summaries:
                summary_week = entry.get("week", 0)
                distance = current_week - summary_week
                if distance <= 0:
                    continue

                text = entry.get("summary", "")
                if not text:
                    continue

                hits = sum(1 for kw in keywords if kw in text)
                if hits == 0:
                    continue

                decay = 1 + (distance / 10.0)
                score = hits / decay

                if score > best_score:
                    best_score = score
                    best_summary = entry

            if best_summary and best_score > 0.1:
                weekly_summary = best_summary.get("summary", "")
                logger.info(
                    f"📚 相关性选中第{best_summary.get('week', 0)}周的周总结"
                    f"（得分{best_score:.2f}，关键词: {list(keywords)[:3]}）"
                )

        # 3. 对年度总结评分并选择
        if player_state.yearly_summaries:
            best_score = 0
            best_summary = None
            for entry in player_state.yearly_summaries:
                end_week = entry.get("end_week", 0)
                distance = current_week - end_week
                if distance <= 0:
                    continue

                text = entry.get("summary", "")
                if not text:
                    continue

                hits = sum(1 for kw in keywords if kw in text)
                if hits == 0:
                    continue

                decay = 1 + (distance / 24.0)
                score = hits / decay

                if score > best_score:
                    best_score = score
                    best_summary = entry

            if best_summary and best_score > 0.1:
                yearly_summary = best_summary.get("summary", "")
                logger.info(
                    f"📚 相关性选中第{best_summary.get('end_week', 0)}周的年度总结"
                    f"（得分{best_score:.2f}）"
                )

        return weekly_summary, yearly_summary

    @staticmethod
    def select_random_historical_summary_fallback(
        player_state,
    ) -> Tuple[Optional[str], Optional[str]]:
        """随机选择历史总结（当无关键词时的回退方案）。

        概率随时间间距增加而降低。

        Returns:
            Tuple of (weekly_summary, yearly_summary)
        """
        if not player_state:
            return None, None

        current_week = player_state.week
        weekly_summary = None
        yearly_summary = None

        if player_state.weekly_summaries:
            for summary_entry in reversed(player_state.weekly_summaries):
                summary_week = summary_entry.get("week", 0)
                distance = current_week - summary_week
                if distance <= 0:
                    continue
                prob = 0.1 * math.exp(-distance / 20)
                if random.random() < prob:
                    weekly_summary = summary_entry.get("summary", "")
                    if weekly_summary:
                        logger.info(
                            f"随机选中第{summary_week}周的周总结"
                            f"（间距{distance}周，概率{prob:.1%}）"
                        )
                        break

        if player_state.yearly_summaries:
            for summary_entry in reversed(player_state.yearly_summaries):
                end_week = summary_entry.get("end_week", 0)
                distance = current_week - end_week
                if distance <= 0:
                    continue
                prob = 0.08 * math.exp(-distance / 48)
                if random.random() < prob:
                    yearly_summary = summary_entry.get("summary", "")
                    if yearly_summary:
                        logger.info(
                            f"随机选中第{end_week}周的年度总结"
                            f"（间距{distance}周，概率{prob:.1%}）"
                        )
                        break

        return weekly_summary, yearly_summary
