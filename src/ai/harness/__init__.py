"""Harness 约束系统 - 结构化约束定义、注册与验证。

提供统一的约束注册中心和验证函数，用于在故事生成前后
进行约束检查，提升生成质量。
"""

from .constraint_registry import (
    ConstraintDefinition,
    ConstraintRegistry,
    ConstraintType,
    Priority,
)
from .preflight_checker import PreflightChecker, PreflightResult
from .diagnostics import ConstraintViolationDiagnostic, DiagnosticReport
from .retry_controller import RetryController
from .validation_pipeline import (
    ConstraintCheckResult,
    ValidationPipeline,
    ValidationResult,
)
from .validators import (
    validate_anti_repetition,
    validate_available_people,
    validate_character_consistency,
    validate_character_habits,
    validate_decision_point_ending,
    validate_established_facts,
    validate_foreshadowing,
    validate_high_storylines,
    validate_logic_constraints,
    validate_medium_storylines,
    validate_no_fabrication,
    validate_no_meta_narration,
    validate_overdue_storylines,
    validate_scene_continuity,
    validate_third_person,
    validate_vector_context,
)
from .temporal_validator import validate_temporal_consistency
from .commitment_validator import validate_commitment_fulfillment
from .character_state_validator import validate_character_state_continuity
from .item_continuity_validator import validate_item_continuity
from .spatial_validator import validate_spatial_movement
from .npc_attribute_validator import validate_npc_attribute_stability
from .info_barrier_validator import validate_information_barrier
from .cause_effect_validator import validate_cause_effect_consistency
from src.ai.narrative.style_validator import StyleAwareValidator
from src.ai.harness.narrative_validators import (
    validate_three_act_structure,
    validate_pacing_variety,
    validate_arc_hint_compliance,
    validate_world_event_integration,
    validate_conflict_directive_compliance,
)

__all__ = [
    # 核心类
    "Priority",
    "ConstraintType",
    "ConstraintDefinition",
    "ConstraintRegistry",
    # 诊断器与重试控制器
    "ConstraintViolationDiagnostic",
    "DiagnosticReport",
    "RetryController",
    # 预检查器与验证管道
    "PreflightChecker",
    "PreflightResult",
    "ValidationPipeline",
    "ValidationResult",
    "ConstraintCheckResult",
    # 验证函数
    "validate_available_people",
    "validate_third_person",
    "validate_no_meta_narration",
    "validate_decision_point_ending",
    "validate_overdue_storylines",
    "validate_scene_continuity",
    "validate_no_fabrication",
    "validate_established_facts",
    "validate_high_storylines",
    "validate_character_consistency",
    "validate_character_habits",
    "validate_foreshadowing",
    "validate_medium_storylines",
    "validate_logic_constraints",
    "validate_anti_repetition",
    "validate_vector_context",
    # 风格验证器
    "StyleAwareValidator",
    # 硬性逻辑验证函数
    "validate_temporal_consistency",
    "validate_commitment_fulfillment",
    "validate_character_state_continuity",
    "validate_item_continuity",
    "validate_spatial_movement",
    "validate_npc_attribute_stability",
    "validate_information_barrier",
    "validate_cause_effect_consistency",
    # 默认注册表
    "default_registry",
]


# ============================================================
# 创建默认注册表并注册所有约束定义
# ============================================================

default_registry = ConstraintRegistry()

# --- CRITICAL 级别（weight=3.0）---

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.AVAILABLE_PEOPLE,
        priority=Priority.CRITICAL,
        description="人物必须来自可用列表，严禁使用名单外的人物",
        validator=validate_available_people,
        prompt_marker="[MUST] **可用人物列表",
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.ESTABLISHED_FACTS,
        priority=Priority.CRITICAL,
        description="不可与已建立的世界事实矛盾",
        validator=validate_established_facts,
        prompt_marker="[MUST] 【已建立的世界事实",
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.OVERDUE_STORYLINES,
        priority=Priority.CRITICAL,
        description="过期剧情线必须在本轮推进或解决",
        validator=validate_overdue_storylines,
        prompt_marker="[MUST] 🚨",
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.WORLD_MODEL_POSITION,
        priority=Priority.CRITICAL,
        description="角色必须在其当前位置出现，不可凭空传送",
        validator=validate_established_facts,  # 复用，完整版本由世界模型提供
        prompt_marker="[MUST]",
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.WORLD_MODEL_COMMITMENT,
        priority=Priority.CRITICAL,
        description="已做出的承诺/协议不可被忽视",
        validator=validate_established_facts,  # 复用，完整版本由世界模型提供
        prompt_marker="[MUST]",
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.NO_FABRICATION,
        priority=Priority.CRITICAL,
        description="禁止编造过往事件，所有回忆必须有据可查",
        validator=validate_no_fabrication,
        prompt_marker="[MUST] **禁止编造过往事件**",
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.THIRD_PERSON_NARRATION,
        priority=Priority.CRITICAL,
        description="必须使用第三人称叙事",
        validator=validate_third_person,
        prompt_marker="[MUST] **人称要求**",
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.DECISION_POINT_ENDING,
        priority=Priority.CRITICAL,
        description="故事结尾必须停在一个具体的决策点",
        validator=validate_decision_point_ending,
        prompt_marker="[MUST] **故事结尾要求**",
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.NO_META_NARRATION,
        priority=Priority.CRITICAL,
        description="禁止跳脱叙事，不可打破第四面墙",
        validator=validate_no_meta_narration,
        prompt_marker="[MUST] **禁止跳脱叙事**",
        weight=3.0,
    )
)

# --- HIGH 级别（weight=2.0）---

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.HIGH_STORYLINES,
        priority=Priority.HIGH,
        description="高重要性剧情线至少涉及一条",
        validator=validate_high_storylines,
        prompt_marker="[SHOULD] **必须在故事中涉及",
        weight=2.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.SCENE_CONTINUITY,
        priority=Priority.HIGH,
        description="场景必须与上一轮结尾地点连贯，无缝衔接或有合理过渡",
        validator=validate_scene_continuity,
        prompt_marker="[REF] 【上一轮故事背景",
        weight=2.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.CHARACTER_CONSISTENCY,
        priority=Priority.HIGH,
        description="角色性格与行为必须与已建立画像一致",
        validator=validate_character_consistency,
        weight=2.0,
    )
)

# --- MEDIUM 级别（weight=1.0）---

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.CHARACTER_HABITS,
        priority=Priority.MEDIUM,
        description="人物习惯应在故事中自然体现",
        validator=validate_character_habits,
        prompt_marker="[SHOULD] 【人物习惯记录",
        weight=1.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.FORESHADOWING,
        priority=Priority.MEDIUM,
        description="已激活的伏笔种子应在故事中有回响",
        validator=validate_foreshadowing,
        prompt_marker="[SHOULD] 【伏笔回响",
        weight=1.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.MEDIUM_STORYLINES,
        priority=Priority.MEDIUM,
        description="中重要性剧情线可选择性延续",
        validator=validate_medium_storylines,
        prompt_marker="[REF] 可选择性延续",
        weight=1.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.LOGIC_CONSTRAINTS,
        priority=Priority.MEDIUM,
        description="时间与逻辑一致性，季节天气等不矛盾",
        validator=validate_logic_constraints,
        prompt_marker="[SHOULD] 11. **时间与逻辑一致性",
        weight=1.0,
    )
)

# --- LOW 级别（weight=0.5）---

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.ANTI_REPETITION,
        priority=Priority.LOW,
        description="避免故事内部出现重复段落或句式",
        validator=validate_anti_repetition,
        inject_in_prompt=False,
        weight=0.5,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.VECTOR_CONTEXT,
        priority=Priority.LOW,
        description="历史上下文向量检索参考",
        validator=validate_vector_context,
        inject_in_prompt=False,
        include_in_scoring=False,
        weight=0.5,
    )
)

# --- 风格验证约束（动态，基于 StyleManifest）---

# --- 硬性逻辑验证约束 ---

# CRITICAL 级别（weight=3.0）
default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.TEMPORAL_CONSISTENCY,
        priority=Priority.CRITICAL,
        description="时间一致性：季节、年龄、时间引用与游戏状态匹配",
        validator=validate_temporal_consistency,
        inject_in_prompt=False,
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.COMMITMENT_FULFILLMENT,
        priority=Priority.CRITICAL,
        description="承诺履行：到期承诺必须被处理，行为不可与承诺矛盾",
        validator=validate_commitment_fulfillment,
        inject_in_prompt=False,
        weight=3.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.CHARACTER_STATE_CONTINUITY,
        priority=Priority.CRITICAL,
        description="角色状态连续性：死亡/重伤/囚禁角色行为受限",
        validator=validate_character_state_continuity,
        inject_in_prompt=False,
        weight=3.0,
    )
)

# HIGH 级别（weight=2.0-2.5）
default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.ITEM_CONTINUITY,
        priority=Priority.HIGH,
        description="物品连续性：使用的物品必须在持有列表中",
        validator=validate_item_continuity,
        inject_in_prompt=False,
        weight=2.5,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.SPATIAL_MOVEMENT,
        priority=Priority.HIGH,
        description="空间位移：角色不可在一轮内跨越远距离",
        validator=validate_spatial_movement,
        inject_in_prompt=False,
        weight=2.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.NPC_ATTRIBUTE_STABILITY,
        priority=Priority.HIGH,
        description="NPC属性固化：NPC描写不可与存储属性矛盾",
        validator=validate_npc_attribute_stability,
        inject_in_prompt=False,
        weight=2.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.INFORMATION_BARRIER,
        priority=Priority.HIGH,
        description="信息屏障：角色不应知道超出其信息范围的事实",
        validator=validate_information_barrier,
        inject_in_prompt=False,
        weight=2.0,
    )
)

# MEDIUM 级别（weight=1.5）
default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.CAUSE_EFFECT_CONSISTENCY,
        priority=Priority.MEDIUM,
        description="因果后果：重大决策的后果应在后续故事中体现",
        validator=validate_cause_effect_consistency,
        inject_in_prompt=False,
        weight=1.5,
    )
)

# --- 风格验证约束（动态，基于 StyleManifest）---

_style_validator = StyleAwareValidator()  # 无风格时所有验证直接通过

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.STYLE_STRUCTURE,
        priority=Priority.HIGH,
        description="风格结构合规（章回/英雄之旅/框架叙事等）",
        validator=_style_validator.validate_style_structure,
        inject_in_prompt=False,
        weight=2.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.STYLE_PACING,
        priority=Priority.MEDIUM,
        description="风格节奏规则合规（章节开头/结尾/hook等）",
        validator=_style_validator.validate_style_pacing,
        inject_in_prompt=False,
        weight=1.5,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.STYLE_LANGUAGE,
        priority=Priority.MEDIUM,
        description="风格语言合规（散文风格/对话/修辞/情感表达）",
        validator=_style_validator.validate_style_language,
        inject_in_prompt=False,
        weight=1.0,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.STYLE_TECHNIQUE,
        priority=Priority.MEDIUM,
        description="风格核心技法合规（叙事技法/修辞手法/叙事模式）",
        validator=_style_validator.validate_style_technique,
        inject_in_prompt=False,
        weight=1.0,
    )
)

# --- 第二层：中观章节验证 ---

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.THREE_ACT_STRUCTURE,
        priority=Priority.HIGH,
        description="三幕结构完整性：故事应有铺垫、发展/转折、高潮/收束",
        validator=validate_three_act_structure,
        inject_in_prompt=False,
        weight=1.5,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.PACING_VARIETY,
        priority=Priority.HIGH,
        description="节奏多样性：节奏干预后故事应打破平坦模式",
        validator=validate_pacing_variety,
        inject_in_prompt=False,
        weight=1.5,
    )
)

# --- 第三层：宏观结构验证 ---

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.ARC_HINT_COMPLIANCE,
        priority=Priority.HIGH,
        description="人物弧光遵从：故事应体现请求的弧光阶段特征",
        validator=validate_arc_hint_compliance,
        inject_in_prompt=False,
        weight=1.5,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.WORLD_EVENT_INTEGRATION,
        priority=Priority.MEDIUM,
        description="世界事件融入：故事应融入注入的世界事件元素",
        validator=validate_world_event_integration,
        inject_in_prompt=False,
        weight=1.5,
    )
)

default_registry.register(
    ConstraintDefinition(
        type=ConstraintType.CONFLICT_DIRECTIVE_COMPLIANCE,
        priority=Priority.MEDIUM,
        description="冲突指令遵从：故事应体现请求的冲突层级",
        validator=validate_conflict_directive_compliance,
        inject_in_prompt=False,
        weight=1.5,
    )
)
