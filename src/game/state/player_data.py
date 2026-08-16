"""玩家数据模型。

此模块定义了 PlayerState 的纯数据属性部分，作为 Mixin 类供 PlayerState 继承。
包含所有 Pydantic 字段定义、验证器和序列化方法。
"""

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional

from pydantic import Field, field_validator

from config.settings import settings

# 在 TYPE_CHECKING 中声明 BaseModel 的方法
if TYPE_CHECKING:
    pass


def default_world_projection_state() -> Dict[str, Any]:
    """Return a fresh v1 projection layer for a player's derived world facts."""

    return {
        "version": 1,
        "projected_through_day_index": -1,
        "applied_through_day_index": -1,
        "pending_from_day_index": None,
        "oldest_pending_at": None,
        "applied_sources": [],
        "world": {
            "fact_updates": [],
            "foreshadowing_seeds": [],
            "habit_updates": [],
            "location_updates": [],
            "career_updates": [],
            "commitment_updates": [],
            "causal_updates": [],
        },
    }


def _sanitize_world_projection_state(value: Any) -> Dict[str, Any]:
    """Fill missing v1 keys while preserving all valid legacy projection data."""

    normalized = default_world_projection_state()
    if not isinstance(value, Mapping):
        return normalized

    normalized.update(deepcopy(dict(value)))
    world = value.get("world")
    if isinstance(world, Mapping):
        normalized_world = default_world_projection_state()["world"]
        normalized_world.update(deepcopy(dict(world)))
        normalized["world"] = normalized_world
    else:
        normalized["world"] = default_world_projection_state()["world"]
    if not isinstance(normalized.get("applied_sources"), list):
        normalized["applied_sources"] = []
    return normalized


class PlayerDataMixin:
    """玩家数据属性 Mixin。

    包含所有数据字段定义，需要与 BaseModel 一起使用。
    """

    # Player identity
    player_name: str = Field(default="", description="玩家名称")
    life_vision: str = Field(default="", description="人生愿景")

    # Core attributes (0-100 scale)
    energy: int = Field(default=settings.INITIAL_ENERGY, ge=0, le=100)
    mood: int = Field(default=settings.INITIAL_MOOD, ge=0, le=100)
    knowledge: int = Field(default=settings.INITIAL_KNOWLEDGE, ge=0, le=100)

    # Relationships: {name: affinity (0-100)} - 为了向后兼容保留
    relationships: Dict[str, int] = Field(default_factory=dict)

    # NPC角色状态系统: {name: CharacterState.model_dump()}
    characters: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # 重要物品状态系统: {item_name: ItemState.model_dump()}
    items: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # 重要地点/场景状态系统: {landmark_name: LandmarkState.model_dump()}
    landmarks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Time tracking
    age: int = Field(default=settings.STARTING_AGE, ge=0)  # No upper age limit
    week: int = Field(default=0, ge=0)

    # v2 authoritative daily timeline. ``start_date`` and ``day_index`` are
    # the only authorities; all other public fields are derived on load.
    timeline: Optional[Dict[str, Any]] = Field(default=None)
    timeline_version: Optional[int] = Field(default=None)
    day_history: list = Field(default_factory=list)
    next_age_day: int = Field(default=365, ge=1)

    # Decision history
    decision_history: list = Field(default_factory=list)

    # Character creation settings
    character_settings: Dict[str, Any] = Field(default_factory=dict)

    # Selected narrative style. This is part of player state because generation
    # can occur after a session is restored from a save.
    narrative_style_id: Optional[str] = Field(default=None)

    # Story history - stores each week's story/event description
    story_history: list = Field(default_factory=list)

    # Four-week summaries - generated every 4 weeks
    four_week_summaries: list = Field(default_factory=list)

    # Yearly summaries - generated every 48 weeks
    yearly_summaries: list = Field(default_factory=list)

    # Multi-round system - new fields
    current_round: int = Field(default=0, ge=0)  # Current round within week (0, 1, 2)
    rounds_per_week: int = Field(
        default=settings.ROUNDS_PER_WEEK, ge=1
    )  # Number of rounds per week

    # Round history - stores each round's compressed summary and decision
    # Structure: [{"week": 0, "round": 0, "summary": "100字总结", "choice": "选项文本", "effects": {...}}]
    round_history: list = Field(default_factory=list)

    # Derived, immutable prompt-compression snapshots. The canonical story
    # remains in round_history; these records only bound long-context prompts.
    long_context_snapshots: list = Field(default_factory=list)

    # Weekly summaries - generated at end of each week after all rounds
    # Structure: [{"week": 0, "summary": "周总结文本", "bonus_effects": {...}}]
    weekly_summaries: list = Field(default_factory=list)

    # Current event state - saves the event being displayed (not yet chosen)
    # This allows resuming exactly where the player left off
    # Structure: {"event_description": "...", "options": [{"text": "...", "effects": {...}}], "story_text": "..."}
    current_event_data: Optional[Dict[str, Any]] = Field(default=None)

    # Exact user-visible phase for states that are not represented by an
    # unchosen current_event_data object. This prevents save/load from treating
    # a committed result or weekly summary as permission to generate the next
    # round automatically.
    resume_view: Optional[Dict[str, Any]] = Field(default=None)

    # 未完结的重要剧情线
    # Structure: [{"description": "...", "created_week": 0, "importance": "high/medium",
    #              "status": "active/deferred", "related_characters": [], "last_mentioned_week": 0}]
    pending_storylines: list = Field(default_factory=list)

    # 已建立的世界事实（人物角色/地理位置/正在进行的事务等一致性信息）
    # Structure: [{"fact": "...", "subject": "主体名", "category": "location/role/situation",
    #              "established_week": 0}]
    established_facts: list = Field(default_factory=list)

    # 上一轮完整故事文本（event_description + story_continuation），用于强制续写
    last_round_full_story: str = Field(
        default="", description="上一轮的完整故事文本，供下一轮续写参考"
    )

    # 上一轮事件是否已完结
    last_event_concluded: bool = Field(
        default=True, description="上一轮事件是否已自然完结。False表示需要强制续写"
    )

    # 伏笔种子系统（草蛇灰线引擎）：存储可在未来故事中回响的伏笔元素
    # Structure: [{"description": "伏笔描述", "original_context": "原始场景简述",
    #              "planted_week": 0, "related_characters": [], "seed_type": "mystery",
    #              "maturity_weeks": 8, "activated": false, "activation_week": null,
    #              "obfuscation_level": 0.5,     # 隐蔽度 0-1（0=明显线索, 1=极度隐蔽）
    #              "narrative_weight": "minor",   # 叙事权重 minor/supporting/major
    #              "recycle_method": "revelation", # 回收方式 revelation/confirmation/ironic_twist/escalation/echo
    #              "related_storylines": []        # 关联的 pending_storylines 描述
    #             }]
    foreshadowing_seeds: list = Field(default_factory=list)

    # 人物习惯追踪系统：记录故事中角色展现出的行为习惯，支持随事件变化
    # Structure: [{"character": "角色名", "habit": "习惯描述",
    #              "category": "behavioral/speech/emotional/social/lifestyle",
    #              "established_week": 0, "last_seen_week": 0,
    #              "strength": "strong/moderate/emerging",
    #              "origin": "习惯来源简述"}]
    character_habits: list = Field(default_factory=list)

    # 世界模型结构化数据（地理位置/职业轨迹/承诺/因果链/身体状态）
    # 与 established_facts 共存，WorldModel 同时读取两者
    # Structure: {"character_locations": {name: LocationInfo.to_dict()},
    #             "career_records": {name: CareerInfo.to_dict()},
    #             "active_commitments": [Commitment.to_dict()],
    #             "causal_chains": [CausalChain.to_dict()],
    #             "physical_states": {name: PhysicalState.to_dict()}}
    world_model_data: Dict[str, Any] = Field(
        default_factory=lambda: {
            "character_locations": {},
            "career_records": {},
            "active_commitments": [],
            "causal_chains": [],
            "physical_states": {},
            "dynamic_facts": [],
            "character_profiles": {},
        }
    )

    # Materialized daily world facts are derived from accepted story revisions.
    # Legacy mixed world_model_data remains intact as a soft prompt hint.
    world_projection_state: Dict[str, Any] = Field(
        default_factory=default_world_projection_state
    )

    # P1-7 authoritative continuity ledger. Narrative prose is never the
    # authority for identity, chronology, committed events, health, or
    # relationships; every mutable entry carries its source event.
    continuity_ledger: Dict[str, Any] = Field(
        default_factory=lambda: {
            "version": 1,
            "immutable_identities": {},
            "timeline": [],
            "completed_events": {},
            "mutable_states": {"health": {}, "relationships": {}, "facts": {}},
            "corrections": [],
            "conflicts": [],
        }
    )

    # 伏笔系统生命周期指标（用于评估伏笔系统健康度）
    # Structure: {"total_planted": 0, "total_activated": 0, "total_expired": 0,
    #             "avg_recovery_distance": 0, "recovery_distances": []}
    foreshadowing_metrics: Dict[str, Any] = Field(
        default_factory=lambda: {
            "total_planted": 0,
            "total_activated": 0,
            "total_expired": 0,
            "avg_recovery_distance": 0.0,
            "recovery_distances": [],
        }
    )

    # 待引入人物队列：存储已生成但尚未在故事中自然引入的新人物
    # 人物生成后不立即添加到 key_people，而是等待合适的故事场景再引入
    # Structure: [{"character_data": {...完整的人物属性}, "created_week": 0,
    #              "introduction_context": "work/social/location_change/education/random",
    #              "priority": 0, "attempts": 0}]
    # - introduction_context: 建议的引入场景类型
    # - priority: 引入优先级（越高越优先）
    # - attempts: 尝试引入次数（超过阈值仍未引入则强制引入）
    pending_character_introductions: list = Field(default_factory=list)

    # ★ 预定事件系统：存储带有具体时间点的承诺事件
    # 当角色在故事中承诺在特定时间做某事时，系统会在此创建预定事件
    # 到达指定轮次时，这些事件会被强制触发
    # Structure: [ScheduledEvent.to_dict()] - 详见 src/game/scheduled_events.py
    scheduled_events: list = Field(default_factory=list)

    # ==================== 创意增强字段 ====================

    # 情感弧线历史：追踪每轮的情感变化
    # Structure: [{"week": 0, "round": 0, "valence": 0.5, "arousal": 0.5, "scene_type": "conflict"}]
    emotional_arc_history: list = Field(default_factory=list)

    # 新颖度评分：评估每周故事与历史故事的差异度
    # Structure: [{"week": 0, "score": 0.8, "similar_to_week": 3}]
    novelty_scores: list = Field(default_factory=list)

    # 玩家偏好：通过选择行为学习到的偏好权重
    # Structure: {"suspense": 0.7, "romance": 0.3, "conflict": 0.5, ...}
    player_preferences: Dict[str, float] = Field(default_factory=dict)

    # ==================== 史诗叙事字段 ====================

    # 角色弧光状态：追踪每个角色的成长阶段
    # Structure: {name: {"phase": "rising", "flaw": "傲慢", "desire": "权力", "growth_score": 0.3}}
    character_arc_state: Dict[str, Dict] = Field(default_factory=dict)

    # 冲突层级塔：分层管理冲突
    # Structure: {"tier1": [...内心冲突], "tier2": [...人际冲突], "tier3": [...社会/命运冲突]}
    conflict_levels: Dict[str, Any] = Field(default_factory=dict)

    # 宿命回响条目：可在未来触发的宿命元素
    # Structure: [{"proposition": "命题", "planted_week": 0, "echo_conditions": [...], "resolved": false}]
    fate_entries: list = Field(default_factory=list)

    # 世界呼吸事件：独立于主角的世界背景事件
    # Structure: [{"event": "描述", "week": 0, "visibility": "background", "affected_npcs": [...]}]
    world_breathing_events: list = Field(default_factory=list)

    @field_validator("relationships")
    @classmethod
    def validate_relationships(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Ensure relationship values are within bounds."""
        return {name: max(0, min(100, affinity)) for name, affinity in v.items()}

    @field_validator("world_projection_state", mode="before")
    @classmethod
    def validate_world_projection_state(cls, value: Any) -> Dict[str, Any]:
        """Make partial pre-projection saves readable without rewriting them."""
        return _sanitize_world_projection_state(value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert state to a persistence-safe dictionary."""
        from src.game.continuity_ledger import ContinuityLedger
        from src.utils.financial_narrative import (
            sanitize_authoritative_fact_records,
            sanitize_world_model_financial_authority,
        )
        from src.utils.legacy_data import strip_retired_wealth_keys

        # model_dump is provided by BaseModel when used in the combined class
        data = strip_retired_wealth_keys(getattr(self, "model_dump")())
        data["established_facts"] = sanitize_authoritative_fact_records(
            data.get("established_facts")
        )
        data["world_model_data"] = sanitize_world_model_financial_authority(
            data.get("world_model_data")
        )
        ledger = data.get("continuity_ledger")
        if isinstance(ledger, Mapping):
            data["continuity_ledger"] = ContinuityLedger(ledger).to_dict()
        return data  # type: ignore[no-any-return]

    def to_prompt_context(
        self,
        recent_rounds: int = 3,
        recent_decisions: int = 30,
    ) -> Dict[str, Any]:
        """P2-性能优化：为 AI 生成 prompt 提供字段投影。

        与 to_dict() 的区别：
        - round_history / decision_history 只保留最近 N 条（生成只消费近期上下文，
          decision_history 仅用于过用短语提取与上一事件定位）；
        - 排除与 prompt 无关的无界历史（story_history / 各类 summary /
          情绪弧线 / 新颖度等）。持久化与 HTTP 响应仍使用 to_dict()。
        """
        data = self.to_dict()
        data["round_history"] = (data.get("round_history") or [])[-recent_rounds:]
        data["decision_history"] = (data.get("decision_history") or [])[-recent_decisions:]
        for key in (
            "story_history",
            "four_week_summaries",
            "yearly_summaries",
            "weekly_summaries",
            "emotional_arc_history",
            "novelty_scores",
            "world_breathing_events",
        ):
            data.pop(key, None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerDataMixin":
        """Create state from dictionary."""
        # ★ 处理可能为 None 的字符串字段，避免 Pydantic 验证错误
        # 这是为了兼容旧数据，这些字段在之前的 bug 中可能被设为 None
        from src.utils.legacy_data import strip_retired_wealth_keys
        from src.utils.financial_narrative import (
            sanitize_authoritative_fact_records,
            sanitize_world_model_financial_authority,
        )

        cleaned_data = strip_retired_wealth_keys(data)
        cleaned_data["established_facts"] = sanitize_authoritative_fact_records(
            cleaned_data.get("established_facts")
        )
        cleaned_data["world_model_data"] = sanitize_world_model_financial_authority(
            cleaned_data.get("world_model_data")
        )
        if cleaned_data.get("last_round_full_story") is None:
            cleaned_data["last_round_full_story"] = ""
        return cls(**cleaned_data)

    def validate_state(self) -> bool:
        """
        Validate that all state values are within acceptable bounds.

        Returns:
            True if valid, raises ValueError if invalid
        """
        if not (settings.MIN_RESOURCE <= self.energy <= settings.MAX_RESOURCE):
            raise ValueError(f"Energy out of bounds: {self.energy}")
        if not (settings.MIN_RESOURCE <= self.mood <= settings.MAX_RESOURCE):
            raise ValueError(f"Mood out of bounds: {self.mood}")
        if not (settings.MIN_RESOURCE <= self.knowledge <= settings.MAX_RESOURCE):
            raise ValueError(f"Knowledge out of bounds: {self.knowledge}")
        if self.week < 0 or self.week > settings.TOTAL_WEEKS:
            raise ValueError(f"Week out of bounds: {self.week}")
        if self.age < 0:
            raise ValueError(f"Age cannot be negative: {self.age}")

        return True
