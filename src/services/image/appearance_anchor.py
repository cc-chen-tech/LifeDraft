"""人物外貌特征锚点 - 文本层面的角色一致性机制.

通过结构化的外貌描述（从文本生成），确保同一角色在不同场景下的视觉一致性。
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class CharacterAppearanceAnchor:
    """人物外貌特征锚点 - 结构化的外貌描述.

    在生成人物图片时创建，后续场景生成时引用，确保视觉一致性。
    所有字段都是文本描述，不涉及具体图片。
    """

    # 基础信息
    name: str  # 角色名称
    era: str = "现代"  # 时代背景

    # 面部特征（最关键）
    face_shape: str = ""  # 脸型：圆脸、瓜子脸、方脸、鹅蛋脸等
    facial_features: str = ""  # 五官特征：单眼皮/双眼皮、鼻梁高低、嘴唇厚薄等
    expression: str = ""  # 常设表情：温和、严肃、活泼、忧郁等
    skin_tone: str = ""  # 肤色：白皙、小麦色、黝黑等

    # 发型特征
    hair_style: str = ""  # 发型：黑色中长发、短发、卷发、马尾等
    hair_color: str = ""  # 发色：乌黑、棕色、银白等
    hair_details: str = ""  # 发型细节：刘海向左分、发梢微卷等

    # 体型与体态
    body_type: str = ""  # 体型：中等身材、高挑、娇小、健硕等
    height_impression: str = ""  # 身高印象：修长、匀称、敦实等
    posture: str = ""  # 体态特征：挺拔、略微驼背、放松等

    # 标志性特征（用于识别）
    distinctive_marks: List[str] = field(default_factory=list)  # 独特标记

    # 服装风格
    typical_outfit: str = ""  # 典型穿着：深蓝色牛仔外套配白T恤
    clothing_style: str = ""  # 服装风格：休闲、正式、复古、潮流等
    accessories: List[str] = field(default_factory=list)  # 配饰：手表、眼镜等

    # 气质与神韵
    aura: str = ""  # 整体气质：书卷气、干练、随性等
    age_appearance: str = ""  # 年龄感：看起来比实际年龄年轻/成熟等

    # 光线与表现（帮助图片生成）
    lighting_preference: str = ""  # 适合的光线：柔和侧光、顶光等
    angle_preference: str = ""  # 适合的角度：正侧面、45度等

    # 生成元信息
    generated_from: str = ""  # 基于什么生成的（原始描述）
    version: int = 1  # 锚点版本

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterAppearanceAnchor":
        """从字典创建."""
        return cls(**data)

    def build_prompt_segment(self) -> str:
        """构建用于图片生成的描述片段.

        Returns:
            结构化的外貌描述文本，可直接插入图片生成提示词
        """
        parts = []

        # 面部（最重要）
        if self.face_shape or self.facial_features:
            face_desc = f"脸型{self.face_shape}，{self.facial_features}".strip("，")
            parts.append(f"面部特征：{face_desc}")

        if self.expression:
            parts.append(f"常设表情：{self.expression}")

        if self.skin_tone:
            parts.append(f"肤色：{self.skin_tone}")

        # 发型
        hair_parts = []
        if self.hair_color:
            hair_parts.append(self.hair_color)
        if self.hair_style:
            hair_parts.append(self.hair_style)
        if self.hair_details:
            hair_parts.append(self.hair_details)
        if hair_parts:
            parts.append(f"发型：{''.join(hair_parts)}")

        # 体型
        body_parts = []
        if self.height_impression:
            body_parts.append(self.height_impression)
        if self.body_type:
            body_parts.append(self.body_type)
        if body_parts:
            parts.append(f"体型：{''.join(body_parts)}")

        if self.posture:
            parts.append(f"体态：{self.posture}")

        # 标志性特征
        if self.distinctive_marks:
            marks = "、".join(self.distinctive_marks)
            parts.append(f"标志性特征：{marks}")

        # 服装（场景生成时可能需要调整）
        if self.typical_outfit:
            parts.append(f"典型服装：{self.typical_outfit}")

        # 配饰
        if self.accessories:
            acc = "、".join(self.accessories)
            parts.append(f"配饰：{acc}")

        # 气质
        if self.aura:
            parts.append(f"整体气质：{self.aura}")

        return "；".join(parts) if parts else ""

    def build_scene_prompt(
        self,
        scene_context: str = "",
        pose_hint: str = "",
        outfit_override: str = "",
    ) -> str:
        """构建用于场景生成的完整提示词.

        Args:
            scene_context: 场景上下文
            pose_hint: 姿势提示
            outfit_override: 服装覆盖（如场景需要换装）

        Returns:
            完整的场景生成提示词
        """
        parts = [f"人物：{self.name}"]

        # 外貌（必须严格保持）
        appearance = self.build_prompt_segment()
        if appearance:
            parts.append(f"外貌特征（必须严格一致）：{appearance}")

        # 服装（可覆盖）
        outfit = outfit_override or self.typical_outfit
        if outfit:
            parts.append(f"穿着：{outfit}")

        # 姿势
        if pose_hint:
            parts.append(f"姿势：{pose_hint}")
        elif self.posture:
            parts.append(f"姿势：{self.posture}")

        # 表情
        if self.expression:
            parts.append(f"表情：{self.expression}")

        # 场景
        if scene_context:
            parts.append(f"场景：{scene_context}")

        # 光线偏好
        if self.lighting_preference:
            parts.append(f"光线：{self.lighting_preference}")

        return "。".join(parts)

    def validate(self) -> List[str]:
        """验证锚点完整性.

        Returns:
            缺失的重要字段列表
        """
        missing = []
        critical_fields = [
            ("face_shape", "脸型"),
            ("facial_features", "五官特征"),
            ("hair_style", "发型"),
            ("body_type", "体型"),
        ]
        for field_name, field_desc in critical_fields:
            if not getattr(self, field_name):
                missing.append(field_desc)
        return missing


def merge_anchors(
    base: CharacterAppearanceAnchor, override: Dict[str, Any]
) -> CharacterAppearanceAnchor:
    """合并锚点，用于更新时保留未修改的字段.

    Args:
        base: 基础锚点
        override: 覆盖字段

    Returns:
        新的合并后的锚点
    """
    data = base.to_dict()
    data.update(override)
    data["version"] = base.version + 1
    return CharacterAppearanceAnchor.from_dict(data)
