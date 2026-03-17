"""NPC角色属性系统。

此模块定义了CharacterState类，用于管理NPC角色的丰富属性系统。
每个角色都有独立的属性，部分属性与主角关联。
"""

import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CharacterState(BaseModel):
    """
    NPC角色的丰富属性系统。
    每个角色都有独立的属性，部分属性与主角关联。
    """

    # ===== 基础信息 =====
    name: str = Field(..., description="角色姓名")
    role: str = Field(default="", description="角色定位（室友/同事/导师等）")
    relationship_desc: str = Field(default="", description="与主角的关系描述")
    age: int = Field(default=25, ge=0, le=120, description="角色年龄")
    gender: str = Field(default="", description="性别")
    occupation: str = Field(default="", description="职业")

    # ===== 性格系统 =====
    personality_traits: List[str] = Field(
        default_factory=list, description="性格标签：['外向', '理性', '热心'] 等"
    )
    temperament: str = Field(
        default="balanced",
        description="气质类型：sanguine(多血质)/choleric(胆汁质)/melancholic(抑郁质)/phlegmatic(粘液质)/balanced(均衡)",
    )

    # ===== 动态状态（会随事件变化）=====
    mood: int = Field(default=60, ge=0, le=100, description="当前情绪状态")
    mood_stability: int = Field(
        default=70, ge=0, le=100, description="情绪稳定性，影响情绪波动幅度"
    )

    # ===== 社会属性 =====
    social_status: str = Field(
        default="ordinary", description="社会地位：student/ordinary/professional/leader/elite"
    )
    influence: int = Field(default=30, ge=0, le=100, description="影响力/社会资源")

    # ===== 能力属性 =====
    competence: int = Field(default=50, ge=0, le=100, description="能力水平")
    specialty: List[str] = Field(default_factory=list, description="专长领域")

    # ===== 隐藏属性（不暴露给用户）=====
    sexual_orientation: str = Field(
        default="heterosexual", description="性倾向: heterosexual/homosexual/bisexual/asexual"
    )
    relationship_status: str = Field(
        default="single", description="感情状态: single/dating/engaged/married/divorced"
    )
    romantic_interest: str = Field(
        default="", description="暗恋/喜欢的对象名字（可以是主角或其他NPC）"
    )
    has_external_obstacle: bool = Field(
        default=False, description="是否有外部阻力（如家族反对），用于私奔事件"
    )
    peak_affinity: int = Field(
        default=50, ge=0, le=100, description="历史最高亲密度，用于判断反目成仇"
    )

    # ===== 与主角关联的属性 =====
    affinity: int = Field(default=50, ge=0, le=100, description="亲密度（与主角双向共享）")
    trust: int = Field(default=50, ge=0, le=100, description="对主角的信任度")
    respect: int = Field(default=50, ge=0, le=100, description="对主角的尊重度")

    # ===== 互动记录 =====
    interaction_count: int = Field(default=0, ge=0, description="互动次数")
    last_interaction_week: int = Field(default=-1, description="最近互动的周数，-1表示从未互动")
    relationship_history: str = Field(default="", description="关系发展简述")

    # ===== 特殊事件触发阈值 =====
    event_triggers: Dict[str, int] = Field(
        default_factory=lambda: {
            # 旧事件（保持兼容）
            "deep_friendship": 80,  # 深度友谊事件
            "conflict": 20,  # 冲突事件
            "help_request": 60,  # 请求帮助
            "secret_sharing": 75,  # 分享秘密 # noqa: B105
            "betrayal_risk": 15,  # 背叛风险
            # 浪漫关系事件
            "romance_spark": 75,  # 恋爱萌芽
            "marriage_proposal": 85,  # 求婚
            "breakup": 25,  # 分手
            "elopement": 90,  # 私奔（需要外部阻力）
            # 友谊信任事件
            "sworn_siblings": 85,  # 结拜
            "soulmate": 80,  # 知己
            "business_partner": 70,  # 创业合伙
            "entrust": 90,  # 托付
            # 负面关系事件
            "become_enemy": 15,  # 反目成仇
            "betrayal": 20,  # 背叛
            "severance": 10,  # 决裂
            "sabotage": 25,  # 暗中陷害
            # 特殊关系事件
            "apprenticeship": 75,  # 师徒
            "patron": 70,  # 贵人提携
            "childbirth": 90,  # 生育子女
        },
        description="特殊事件的触发阈值",
    )

    # ===== 已触发事件记录（避免重复触发）=====
    triggered_events: List[str] = Field(
        default_factory=list, description="已经触发过的事件类型列表"
    )

    def update_mood(self, change: int) -> None:
        """
        更新角色情绪，受情绪稳定性影响。

        Args:
            change: 情绪变化值
        """
        # 情绪稳定性影响变化幅度：稳定性越高，变化越小
        stability_factor = self.mood_stability / 100
        adjusted_change = int(change * (1 - stability_factor * 0.5))
        self.mood = max(0, min(100, self.mood + adjusted_change))

    def update_relationship(
        self, affinity_change: int = 0, trust_change: int = 0, respect_change: int = 0
    ) -> None:
        """
        更新与主角的关系属性。

        Args:
            affinity_change: 亲密度变化
            trust_change: 信任度变化
            respect_change: 尊重度变化
        """
        if affinity_change:
            self.affinity = max(0, min(100, self.affinity + affinity_change))
            # 更新历史最高亲密度
            if self.affinity > self.peak_affinity:
                self.peak_affinity = self.affinity
        if trust_change:
            self.trust = max(0, min(100, self.trust + trust_change))
        if respect_change:
            self.respect = max(0, min(100, self.respect + respect_change))

    def record_interaction(self, week: int, summary: str = "") -> None:
        """
        记录与主角的互动。

        Args:
            week: 当前周数
            summary: 互动简述
        """
        self.interaction_count += 1
        self.last_interaction_week = week
        if summary:
            if self.relationship_history:
                self.relationship_history += f" | 第{week}周: {summary}"
            else:
                self.relationship_history = f"第{week}周: {summary}"

    def check_event_trigger(self, event_type: str) -> bool:
        """Check if special event should trigger. Delegates to PlayerService."""
        from src.game.player_service import PlayerService

        return PlayerService.check_event_trigger(self, event_type)

    def get_interaction_style(self) -> str:
        """
        根据性格特点返回互动风格描述。

        Returns:
            互动风格描述
        """
        style_parts = []

        # 根据气质类型
        temperament_styles = {
            "sanguine": "热情活泼",
            "choleric": "直接果断",
            "melancholic": "深思熟虑",
            "phlegmatic": "温和稳重",
            "balanced": "平和理性",
        }
        style_parts.append(temperament_styles.get(self.temperament, "平和"))

        # 根据当前情绪
        if self.mood >= 80:
            style_parts.append("心情愉悦")
        elif self.mood <= 30:
            style_parts.append("情绪低落")

        # 根据与主角关系
        if self.affinity >= 80:
            style_parts.append("亲切友好")
        elif self.affinity <= 30:
            style_parts.append("态度冷淡")

        return "，".join(style_parts)

    def to_context_string(self) -> str:
        """
        生成用于AI上下文的角色描述。

        Returns:
            角色描述字符串
        """
        traits_str = "、".join(self.personality_traits) if self.personality_traits else "普通"
        specialty_str = "、".join(self.specialty) if self.specialty else "无特殊专长"

        return f"""{self.name}（{self.role}）：
- 年龄：{self.age}岁，职业：{self.occupation or '未知'}
- 性格：{traits_str}
- 当前情绪：{self.mood}/100，互动风格：{self.get_interaction_style()}
- 与主角亲密度：{self.affinity}/100，信任度：{self.trust}/100
- 专长：{specialty_str}
- 社会地位：{self.social_status}，影响力：{self.influence}/100
- 关系简述：{self.relationship_desc}"""

    @classmethod
    def from_simple_dict(cls, data: Dict[str, Any]) -> "CharacterState":
        """
        从简单的角色字典创建（兼容旧数据）。

        Args:
            data: 简单格式的角色数据 {name, role, relationship}

        Returns:
            CharacterState实例
        """
        return cls(
            name=data.get("name", "未知"),
            role=data.get("role", ""),
            relationship_desc=data.get("relationship", ""),
            # 其他属性使用默认值
        )
