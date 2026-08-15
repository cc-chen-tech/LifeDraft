"""Decision repository for decision history and story search."""

import logging
from typing import Any, Dict, List

from sqlalchemy import or_

from src.database.models import Decision, SessionLocal, get_db

logger = logging.getLogger(__name__)


class DecisionRepository:
    """Repository for decision and story history operations."""

    def save_decision(
        self,
        game_id: int,
        week: int,
        event_description: str,
        choice_text: str,
        effects: Dict[str, Any],
    ) -> None:
        """
        Save a decision record.

        Args:
            game_id: Game ID
            week: Week number
            event_description: Event description
            choice_text: Chosen option text
            effects: Effects dictionary
        """
        with get_db() as db:
            decision = Decision(
                game_id=game_id,
                week=week,
                event_description=event_description,
                choice_text=choice_text,
                effects=effects,
            )
            db.add(decision)
            db.commit()

    def get_decision_history(self, game_id: int) -> List[Decision]:
        """Get decision history for a game."""
        db = SessionLocal()
        try:
            return (
                db.query(Decision).filter(Decision.game_id == game_id).order_by(Decision.week).all()
            )
        finally:
            db.close()

    def get_story_history(self, game_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """
        ★ 获取历史故事文本，用于一致性验证和关键行为核查。

        Args:
            game_id: 游戏ID
            limit: 最多返回的故事数量

        Returns:
            故事列表，每个包含 week, story_text, choice_text
        """
        db = SessionLocal()
        try:
            decisions = (
                db.query(Decision)
                .filter(Decision.game_id == game_id)
                .order_by(Decision.week.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "week": d.week,
                    "story_text": d.event_description,
                    "choice_text": d.choice_text,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in reversed(decisions)  # 反转为时间顺序
            ]
        finally:
            db.close()

    def search_story_history(
        self, game_id: int, keywords: List[str], max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        ★ 搜索历史故事中包含关键词的段落，用于验证捕捉事实是否被忽略。

        Args:
            game_id: 游戏ID
            keywords: 要搜索的关键词列表
            max_results: 最多返回结果数

        Returns:
            包含关键词的故事片段列表
        """
        db = SessionLocal()
        try:
            decisions = (
                db.query(Decision).filter(Decision.game_id == game_id).order_by(Decision.week).all()
            )

            results = []
            for d in decisions:
                story_lower = d.event_description.lower() if d.event_description else ""
                for kw in keywords:
                    if kw.lower() in story_lower:
                        results.append(
                            {
                                "week": d.week,
                                "story_text": d.event_description,
                                "matched_keyword": kw,
                            }
                        )
                        break  # 一个故事只记录一次

                if len(results) >= max_results:
                    break

            return results
        finally:
            db.close()
