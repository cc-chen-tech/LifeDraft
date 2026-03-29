"""Character introduction service for round system.

Handles the generation, queuing, and introduction of new characters
into the story world.
"""

import logging
import random
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CharacterIntroductionService:
    """Service for managing character introductions in rounds.

    This service handles:
    - Probabilistic generation of new characters
    - Queuing characters for future introduction
    - Detecting appropriate introduction opportunities
    - Executing character introductions
    """

    def __init__(
        self,
        player_state_getter: Callable[[], Any],
        character_creator: Any,
        character_settings_setter: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Args:
            player_state_getter: Function that returns current player state
            character_creator: CharacterCreator instance
            character_settings_setter: Function to update character settings (optional)
        """
        self._get_player_state = player_state_getter
        self.character_creator = character_creator
        self._set_character_settings = character_settings_setter

    @property
    def player_state(self):
        return self._get_player_state()

    def maybe_generate_new_character(
        self, probability: float = 0.08
    ) -> Optional[Dict[str, Any]]:
        """
        以一定概率生成新的人物，存入待引入队列。
        人物不会立即出现在故事中，而是等待合适的场景再自然引入。

        Args:
            probability: 生成新人物的概率（默认0.08，即8%）

        Returns:
            新生成的人物字典（存入队列），如果没有生成则返回None
        """
        player_state = self.player_state
        if not player_state:
            return None

        # 检查待引入队列是否已满（最多3个待引入人物）
        pending = getattr(player_state, "pending_character_introductions", []) or []
        if len(pending) >= 3:
            logger.debug("待引入人物队列已满，跳过生成")
            return None

        # 概率判断
        if random.random() > probability:
            logger.debug(f"本轮不生成新人物（概率{probability:.0%}）")
            return None

        logger.info(f"触发新人物生成（概率{probability:.0%}）")

        try:
            # 获取当前设定
            character_settings = player_state.character_settings or {}
            player_name = player_state.player_name or "主角"
            life_vision = player_state.life_vision or ""

            # 获取已有的关系人物（包括待引入的）
            existing_people = self._collect_existing_people(character_settings, pending)

            new_person = self.character_creator.generate_single_relationship_person(
                player_name=player_name,
                life_vision=life_vision,
                previous_settings=character_settings,
                existing_people=existing_people,
                person_index=len(existing_people),
                total_needed=len(existing_people) + 1,
            )

            if not new_person or not new_person.get("name"):
                logger.warning("新人物生成失败：缺少名字")
                return None

            new_name = new_person["name"]
            logger.info(
                f"成功生成新人物：{new_name} ({new_person.get('role', '未知')})"
            )

            # 根据人物角色和当前状态，决定引入场景
            intro_context = self.determine_introduction_context(new_person)

            # 存入待引入队列，而非立即添加
            pending_entry = {
                "character_data": new_person,
                "created_week": player_state.week,
                "introduction_context": intro_context,
                "priority": self.calculate_introduction_priority(new_person),
                "attempts": 0,
            }

            # 确保 pending_character_introductions 字段存在
            if not hasattr(player_state, "pending_character_introductions"):
                player_state.pending_character_introductions = []

            player_state.pending_character_introductions.append(pending_entry)
            logger.info(
                f"新人物 {new_name} 已加入待引入队列（场景：{intro_context}，优先级：{pending_entry['priority']}）"
            )

            return new_person

        except Exception as e:
            logger.error(f"生成新人物失败：{e}")
            return None

    def _collect_existing_people(self, character_settings: Dict, pending: list) -> list:
        """收集所有已存在的人物，包括家庭成员、关系人物和待引入人物。"""
        existing_people = []

        if "relationships" in character_settings:
            existing_people = character_settings["relationships"].get("key_people", [])

        if "family" in character_settings:
            family_members = character_settings["family"].get("family_members", [])
            for member in family_members:
                if isinstance(member, dict):
                    existing_people.append(member)

        # 还要包含待引入人物，避免名字重复
        for pending_char in pending:
            if pending_char.get("character_data", {}).get("name"):
                existing_people.append({"name": pending_char["character_data"]["name"]})

        return existing_people

    def determine_introduction_context(self, new_person: Dict[str, Any]) -> str:
        """
        根据人物角色和当前玩家状态，决定最合适的引入场景。

        Args:
            new_person: 新人物数据

        Returns:
            引入场景类型：work/social/location_change/education/random
        """
        role = new_person.get("role", "").lower()

        # 根据角色类型判断
        if any(
            kw in role
            for kw in [
                "同事",
                "上司",
                "下属",
                "合作",
                "客户",
                "colleague",
                "boss",
                "partner",
                "client",
            ]
        ):
            return "work"
        elif any(
            kw in role
            for kw in [
                "同学",
                "老师",
                "导师",
                "student",
                "classmate",
                "teacher",
                "mentor",
            ]
        ):
            return "education"
        elif any(kw in role for kw in ["邻居", "neighbor"]):
            return "location_change"

        # 根据当前玩家状态判断
        player_state = self.player_state
        character_settings = player_state.character_settings or {}
        world_model = player_state.world_model_data or {}

        # 检查是否有最近的工作变化
        career_records = world_model.get("career_records", {})
        player_name = player_state.player_name or "主角"
        if player_name in career_records:
            career = career_records[player_name]
            if isinstance(career, dict):
                since_week = career.get("since_week", 0)
                current_week = player_state.week
                if current_week - since_week < 4:  # 4周内换过工作
                    return "work"

        # 默认为社交场景
        return "social"

    def calculate_introduction_priority(self, new_person: Dict[str, Any]) -> int:
        """
        计算人物的引入优先级。

        Args:
            new_person: 新人物数据

        Returns:
            优先级（0-10，越高越优先）
        """
        priority = 5  # 基础优先级

        # 特殊角色提高优先级
        role = new_person.get("role", "").lower()
        if any(
            kw in role for kw in ["恋人", "爱人", "伴侣", "lover", "partner", "spouse"]
        ):
            priority += 3
        elif any(kw in role for kw in ["导师", "贵人", "mentor", "patron"]):
            priority += 2

        # 高亲密度起始值提高优先级
        affinity = new_person.get("affinity", 50)
        if affinity >= 70:
            priority += 1

        return min(10, priority)

    def check_introduction_opportunity(self) -> Optional[Dict[str, Any]]:
        """
        检查当前轮是否有合适的机会引入待引入人物。

        Returns:
            如果有机会，返回待引入人物数据；否则返回 None
        """
        player_state = self.player_state
        pending = getattr(player_state, "pending_character_introductions", []) or []
        if not pending:
            return None

        current_week = player_state.week

        # 按优先级排序，并考虑等待时间
        sorted_pending = sorted(
            pending, key=lambda x: (-x.get("priority", 0), x.get("created_week", 0))
        )

        for entry in sorted_pending:
            created_week = entry.get("created_week", current_week)
            attempts = entry.get("attempts", 0)
            intro_context = entry.get("introduction_context", "random")

            # 计算等待周数
            waiting_weeks = current_week - created_week

            # 强制引入条件：等待超过4周或尝试超过3次
            if waiting_weeks >= 4 or attempts >= 3:
                logger.info(
                    f"待引入人物 {entry['character_data'].get('name')} 已等待{waiting_weeks}周，强制引入"
                )
                return entry

            # 检查是否有匹配的引入场景
            if self.matches_introduction_scene(intro_context):
                logger.info(
                    f"发现匹配的引入场景 [{intro_context}]，准备引入 {entry['character_data'].get('name')}"
                )
                return entry

        return None

    def matches_introduction_scene(self, intro_context: str) -> bool:
        """
        检查当前是否匹配指定的引入场景。

        Args:
            intro_context: 引入场景类型

        Returns:
            是否匹配
        """
        player_state = self.player_state
        character_settings = player_state.character_settings or {}
        world_model = player_state.world_model_data or {}
        round_history = player_state.round_history or []

        # 获取最近几轮的故事内容来判断场景
        recent_stories = []
        for r in round_history[-3:]:
            recent_stories.append(r.get("event_description", ""))
            recent_stories.append(r.get("summary", ""))
        recent_text = " ".join(recent_stories).lower()

        if intro_context == "work":
            # 检查是否涉及工作相关内容
            work_keywords = [
                "公司",
                "工作",
                "项目",
                "会议",
                "同事",
                "办公室",
                "work",
                "office",
                "project",
                "meeting",
            ]
            # 或者检查职业状态是否有变化
            career_records = world_model.get("career_records", {})
            player_name = player_state.player_name or "主角"
            if player_name in career_records:
                career = career_records[player_name]
                if isinstance(career, dict):
                    since_week = career.get("since_week", 0)
                    if player_state.week - since_week < 6:  # 6周内换过工作
                        return True
            return any(kw in recent_text for kw in work_keywords)

        elif intro_context == "social":
            # 检查是否涉及社交活动
            social_keywords = [
                "聚会",
                "朋友",
                "餐厅",
                "酒吧",
                "party",
                "社交",
                "friend",
                "restaurant",
                "bar",
            ]
            return any(kw in recent_text for kw in social_keywords)

        elif intro_context == "location_change":
            # 检查是否有位置变化
            locations = world_model.get("character_locations", {})
            player_name = player_state.player_name or "主角"
            if player_name in locations:
                loc = locations[player_name]
                if isinstance(loc, dict):
                    since_week = loc.get("since_week", 0)
                    if player_state.week - since_week < 4:  # 4周内搬过家
                        return True
            return False

        elif intro_context == "education":
            # 检查是否涉及学习相关内容
            edu_keywords = [
                "学校",
                "学习",
                "课程",
                "培训",
                "school",
                "study",
                "course",
                "training",
            ]
            return any(kw in recent_text for kw in edu_keywords)

        # random 类型始终可以引入
        return intro_context == "random"

    def introduce_pending_character(
        self, pending_entry: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        执行人物引入：从待引入队列移动到正式关系列表。

        Args:
            pending_entry: 待引入人物条目

        Returns:
            引入的人物数据
        """
        player_state = self.player_state
        new_person = pending_entry.get("character_data")
        if not new_person or not new_person.get("name"):
            return None

        new_name = new_person["name"]

        try:
            # 添加到 character_settings 的 key_people
            character_settings = player_state.character_settings or {}
            if "relationships" not in character_settings:
                character_settings["relationships"] = {"key_people": []}
            if "key_people" not in character_settings["relationships"]:
                character_settings["relationships"]["key_people"] = []

            character_settings["relationships"]["key_people"].append(new_person)
            player_state.character_settings = character_settings

            # 添加到 relationships
            initial_affinity = new_person.get("affinity", 50)
            player_state.relationships[new_name] = initial_affinity

            # 从待引入队列中移除
            pending = player_state.pending_character_introductions
            player_state.pending_character_introductions = [
                e
                for e in pending
                if e.get("character_data", {}).get("name") != new_name
            ]

            logger.info(
                f"新人物 {new_name} 已正式引入（初始亲密度：{initial_affinity}）"
            )

            return new_person

        except Exception as e:
            logger.error(f"引入人物失败：{e}")
            return None
