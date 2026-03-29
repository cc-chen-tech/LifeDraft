"""
关系事件MCP服务
检测和触发人物关系事件
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.game.relationship_events import (
    RELATIONSHIP_EVENTS,
    EventCategory,
    RelationshipEventDef,
    get_event_by_type,
    get_events_by_category,
)

if TYPE_CHECKING:
    from src.game.state import CharacterState, PlayerState

logger = logging.getLogger(__name__)


@dataclass
class TriggeredEvent:
    """触发的事件信息"""

    event_type: str  # 事件类型
    character_name: str  # 涉及的角色名
    event_def: RelationshipEventDef  # 事件定义
    era_name: str  # 时代适配后的事件名
    description: str  # 事件描述
    priority: int = 0  # 优先级（用于排序）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "character_name": self.character_name,
            "era_name": self.era_name,
            "description": self.description,
            "category": self.event_def.category.value,
            "priority": self.priority,
        }


class RelationshipMCPService:
    """
    关系事件检测和触发的MCP服务

    主要功能：
    1. 检测玩家与NPC之间是否满足事件触发条件
    2. 根据时代背景生成适配的事件描述
    3. 记录已触发的事件避免重复
    """

    def __init__(
        self, player_gender: str = "male", player_orientation: str = "heterosexual"
    ):
        """
        初始化MCP服务

        Args:
            player_gender: 主角性别 (male/female/other)
            player_orientation: 主角性倾向
        """
        self.player_gender = player_gender
        self.player_orientation = player_orientation

    def is_romance_compatible(
        self,
        char_orientation: str,
        char_gender: str,
        player_orientation: Optional[str] = None,
        player_gender: Optional[str] = None,
    ) -> bool:
        """
        检查两个角色是否可能发展浪漫关系

        Args:
            char_orientation: NPC的性倾向
            char_gender: NPC的性别
            player_orientation: 主角的性倾向
            player_gender: 主角的性别

        Returns:
            是否可能发展浪漫关系
        """
        player_orientation = player_orientation or self.player_orientation
        player_gender = player_gender or self.player_gender

        # 无性恋不发展浪漫关系
        if char_orientation == "asexual" or player_orientation == "asexual":
            return False

        # 判断性别是否相同
        same_gender = self._is_same_gender(char_gender, player_gender)

        # 双性恋可以与任何性别发展关系
        if char_orientation == "bisexual" and player_orientation == "bisexual":
            return True

        # 异性恋需要不同性别
        if char_orientation == "heterosexual" and player_orientation == "heterosexual":
            return not same_gender

        # 同性恋需要相同性别
        if char_orientation == "homosexual" and player_orientation == "homosexual":
            return same_gender

        # 双性恋与异性恋
        if (
            char_orientation == "bisexual" and player_orientation == "heterosexual"
        ) or (char_orientation == "heterosexual" and player_orientation == "bisexual"):
            return not same_gender

        # 双性恋与同性恋
        if (char_orientation == "bisexual" and player_orientation == "homosexual") or (
            char_orientation == "homosexual" and player_orientation == "bisexual"
        ):
            return same_gender

        # 其他情况默认不兼容
        return False

    def _is_same_gender(self, gender1: str, gender2: str) -> bool:
        """判断两个性别是否相同"""
        g1 = gender1.lower().strip() if gender1 else ""
        g2 = gender2.lower().strip() if gender2 else ""

        def is_male(g: str) -> bool:
            # 检查是否为男性（排除 female 的干扰）
            if any(k in g for k in ["female", "woman", "女", "女性"]):
                return False
            return any(k in g for k in ["male", "man", "男", "男性"]) or g == "male"

        def is_female(g: str) -> bool:
            return any(k in g for k in ["female", "woman", "女", "女性"])

        g1_is_male = is_male(g1)
        g2_is_male = is_male(g2)
        g1_is_female = is_female(g1)
        g2_is_female = is_female(g2)

        if g1_is_male and g2_is_male:
            return True
        if g1_is_female and g2_is_female:
            return True

        return False

    def check_event_conditions(
        self,
        event_def: RelationshipEventDef,
        character: "CharacterState",
        player: "PlayerState",
    ) -> bool:
        """
        检查单个事件的触发条件

        Args:
            event_def: 事件定义
            character: NPC角色状态
            player: 玩家状态

        Returns:
            是否满足触发条件
        """
        # 检查是否已经触发过
        if event_def.event_type in character.triggered_events:
            return False

        # 检查亲密度
        if event_def.is_negative_threshold:
            if (
                event_def.required_affinity > 0
                and character.affinity > event_def.required_affinity
            ):
                return False
        else:
            if (
                event_def.required_affinity > 0
                and character.affinity < event_def.required_affinity
            ):
                return False

        # 检查信任度
        if event_def.is_negative_threshold:
            if (
                event_def.required_trust > 0
                and character.trust > event_def.required_trust
            ):
                return False
        else:
            if (
                event_def.required_trust > 0
                and character.trust < event_def.required_trust
            ):
                return False

        # 检查尊重度
        if event_def.required_respect > 0:
            if event_def.is_negative_threshold:
                if character.respect > event_def.required_respect:
                    return False
            else:
                if character.respect < event_def.required_respect:
                    return False

        # 检查互动次数
        if event_def.min_interaction_count > 0:
            if character.interaction_count < event_def.min_interaction_count:
                return False

        # 检查性倾向匹配
        if event_def.require_orientation_match:
            if not self.is_romance_compatible(
                character.sexual_orientation,
                character.gender,
            ):
                return False

        # 检查感情状态
        if event_def.require_single:
            if character.relationship_status != "single":
                return False

        if event_def.require_dating:
            if character.relationship_status not in ["dating", "engaged", "married"]:
                return False

        if event_def.require_married:
            if character.relationship_status != "married":
                return False

        # 检查外部阻力
        if event_def.require_external_obstacle:
            if not character.has_external_obstacle:
                return False

        # 检查高能力要求
        if event_def.require_high_competence:
            if character.competence < 70:
                return False

        # 检查高影响力要求
        if event_def.require_high_influence:
            if character.influence < 60:
                return False

        # 检查历史最高亲密度（反目成仇需要曾经关系好）
        if event_def.check_peak_affinity:
            if character.peak_affinity < event_def.peak_affinity_threshold:
                return False

        return True

    def _check_events_by_category(
        self,
        category: "EventCategory",
        character: "CharacterState",
        player: "PlayerState",
        era: str,
        base_priority: int,
        priority_overrides: Optional[Dict[str, int]] = None,
    ) -> List[TriggeredEvent]:
        """
        通用事件检查方法：检查指定类别的所有事件是否满足触发条件。

        Args:
            category: 事件类别
            character: NPC角色状态
            player: 玩家状态
            era: 时代背景
            base_priority: 基础优先级
            priority_overrides: 特定事件类型的优先级覆盖 {event_type: priority}

        Returns:
            触发的事件列表
        """
        triggered = []
        events = get_events_by_category(category)

        for event_def in events:
            if self.check_event_conditions(event_def, character, player):
                era_name = event_def.get_era_name(era)
                description = event_def.description_template.format(
                    character=character.name
                )
                priority = base_priority
                if priority_overrides and event_def.event_type in priority_overrides:
                    priority = priority_overrides[event_def.event_type]

                triggered.append(
                    TriggeredEvent(
                        event_type=event_def.event_type,
                        character_name=character.name,
                        event_def=event_def,
                        era_name=era_name,
                        description=description,
                        priority=priority,
                    )
                )

        return triggered

    def check_romance_events(
        self, character: "CharacterState", player: "PlayerState", era: str
    ) -> List[TriggeredEvent]:
        """检查浪漫关系事件"""
        return self._check_events_by_category(
            EventCategory.ROMANCE,
            character,
            player,
            era,
            base_priority=90,
            priority_overrides={"marriage_proposal": 100},
        )

    def check_friendship_events(
        self, character: "CharacterState", player: "PlayerState", era: str
    ) -> List[TriggeredEvent]:
        """检查友谊信任事件"""
        return self._check_events_by_category(
            EventCategory.FRIENDSHIP, character, player, era, base_priority=80
        )

    def check_negative_events(
        self, character: "CharacterState", player: "PlayerState", era: str
    ) -> List[TriggeredEvent]:
        """检查负面关系事件"""
        return self._check_events_by_category(
            EventCategory.NEGATIVE, character, player, era, base_priority=70
        )

    def check_special_events(
        self, character: "CharacterState", player: "PlayerState", era: str
    ) -> List[TriggeredEvent]:
        """检查特殊关系事件"""
        return self._check_events_by_category(
            EventCategory.SPECIAL, character, player, era, base_priority=60
        )

    def get_triggered_events(
        self, player: "PlayerState", era: str = "modern", max_events: int = 2
    ) -> List[Dict[str, Any]]:
        """
        主入口：检测所有角色的可触发事件

        Args:
            player: 玩家状态
            era: 时代背景
            max_events: 最多返回的事件数

        Returns:
            触发事件的字典列表
        """
        all_triggered: List[TriggeredEvent] = []

        # 获取主角性别和性倾向
        char_settings = player.character_settings or {}
        player_gender = char_settings.get("gender", {}).get("gender", "male")
        # 主角性倾向可以从设置中获取，如果没有则默认
        player_orientation = char_settings.get("sexual_orientation", "heterosexual")

        self.player_gender = player_gender
        self.player_orientation = player_orientation

        # 获取时代
        era_info = char_settings.get("era", {})
        era_name = era_info.get("era", era)

        # 遍历所有角色检测事件
        for char_data in player.characters.values():
            from src.game.state import CharacterState

            # char_data 可能是 CharacterState 对象或 dict
            if isinstance(char_data, CharacterState):
                character = char_data
            elif isinstance(char_data, dict):
                character = CharacterState(**char_data)
            else:
                continue

            # 检查各类事件
            all_triggered.extend(self.check_romance_events(character, player, era_name))
            all_triggered.extend(
                self.check_friendship_events(character, player, era_name)
            )
            all_triggered.extend(
                self.check_negative_events(character, player, era_name)
            )
            all_triggered.extend(self.check_special_events(character, player, era_name))

        # 按优先级排序
        all_triggered.sort(key=lambda e: e.priority, reverse=True)

        # 限制返回数量
        result = all_triggered[:max_events]

        logger.info(
            f"Detected {len(all_triggered)} events, returning top {len(result)}"
        )

        return [e.to_dict() for e in result]

    def mark_event_triggered(
        self, player: "PlayerState", character_name: str, event_type: str
    ) -> bool:
        """
        标记事件已触发

        Args:
            player: 玩家状态
            character_name: 角色名
            event_type: 事件类型

        Returns:
            是否成功标记
        """
        if character_name not in player.characters:
            return False

        char_data = player.characters[character_name]

        # char_data 可能是 CharacterState 对象或 dict
        from src.game.state import CharacterState

        if isinstance(char_data, CharacterState):
            if event_type not in char_data.triggered_events:
                char_data.triggered_events.append(event_type)
        elif isinstance(char_data, dict):
            if "triggered_events" not in char_data:
                char_data["triggered_events"] = []
            if event_type not in char_data["triggered_events"]:
                char_data["triggered_events"].append(event_type)
            player.characters[character_name] = char_data
        else:
            return False

        # 处理状态变更
        self._apply_event_state_changes(player, character_name, event_type)

        return True

    def _apply_event_state_changes(
        self, player: "PlayerState", character_name: str, event_type: str
    ) -> None:
        """
        应用事件带来的状态变更

        Args:
            player: 玩家状态
            character_name: 角色名
            event_type: 事件类型
        """
        if character_name not in player.characters:
            return

        char_data = player.characters[character_name]

        # char_data 可能是 CharacterState 对象或 dict
        from src.game.state import CharacterState

        # 恒爱萌芽 -> 改变感情状态
        if event_type == "romance_spark":
            if isinstance(char_data, CharacterState):
                char_data.relationship_status = "dating"
                char_data.romantic_interest = "player"
            else:
                char_data["relationship_status"] = "dating"
                char_data["romantic_interest"] = "player"

        # 求婚 -> 改变感情状态
        elif event_type == "marriage_proposal":
            if isinstance(char_data, CharacterState):
                char_data.relationship_status = "married"
            else:
                char_data["relationship_status"] = "married"

        # 分手 -> 改变感情状态
        elif event_type == "breakup":
            if isinstance(char_data, CharacterState):
                char_data.relationship_status = "single"
                char_data.romantic_interest = ""
            else:
                char_data["relationship_status"] = "single"
                char_data["romantic_interest"] = ""

        # 私奔 -> 改变感情状态，移除外部阻力
        elif event_type == "elopement":
            if isinstance(char_data, CharacterState):
                char_data.relationship_status = "married"
                char_data.has_external_obstacle = False
            else:
                char_data["relationship_status"] = "married"
                char_data["has_external_obstacle"] = False

        if not isinstance(char_data, CharacterState):
            player.characters[character_name] = char_data

    def generate_event_context(
        self, events: List[Dict[str, Any]], era: str, language: str = "zh"
    ) -> str:
        """
        生成事件上下文供AI使用

        Args:
            events: 事件列表
            era: 时代背景
            language: 语言

        Returns:
            事件上下文字符串
        """
        if not events:
            return ""

        lines = ["【本轮触发的重要关系事件】"]

        for event in events:
            lines.append(f"- {event['character_name']}: {event['era_name']}")
            lines.append(f"  {event['description']}")

        lines.append("")
        lines.append("请将以上事件自然地融入本轮故事中，使其感觉是故事发展的自然结果。")

        return "\n".join(lines)
