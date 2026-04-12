"""约束注册中心 - 定义约束优先级、类型枚举和注册表。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple


class Priority(Enum):
    """约束优先级，数值越小越关键。"""

    CRITICAL = 1  # 违反即判定失败，必须重试
    HIGH = 2  # 严重问题，尽量重试
    MEDIUM = 3  # 记录警告，不自动重试
    LOW = 4  # 仅记录统计


class ConstraintType(Enum):
    """所有约束类型枚举。"""

    # CRITICAL 级别
    AVAILABLE_PEOPLE = "available_people"  # 人物必须来自可用列表
    ESTABLISHED_FACTS = "established_facts"  # 不可与已建立事实矛盾
    OVERDUE_STORYLINES = "overdue_storylines"  # 过期剧情线必须推进
    WORLD_MODEL_POSITION = "world_model_position"  # 角色位置约束
    WORLD_MODEL_COMMITMENT = "world_model_commitment"  # 承诺/协议约束
    NO_FABRICATION = "no_fabrication"  # 禁止编造过往事件
    THIRD_PERSON_NARRATION = "third_person"  # 第三人称叙事
    DECISION_POINT_ENDING = "decision_point_ending"  # 结尾有决策点
    NO_META_NARRATION = "no_meta_narration"  # 禁止跳脱叙事

    # HIGH 级别
    HIGH_STORYLINES = "high_storylines"  # 高重要性剧情线
    SCENE_CONTINUITY = "scene_continuity"  # 场景连贯性
    CHARACTER_CONSISTENCY = "character_consistency"  # 角色性格一致性

    # MEDIUM 级别
    CHARACTER_HABITS = "character_habits"  # 人物习惯
    FORESHADOWING = "foreshadowing"  # 伏笔回响
    MEDIUM_STORYLINES = "medium_storylines"  # 中重要性剧情线
    LOGIC_CONSTRAINTS = "logic_constraints"  # 时间逻辑一致性

    # 硬性逻辑验证
    TEMPORAL_CONSISTENCY = "temporal_consistency"  # 时间一致性
    COMMITMENT_FULFILLMENT = "commitment_fulfillment"  # 承诺履行
    CHARACTER_STATE_CONTINUITY = "character_state_continuity"  # 角色状态连续性
    ITEM_CONTINUITY = "item_continuity"  # 物品连续性
    SPATIAL_MOVEMENT = "spatial_movement"  # 空间位移
    NPC_ATTRIBUTE_STABILITY = "npc_attribute_stability"  # NPC属性固化
    INFORMATION_BARRIER = "information_barrier"  # 信息屏障
    CAUSE_EFFECT_CONSISTENCY = "cause_effect_consistency"  # 因果后果

    # LOW 级别
    ANTI_REPETITION = "anti_repetition"  # 反重复
    VECTOR_CONTEXT = "vector_context"  # 历史上下文参考

    # 风格验证（新增）
    STYLE_STRUCTURE = "style_structure"  # 结构合规
    STYLE_PACING = "style_pacing"  # 节奏规则合规
    STYLE_LANGUAGE = "style_language"  # 语言风格合规
    STYLE_TECHNIQUE = "style_technique"  # 核心技法合规


@dataclass
class ConstraintDefinition:
    """单个约束的完整定义。"""

    type: ConstraintType
    priority: Priority
    description: str  # 中文描述
    validator: Callable[[str, dict], Tuple[bool, str, dict]]
    inject_in_prompt: bool = True  # 是否注入到 prompt 中
    prompt_marker: str = ""  # prompt 中的标记文本，用于 preflight 检查
    fallback_content: Optional[str] = None  # 当上下文缺失时的降级内容
    include_in_scoring: bool = True  # 是否参与评分
    weight: float = 1.0  # 评分权重（建议值：CRITICAL=3.0, HIGH=2.0, MEDIUM=1.0, LOW=0.5）


class ConstraintRegistry:
    """约束注册中心，管理所有约束定义。"""

    def __init__(self) -> None:
        self._constraints: Dict[ConstraintType, ConstraintDefinition] = {}

    def register(self, defn: ConstraintDefinition) -> None:
        """注册一个约束定义。"""
        self._constraints[defn.type] = defn

    def get(self, ctype: ConstraintType) -> Optional[ConstraintDefinition]:
        """按类型获取单个约束定义。"""
        return self._constraints.get(ctype)

    def get_critical_constraints(self) -> List[ConstraintDefinition]:
        """获取所有 CRITICAL 级别约束。"""
        return [c for c in self._constraints.values() if c.priority == Priority.CRITICAL]

    def get_by_priority(self, priority: Priority) -> List[ConstraintDefinition]:
        """按优先级筛选约束。"""
        return [c for c in self._constraints.values() if c.priority == priority]

    def get_all_for_validation(self) -> List[ConstraintDefinition]:
        """返回所有启用验证的约束，按优先级排序（CRITICAL 在前）。"""
        active = [c for c in self._constraints.values() if c.include_in_scoring]
        return sorted(active, key=lambda c: c.priority.value)

    def get_all(self) -> List[ConstraintDefinition]:
        """返回所有已注册的约束。"""
        return list(self._constraints.values())

    @property
    def count(self) -> int:
        """已注册约束数量。"""
        return len(self._constraints)
