"""玩家状态管理。

此模块定义了PlayerState类，用于管理玩家的核心状态。
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from config.settings import settings
import logging

from src.game.state.character_state import CharacterState

logger = logging.getLogger(__name__)


class PlayerState(BaseModel):
    """Represents the player's current state in the game."""
    
    # Player identity
    player_name: str = Field(default="", description="玩家名称")
    life_vision: str = Field(default="", description="人生愿景")
    
    # Core attributes (0-100 scale)
    energy: int = Field(default=settings.INITIAL_ENERGY, ge=0, le=100)
    mood: int = Field(default=settings.INITIAL_MOOD, ge=0, le=100)
    knowledge: int = Field(default=settings.INITIAL_KNOWLEDGE, ge=0, le=100)
    wealth: int = Field(default=settings.INITIAL_WEALTH, ge=0)
    
    # Relationships: {name: affinity (0-100)} - 为了向后兼容保留
    relationships: Dict[str, int] = Field(default_factory=dict)
    
    # NPC角色状态系统: {name: CharacterState.model_dump()}
    characters: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    # Time tracking
    age: int = Field(default=settings.STARTING_AGE, ge=0)  # No upper age limit
    week: int = Field(default=0, ge=0)
    
    # Decision history
    decision_history: list = Field(default_factory=list)
    
    # Character creation settings
    character_settings: Dict[str, Any] = Field(default_factory=dict)
    
    # Story history - stores each week's story/event description
    story_history: list = Field(default_factory=list)
    
    # Four-week summaries - generated every 4 weeks
    four_week_summaries: list = Field(default_factory=list)
    
    # Yearly summaries - generated every 48 weeks
    yearly_summaries: list = Field(default_factory=list)
    
    # Multi-round system - new fields
    current_round: int = Field(default=0, ge=0)  # Current round within week (0, 1, 2)
    rounds_per_week: int = Field(default=settings.ROUNDS_PER_WEEK, ge=1)  # Number of rounds per week
    
    # Round history - stores each round's compressed summary and decision
    # Structure: [{"week": 0, "round": 0, "summary": "100字总结", "choice": "选项文本", "effects": {...}}]
    round_history: list = Field(default_factory=list)
    
    # Weekly summaries - generated at end of each week after all rounds
    # Structure: [{"week": 0, "summary": "周总结文本", "bonus_effects": {...}}]
    weekly_summaries: list = Field(default_factory=list)
    
    # Current event state - saves the event being displayed (not yet chosen)
    # This allows resuming exactly where the player left off
    # Structure: {"event_description": "...", "options": [{"text": "...", "effects": {...}}], "story_text": "..."}
    current_event_data: Optional[Dict[str, Any]] = Field(default=None)
    
    # 未完结的重要剧情线
    # Structure: [{"description": "...", "created_week": 0, "importance": "high/medium",
    #              "status": "active/deferred", "related_characters": [], "last_mentioned_week": 0}]
    pending_storylines: list = Field(default_factory=list)
    
    # 已建立的世界事实（人物角色/地理位置/正在进行的事务等一致性信息）
    # Structure: [{"fact": "...", "subject": "主体名", "category": "location/role/situation",
    #              "established_week": 0}]
    established_facts: list = Field(default_factory=list)
    
    # 上一轮完整故事文本（event_description + story_continuation），用于强制续写
    last_round_full_story: str = Field(default="", description="上一轮的完整故事文本，供下一轮续写参考")
    
    # 上一轮事件是否已完结
    last_event_concluded: bool = Field(default=True, description="上一轮事件是否已自然完结。False表示需要强制续写")
    
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
            "character_profiles": {}
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
            "recovery_distances": []
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
    
    @field_validator('relationships')
    @classmethod
    def validate_relationships(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Ensure relationship values are within bounds."""
        return {name: max(0, min(100, affinity)) for name, affinity in v.items()}
    
    def update(
        self,
        energy: Optional[int] = None,
        mood: Optional[int] = None,
        knowledge: Optional[int] = None,
        wealth: Optional[int] = None,
        relationships: Optional[Dict[str, int]] = None
    ) -> None:
        """
        Update player state with new values.
        
        Args:
            energy: Change in energy (can be negative)
            mood: Change in mood (can be negative)
            knowledge: Change in knowledge (can be negative)
            wealth: Change in wealth (can be negative)
            relationships: Dict of relationship changes {name: change}
        """
        if energy is not None:
            self.energy = max(settings.MIN_RESOURCE, min(settings.MAX_RESOURCE, self.energy + energy))
        
        if mood is not None:
            self.mood = max(settings.MIN_RESOURCE, min(settings.MAX_RESOURCE, self.mood + mood))
        
        if knowledge is not None:
            self.knowledge = max(settings.MIN_RESOURCE, min(settings.MAX_RESOURCE, self.knowledge + knowledge))
        
        if wealth is not None:
            self.wealth = max(0, self.wealth + wealth)  # Wealth has no upper limit
        
        if relationships is not None:
            for name, change in relationships.items():
                current = self.relationships.get(name, 50)  # Default to neutral
                self.relationships[name] = max(
                    settings.MIN_RESOURCE,
                    min(settings.MAX_RESOURCE, current + change)
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
        start_year = era.get("year", 2024)
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
            "date_string_en": f"Year {current_year}, Month {current_month}, Week {week_in_month}"
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
            round_name = round_names[round_idx] if round_idx < len(round_names) else f"第{round_idx+1}轮"
            date_str = r.get("date_info", {}).get("date_string", "")
            date_prefix = f"({date_str}) " if date_str else ""
            event_concluded = r.get('event_concluded', True)
            concluded_marker = "" if event_concluded else " ⚠️未完结"
            choice = r.get('choice', '')
            
            # Use full event_description for richer context; fallback to summary
            full_story = r.get('event_description', '') or r.get('summary', '')
            continuation = r.get('story_continuation', '')
            
            parts = [f"【{round_name}】{date_prefix}{concluded_marker}"]
            parts.append(full_story)
            parts.append(f"(选择了: {choice})")
            if continuation:
                parts.append(f"→ 后续发展: {continuation}")
            context_parts.append("\n".join(parts))
        
        return "\n\n".join(context_parts)
    
    def validate(self) -> bool:
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
        if self.wealth < 0:
            raise ValueError(f"Wealth cannot be negative: {self.wealth}")
        if self.week < 0 or self.week > settings.TOTAL_WEEKS:
            raise ValueError(f"Week out of bounds: {self.week}")
        if self.age < 0:
            raise ValueError(f"Age cannot be negative: {self.age}")
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary."""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerState":
        """Create state from dictionary."""
        return cls(**data)
    
    def is_game_over(self) -> bool:
        """Check if game has ended."""
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
    
    # ==================== NPC角色管理方法 ====================
    
    def add_character(self, character: CharacterState) -> None:
        """
        添加或更新一个NPC角色。
        同时同步到relationships字典保持兼容性。
        
        Args:
            character: CharacterState实例
        """
        self.characters[character.name] = character.model_dump()
        # 同步到relationships字典
        self.relationships[character.name] = character.affinity
        logger.debug(f"Added character: {character.name} with affinity {character.affinity}")
    
    def get_character(self, name: str) -> Optional[CharacterState]:
        """
        获取指定名字的NPC角色。
        
        Args:
            name: 角色名字
        
        Returns:
            CharacterState实例，不存在则返回None
        """
        if name in self.characters:
            return CharacterState(**self.characters[name])
        return None
    
    def get_all_characters(self) -> List[CharacterState]:
        """
        获取所有NPC角色。
        
        Returns:
            CharacterState列表
        """
        return [CharacterState(**data) for data in self.characters.values()]
    
    def update_character(self, name: str, **kwargs) -> bool:
        """
        更新指定角色的属性。
        
        Args:
            name: 角色名字
            **kwargs: 要更新的属性
        
        Returns:
            是否更新成功
        """
        if name not in self.characters:
            logger.warning(f"Character not found: {name}")
            return False
        
        character_data = self.characters[name]
        for key, value in kwargs.items():
            if key in character_data:
                character_data[key] = value
        
        self.characters[name] = character_data
        
        # 如果更新了affinity，同步到relationships
        if "affinity" in kwargs:
            self.relationships[name] = kwargs["affinity"]
        
        return True
    
    def update_character_relationship(
        self,
        name: str,
        affinity_change: int = 0,
        trust_change: int = 0,
        respect_change: int = 0,
        mood_change: int = 0,
        interaction_summary: str = ""
    ) -> bool:
        """Update character relationship. Delegates to PlayerService."""
        from src.game.player_service import PlayerService
        return PlayerService.update_character_relationship(
            self, name, affinity_change, trust_change, respect_change,
            mood_change, interaction_summary
        )
    
    def sync_relationships_to_characters(self) -> None:
        """
        将relationships字典的变化同步到characters。
        用于处理通过旧API更新的关系值。
        """
        for name, affinity in self.relationships.items():
            if name in self.characters:
                self.characters[name]["affinity"] = affinity
    
    def sync_characters_to_relationships(self) -> None:
        """
        将characters的affinity同步到relationships。
        """
        for name, char_data in self.characters.items():
            self.relationships[name] = char_data.get("affinity", 50)
    
    def get_characters_context(self) -> str:
        """Generate AI context string for all characters. Delegates to PlayerService."""
        from src.game.player_service import PlayerService
        return PlayerService.get_characters_context(self)
    
    def check_character_events(self) -> List[Dict[str, Any]]:
        """Check all characters for special event triggers. Delegates to PlayerService."""
        from src.game.player_service import PlayerService
        return PlayerService.check_character_events(self)
    
    def initialize_characters_from_settings(self) -> None:
        """Initialize character system from character_settings. Delegates to PlayerService."""
        from src.game.player_service import PlayerService
        PlayerService.initialize_characters_from_settings(self)
    
    # ==================== 预定事件管理方法 ====================
    
    def add_scheduled_event(self, event: "ScheduledEvent") -> None:
        """添加一个预定事件
        
        Args:
            event: ScheduledEvent 实例
        """
        from src.game.scheduled_events import ScheduledEvent
        # 检查是否已存在
        existing_ids = [e.get("event_id") for e in self.scheduled_events]
        if event.event_id not in existing_ids:
            self.scheduled_events.append(event.to_dict())
            logger.debug(f"添加预定事件: {event.description[:40]}... (ID: {event.event_id})")
    
    def get_scheduled_event_manager(self) -> "ScheduledEventManager":
        """获取预定事件管理器实例
        
        Returns:
            ScheduledEventManager 实例
        """
        from src.game.scheduled_events import ScheduledEventManager
        return ScheduledEventManager.from_dict_list(self.scheduled_events)
    
    def sync_scheduled_events_from_manager(self, manager: "ScheduledEventManager") -> None:
        """从管理器同步预定事件状态
        
        Args:
            manager: ScheduledEventManager 实例
        """
        self.scheduled_events = manager.to_dict_list()
    
    def get_pending_scheduled_events(self, week: int = None, round_num: int = None) -> List[Dict[str, Any]]:
        """获取待触发的预定事件
        
        Args:
            week: 指定周数，默认当前周
            round_num: 指定轮次，默认当前轮次
        
        Returns:
            预定事件字典列表
        """
        target_week = week if week is not None else self.week
        target_round = round_num if round_num is not None else self.current_round
        
        pending = []
        for e in self.scheduled_events:
            if e.get("status") != "pending":
                continue
            if e.get("scheduled_week") == target_week and e.get("scheduled_round") == target_round:
                pending.append(e)
        
        # 按重要程度排序
        importance_order = {"critical": 0, "normal": 1, "minor": 2}
        pending.sort(key=lambda e: importance_order.get(e.get("importance", "normal"), 1))
        
        return pending
    
    def mark_scheduled_event_triggered(self, event_id: str) -> bool:
        """标记预定事件已触发
        
        Args:
            event_id: 事件ID
        
        Returns:
            是否成功标记
        """
        for e in self.scheduled_events:
            if e.get("event_id") == event_id:
                e["status"] = "triggered"
                logger.info(f"预定事件已触发: {event_id}")
                return True
        return False
    
    def get_overdue_scheduled_events(self) -> List[Dict[str, Any]]:
        """获取已过期的预定事件
        
        Returns:
            过期的预定事件列表
        """
        overdue = []
        for e in self.scheduled_events:
            if e.get("status") != "pending":
                continue
            scheduled_week = e.get("scheduled_week", -1)
            scheduled_round = e.get("scheduled_round", -1)
            
            if scheduled_week < self.week:
                overdue.append(e)
            elif scheduled_week == self.week and scheduled_round < self.current_round:
                overdue.append(e)
        
        return overdue
