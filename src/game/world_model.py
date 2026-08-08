"""Structured world model for story consistency enforcement.

Provides queryable, validatable data structures for geographic locations,
career progression, commitments, causal chains, and physical states.
Built from PlayerState data and used to generate constraint text for AI prompts
and validate generated stories.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.game.relationship_authority import build_required_cast_constraints, extract_required_key_people
from src.utils.financial_narrative import contains_precise_financial_fact

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================


@dataclass
class LocationInfo:
    """Character's current geographic location."""

    location: str = ""  # "北京市朝阳区"
    region: str = ""  # "北京" (coarse-grained for distance checks)
    since_week: int = 0  # When they arrived / were established here
    travel_mode: str = "resident"  # "resident" / "visiting" / "traveling"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location": self.location,
            "region": self.region,
            "since_week": self.since_week,
            "travel_mode": self.travel_mode,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LocationInfo":
        return cls(
            location=d.get("location", ""),
            region=d.get("region", ""),
            since_week=d.get("since_week", 0),
            travel_mode=d.get("travel_mode", "resident"),
        )


@dataclass
class CareerInfo:
    """Character's career record."""

    current_job: str = ""  # "产品经理"
    employer: str = ""  # "某科技公司"
    level: str = "mid"  # "junior"/"mid"/"senior"/"lead"/"executive"
    since_week: int = 0  # When this role started
    history: List[Dict[str, Any]] = field(default_factory=list)  # Past career changes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_job": self.current_job,
            "employer": self.employer,
            "level": self.level,
            "since_week": self.since_week,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CareerInfo":
        return cls(
            current_job=d.get("current_job", ""),
            employer=d.get("employer", ""),
            level=d.get("level", "mid"),
            since_week=d.get("since_week", 0),
            history=d.get("history", []),
        )


@dataclass
class Commitment:
    """A promise, appointment, or obligation."""

    description: str = ""  # "答应周末陪妈妈去医院"
    parties: List[str] = field(default_factory=list)  # People involved
    deadline_week: int = -1  # Expected fulfillment week (-1 = no deadline)
    status: str = "pending"  # "pending"/"fulfilled"/"broken"/"expired"
    created_week: int = 0
    importance: str = "normal"  # "critical"/"normal"/"minor"

    # ★ 预定事件系统：支持在具体轮次强制触发承诺事件
    scheduled_round: int = -1  # 具体轮次（-1表示无具体轮次，0=周一, 1=周中, 2=周末）
    scheduled_week: int = -1  # 具体周数（-1表示无具体周数，用于跨周承诺）
    event_hint: str = ""  # 事件提示（描述事件应该包含的内容）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "parties": self.parties,
            "deadline_week": self.deadline_week,
            "status": self.status,
            "created_week": self.created_week,
            "importance": self.importance,
            "scheduled_round": self.scheduled_round,
            "scheduled_week": self.scheduled_week,
            "event_hint": self.event_hint,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Commitment":
        return cls(
            description=d.get("description", ""),
            parties=d.get("parties", []),
            deadline_week=d.get("deadline_week", -1),
            status=d.get("status", "pending"),
            created_week=d.get("created_week", 0),
            importance=d.get("importance", "normal"),
            scheduled_round=d.get("scheduled_round", -1),
            scheduled_week=d.get("scheduled_week", -1),
            event_hint=d.get("event_hint", ""),
        )

    def is_scheduled(self) -> bool:
        """检查是否为预定事件（有具体的触发时间点）"""
        return self.scheduled_week >= 0 and self.scheduled_round >= 0


@dataclass
class CausalChain:
    """An action-consequence pair that should echo in future stories."""

    cause: str = ""  # "得罪了部门主管李总"
    expected_consequence: str = ""  # "可能影响晋升评审"
    characters: List[str] = field(default_factory=list)
    created_week: int = 0
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cause": self.cause,
            "expected_consequence": self.expected_consequence,
            "characters": self.characters,
            "created_week": self.created_week,
            "resolved": self.resolved,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CausalChain":
        return cls(
            cause=d.get("cause", ""),
            expected_consequence=d.get("expected_consequence", ""),
            characters=d.get("characters", []),
            created_week=d.get("created_week", 0),
            resolved=d.get("resolved", False),
        )


@dataclass
class PhysicalState:
    """A character's notable physical condition (injury, illness, pregnancy, etc.)."""

    condition: str = ""  # "右腿骨折"
    severity: str = "moderate"  # "minor"/"moderate"/"severe"
    since_week: int = 0
    expected_recovery_week: int = -1  # -1 = unknown/permanent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition": self.condition,
            "severity": self.severity,
            "since_week": self.since_week,
            "expected_recovery_week": self.expected_recovery_week,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PhysicalState":
        return cls(
            condition=d.get("condition", ""),
            severity=d.get("severity", "moderate"),
            since_week=d.get("since_week", 0),
            expected_recovery_week=d.get("expected_recovery_week", -1),
        )


@dataclass
class CharacterProfile:
    """Behavioral profile for a character, synthesized from accumulated story evidence.

    Unlike fixed personality traits (set at character creation), profiles
    are dynamically built from observed behaviors across multiple stories.
    Once evidence_count reaches a threshold, personality violations for
    this character become CRITICAL-level in consistency validation.
    """

    character: str = ""  # Character name
    behavioral_traits: List[str] = field(default_factory=list)  # ["冲突回避型", "善于倾听"]
    speech_style: str = ""  # "说话直接、偶尔带自嘲式幽默"
    decision_patterns: List[str] = field(default_factory=list)  # ["倾向妥协", "重视关系胜过利益"]
    emotional_tendencies: List[str] = field(default_factory=list)  # ["压抑情绪", "独处时才释放"]
    behavioral_boundaries: List[str] = field(
        default_factory=list
    )  # ["绝不在公开场合发怒", "不会背叛朋友"]
    constraint_text: str = ""  # Synthesized constraint for prompt injection
    evidence_count: int = 0  # How many weekly syntheses have contributed
    last_updated_week: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character": self.character,
            "behavioral_traits": self.behavioral_traits,
            "speech_style": self.speech_style,
            "decision_patterns": self.decision_patterns,
            "emotional_tendencies": self.emotional_tendencies,
            "behavioral_boundaries": self.behavioral_boundaries,
            "constraint_text": self.constraint_text,
            "evidence_count": self.evidence_count,
            "last_updated_week": self.last_updated_week,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CharacterProfile":
        return cls(
            character=d.get("character", ""),
            behavioral_traits=d.get("behavioral_traits", []),
            speech_style=d.get("speech_style", ""),
            decision_patterns=d.get("decision_patterns", []),
            emotional_tendencies=d.get("emotional_tendencies", []),
            behavioral_boundaries=d.get("behavioral_boundaries", []),
            constraint_text=d.get("constraint_text", ""),
            evidence_count=d.get("evidence_count", 0),
            last_updated_week=d.get("last_updated_week", 0),
        )


# ==================== Career Level System ====================

# Ordered from low to high
CAREER_LEVELS = ["intern", "junior", "mid", "senior", "lead", "executive"]
CAREER_LEVEL_INDEX = {level: i for i, level in enumerate(CAREER_LEVELS)}

# Maximum level-jump allowed per transition (2 = can skip 1 level, e.g. junior->senior)
MAX_CAREER_JUMP = 2

# Minimum weeks at a level before promotion is plausible
MIN_WEEKS_BEFORE_PROMOTION = {
    "intern": 12,  # ~3 months
    "junior": 24,  # ~6 months
    "mid": 48,  # ~1 year
    "senior": 48,  # ~1 year
    "lead": 48,  # ~1 year
}


# ==================== WorldModel ====================


class WorldModel:
    """Structured world model built from PlayerState, provides consistency
    querying, validation, and constraint text generation."""

    def __init__(self):
        self.character_locations: Dict[str, LocationInfo] = {}
        self.career_records: Dict[str, CareerInfo] = {}
        self.active_commitments: List[Commitment] = []
        self.causal_chains: List[CausalChain] = []
        self.physical_states: Dict[str, PhysicalState] = {}
        self.dynamic_facts: List[Any] = []  # List of DynamicFact objects from StoryAnalyzer
        self.character_profiles: Dict[str, CharacterProfile] = (
            {}
        )  # Behavioral profiles per character
        self.current_week: int = 0
        self.era: str = "modern"

        # ★ 新增字段：位置图谱与角色知识集
        self.location_graph: Dict[str, Dict[str, int]] = {}  # {"城市A": {"城市B": 2, "城市C": 3}}
        self.character_knowledge_sets: Dict[str, set] = {}  # {"角色A": {"秘密1", "事件2"}}
        self.required_cast: List[Dict[str, str]] = []
        self.continuity_ledger = None
        self.continuity_source_state = None

    # -------------------- Factory --------------------

    @classmethod
    def from_player_state(cls, player_state) -> "WorldModel":
        """Build a WorldModel from a PlayerState instance.

        Reads from both the new ``world_model_data`` dict (if present) and
        the legacy ``established_facts`` list so that older saves are still
        supported.
        """
        wm = cls()
        wm.current_week = player_state.week

        # Extract era
        cs = player_state.character_settings or {}
        era_info = cs.get("era", {})
        wm.era = era_info.get("era_description", "modern")
        wm.required_cast = extract_required_key_people(cs)
        wm.continuity_source_state = player_state

        try:
            from src.game.continuity_ledger import ContinuityLedger

            wm.continuity_ledger = ContinuityLedger.from_player_state(player_state)
            wm.continuity_ledger.persist(player_state)
        except (TypeError, ValueError, KeyError) as exc:
            logger.warning("Skipping invalid continuity ledger: %s", exc)

        # ---------- Read new structured data ----------
        wmd: Dict[str, Any] = getattr(player_state, "world_model_data", None) or {}

        for name, loc_d in wmd.get("character_locations", {}).items():
            wm.character_locations[name] = LocationInfo.from_dict(loc_d)

        for name, car_d in wmd.get("career_records", {}).items():
            wm.career_records[name] = CareerInfo.from_dict(car_d)

        for com_d in wmd.get("active_commitments", []):
            wm.active_commitments.append(Commitment.from_dict(com_d))

        for cc_d in wmd.get("causal_chains", []):
            wm.causal_chains.append(CausalChain.from_dict(cc_d))

        for name, ps_d in wmd.get("physical_states", {}).items():
            wm.physical_states[name] = PhysicalState.from_dict(ps_d)

        # ---------- Read dynamic facts from StoryAnalyzer ----------
        for df_d in wmd.get("dynamic_facts", []):
            try:
                from src.ai.story_analyzer import DynamicFact

                df = DynamicFact.from_dict(df_d)
                # Skip expired facts
                if df.expiry_week > 0 and df.expiry_week <= wm.current_week:
                    df.active = False
                if df.active and not contains_precise_financial_fact(
                    df.fact_type,
                    df.subject,
                    df.description,
                    df.constraint_text,
                    df.source_excerpt,
                ):
                    wm.dynamic_facts.append(df)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping invalid dynamic fact data: {e}, data: {df_d}")
            except Exception as e:
                logger.error(f"Unexpected error parsing dynamic fact: {e}, data: {df_d}")

        # ---------- Read character behavioral profiles ----------
        for name, cp_d in wmd.get("character_profiles", {}).items():
            try:
                wm.character_profiles[name] = CharacterProfile.from_dict(cp_d)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Skipping invalid character profile data for {name}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error parsing character profile {name}: {e}")

        # ---------- Read location graph ----------
        for loc_name, distances in wmd.get("location_graph", {}).items():
            if isinstance(distances, dict):
                wm.location_graph[loc_name] = distances

        # ---------- Read character knowledge sets ----------
        for char_name, knowledge in wmd.get("character_knowledge_sets", {}).items():
            if isinstance(knowledge, (list, set)):
                wm.character_knowledge_sets[char_name] = set(knowledge)

        # ---------- Supplement from legacy established_facts ----------
        for fact in getattr(player_state, "established_facts", []):
            category = fact.get("category", "")
            subject = fact.get("subject", "")
            fact_text = fact.get("fact", "")
            week = fact.get("established_week", 0)

            if not subject or not fact_text:
                continue

            if category == "location" and subject not in wm.character_locations:
                wm.character_locations[subject] = LocationInfo(
                    location=fact_text,
                    region=_extract_region(fact_text),
                    since_week=week,
                    travel_mode="resident",
                )
            elif category == "role" and subject not in wm.career_records:
                wm.career_records[subject] = CareerInfo(current_job=fact_text, since_week=week)

        # ---------- Supplement from character_settings (initial occupation) ----------
        if "occupation" in cs and "主角" not in wm.career_records:
            occ = cs["occupation"]
            protagonist_name = player_state.player_name or "主角"
            wm.career_records[protagonist_name] = CareerInfo(
                current_job=occ.get("occupation", ""),
                employer=occ.get("employer", ""),
                level=occ.get("level", "mid"),
                since_week=0,
            )

        return wm

    # -------------------- Validation Methods --------------------

    def check_geographic_feasibility(self, char_names: List[str]) -> List[str]:
        """Check whether characters appearing in the same scene are geographically plausible.

        Returns a list of conflict description strings (empty = no issues).
        """
        issues: List[str] = []
        if len(char_names) < 2:
            return issues

        located = {
            n: self.character_locations[n] for n in char_names if n in self.character_locations
        }
        if len(located) < 2:
            return issues  # Not enough location data to validate

        regions: dict[str, list[str]] = {}
        for name, loc in located.items():
            regions.setdefault(loc.region, []).append(name)

        if len(regions) > 1:
            parts = []
            for region, names in regions.items():
                parts.append(f"{'、'.join(names)}在{region}")
            issues.append(
                f"地理冲突：{' ；'.join(parts)}，他们不应同时出现在同一个物理场景中。"
                f"如需同场景互动，请使用电话/视频通话，或先交代人物移动。"
            )

        return issues

    def check_career_plausibility(
        self, character: str, new_role: str, new_level: str = ""
    ) -> List[str]:
        """Check whether a career change is plausible. Returns conflict descriptions."""
        issues: List[str] = []
        if character not in self.career_records:
            return issues

        record = self.career_records[character]

        # Level jump check
        if new_level and record.level:
            old_idx = CAREER_LEVEL_INDEX.get(record.level, -1)
            new_idx = CAREER_LEVEL_INDEX.get(new_level, -1)
            if old_idx >= 0 and new_idx >= 0:
                jump = new_idx - old_idx
                if jump > MAX_CAREER_JUMP:
                    issues.append(
                        f"职业跳跃过大：{character}从{record.level}({record.current_job})直接升到"
                        f"{new_level}({new_role})，跨越了{jump}个级别，不太合理。"
                    )

                # Time check
                weeks_at_level = self.current_week - record.since_week
                min_weeks = MIN_WEEKS_BEFORE_PROMOTION.get(record.level, 24)
                if jump > 0 and weeks_at_level < min_weeks:
                    issues.append(
                        f"晋升过快：{character}在当前职位仅{weeks_at_level}周"
                        f"（最低建议{min_weeks}周），升职不太合理。"
                    )

        return issues

    def get_pending_commitments(self, week: int) -> List[Commitment]:
        """Get commitments that are due or overdue at the given week."""
        result = []
        for c in self.active_commitments:
            if c.status != "pending":
                continue
            if c.deadline_week >= 0 and c.deadline_week <= week:
                result.append(c)
        return result

    def get_expiring_commitments(self, week: int, lookahead: int = 3) -> List[Commitment]:
        """Get commitments that will expire within `lookahead` weeks."""
        result = []
        for c in self.active_commitments:
            if c.status != "pending":
                continue
            if 0 <= c.deadline_week <= week + lookahead:
                result.append(c)
        return result

    def get_active_causal_chains(self) -> List[CausalChain]:
        """Get unresolved causal chains."""
        return [cc for cc in self.causal_chains if not cc.resolved]

    def get_established_profile_names(self) -> List[str]:
        """Get names of characters with well-established behavioral profiles (evidence_count >= 4)."""
        return [
            name
            for name, p in self.character_profiles.items()
            if p.evidence_count >= 4 and p.constraint_text
        ]

    # -------------------- Epic Narrative Query Methods --------------------

    def get_character_arc(self, name: str) -> Optional[Dict]:
        """获取角色弧光状态（从 PlayerState.character_arc_state 读取）。

        注意：此方法需要 PlayerState 上下文，调用方应传入 player_state.character_arc_state。
        WorldModel 本身不存储此数据，而是作为查询代理。
        返回 None 表示该角色无弧光数据。
        """
        # character_arc_state 存储在 PlayerState 中，WorldModel 不直接持有
        # 此方法作为接口预留，实际调用时由上层传入数据
        return None

    def get_active_conflicts(self, tier: int) -> List[Dict]:
        """获取指定层级的活跃冲突（从 PlayerState.conflict_levels 读取）。

        Args:
            tier: 冲突层级 (1=内心, 2=人际, 3=社会/命运)

        Returns:
            该层级的冲突列表，无数据时返回空列表。
        """
        return []

    def get_pending_fate_echoes(self, current_week: int) -> List[Dict]:
        """获取当前周可能触发的宿命回响条目（从 PlayerState.fate_entries 读取）。

        Args:
            current_week: 当前周数

        Returns:
            未解决且满足回响条件的条目列表。
        """
        return []

    def get_world_events(self, recent_n: int = 5) -> List[Dict]:
        """获取最近的世界呼吸事件（从 PlayerState.world_breathing_events 读取）。

        Args:
            recent_n: 返回最近 N 条事件

        Returns:
            最近的世界事件列表。
        """
        return []

    # -------------------- Constraint Text Generation --------------------

    def build_constraints_text(self, language: str) -> str:
        """Build a comprehensive constraint text block for injection into AI prompts.

        This replaces/enhances the old ``_build_established_facts_context``.
        """
        zh = language == "zh"
        sections: List[str] = []

        # --- Geographic Constraints ---
        loc_lines = self._build_location_constraints(zh)
        if loc_lines:
            sections.append(loc_lines)

        # --- Career Constraints ---
        career_lines = self._build_career_constraints(zh)
        if career_lines:
            sections.append(career_lines)

        # --- Commitment Constraints ---
        commit_lines = self._build_commitment_constraints(zh)
        if commit_lines:
            sections.append(commit_lines)

        # --- Causal Chain Constraints ---
        causal_lines = self._build_causal_constraints(zh)
        if causal_lines:
            sections.append(causal_lines)

        # --- Physical State Constraints ---
        phys_lines = self._build_physical_constraints(zh)
        if phys_lines:
            sections.append(phys_lines)

        # --- Dynamic Facts (AI-identified constraints) ---
        dynamic_lines = self._build_dynamic_facts_constraints(zh)
        if dynamic_lines:
            sections.append(dynamic_lines)

        # --- Character Behavioral Profiles ---
        profile_lines = self._build_character_profile_constraints(zh)
        if profile_lines:
            sections.append(profile_lines)

        # --- Preset Key People Relationships ---
        required_cast_lines = self._build_required_cast_constraints("zh" if zh else "en")
        if required_cast_lines:
            sections.append(required_cast_lines)

        # Keep the authoritative ledger last so it has explicit precedence
        # over legacy summaries and extracted prose facts.
        if self.continuity_ledger is not None:
            ledger_lines = self.continuity_ledger.build_constraints_text("zh" if zh else "en")
            if ledger_lines:
                sections.append(ledger_lines)

        if not sections:
            return ""

        header = (
            "\n【世界模型约束 — 必须严格遵守，不得矛盾】"
            if zh
            else "\n[World Model Constraints — MUST STRICTLY FOLLOW, NO CONTRADICTIONS]"
        )
        footer = (
            (
                "❗以上所有约束在故事生成时必须严格遵守。如需变动（如人物搬迁、职位变化），"
                "必须在故事中给出合理的交代和过渡。"
            )
            if zh
            else (
                "❗ALL above constraints MUST be strictly followed. Any changes "
                "(relocation, career change) MUST be justified and transitioned in the story."
            )
        )

        return header + "\n" + "\n".join(sections) + "\n" + footer

    def _build_required_cast_constraints(self, language: str) -> str:
        if not self.required_cast:
            return ""
        return build_required_cast_constraints(
            {"relationships": {"key_people": self.required_cast}},
            language,
        )

    def _build_location_constraints(self, zh: bool) -> str:
        if not self.character_locations:
            return ""
        lines = []
        # 定义模糊位置关键词
        vague_keywords_zh = ["未知", "离开", "旅途中", "不明", "外出"]
        vague_keywords_en = ["unknown", "left", "traveling", "away", "departed"]

        # 分类角色：明确位置 vs 模糊位置
        clear_chars = []  # (name, loc) 有明确位置的角色
        vague_chars = []  # (name, loc, status) 位置模糊的角色

        for name, loc in self.character_locations.items():
            loc_lower = loc.location.lower()
            is_vague = False
            vague_status = ""

            # 检测是否为模糊位置
            if zh:
                for kw in vague_keywords_zh:
                    if kw in loc.location:
                        is_vague = True
                        vague_status = loc.location
                        break
            else:
                for kw in vague_keywords_en:
                    if kw in loc_lower:
                        is_vague = True
                        vague_status = loc.location
                        break

            # 旅途中模式也算模糊位置
            if loc.travel_mode == "traveling":
                is_vague = True
                vague_status = vague_status or ("旅途中" if zh else "traveling")

            if is_vague:
                vague_chars.append((name, loc, vague_status))
            else:
                clear_chars.append((name, loc))

        if zh:
            lines.append("=" * 60)
            lines.append("🚨 【人物地理位置约束 — 违反将导致故事被判定为不合格】")
            lines.append("=" * 60)

            # 明确位置的角色 - 严格约束
            if clear_chars:
                lines.append("  【有明确位置的角色 — 绝对禁止违反】")
                for name, loc in clear_chars:
                    mode_label = {
                        "resident": "常住",
                        "visiting": "暂访",
                        "traveling": "旅途中",
                    }.get(loc.travel_mode, "")
                    lines.append(
                        f"  ❗ {name} 当前位置：{loc.location}（{loc.region}，{mode_label}）"
                    )
                lines.append("")
                lines.append("  🚨 【硬性规则 — 违反将触发重新生成】：")
                lines.append("  1. 上述角色只能出现在其【当前位置】")
                lines.append("  2. 如果需要在其他地点出现，必须在故事中明确交代移动过程")
                lines.append("  3. 两个在不同地点的角色不能在同一物理场景中对话或互动")
                lines.append("")

            # 模糊位置的角色 - 灵活约束
            if vague_chars:
                lines.append("  【位置不确定的角色】")
                for name, loc, status in vague_chars:
                    lines.append(f"  💡 {name} 目前状态：{status}")
                lines.append("  📝 这些角色如需出现，应在故事中自然交代其回归或到达的原因。")
                lines.append("")

            lines.append("  ❌ 【绝对禁止的地理错误】（违反将触发重新生成）：")
            lines.append("  1. 不同城市/地点的人物在同一物理场景中偶遇，未交代移动")
            lines.append("  2. 角色从其当前位置瞬间移动到其他地点，无过程交代")
            lines.append("  3. 角色出现在与其当前位置矛盾的地点")
            lines.append("")
            lines.append("  ✅ 【正确的处理方式】：")
            lines.append("  - 人物A在地点X，人物B在地点Y：他们只能通过通讯方式互动")
            lines.append("  - 如需面对面互动：必须先写人物A从X移动到Y的过程")
            lines.append("=" * 60)
        else:
            lines.append("=" * 60)
            lines.append("🚨 [CHARACTER LOCATION CONSTRAINTS — Violations cause story rejection]")
            lines.append("=" * 60)

            # 明确位置的角色 - 严格约束
            if clear_chars:
                lines.append(
                    "  [Characters with clear locations — ABSOLUTELY FORBIDDEN to violate]"
                )
                for name, loc in clear_chars:
                    mode_label = {
                        "resident": "resident",
                        "visiting": "visiting",
                        "traveling": "traveling",
                    }.get(loc.travel_mode, "")
                    lines.append(
                        f"  ❗ {name} current location: {loc.location} ({loc.region}, {mode_label})"
                    )
                lines.append("")
                lines.append("  🚨 [HARD RULES — Violations trigger regeneration]:")
                lines.append("  1. Above characters can ONLY appear at their [current location]")
                lines.append(
                    "  2. If they need to appear elsewhere, travel MUST be explicitly narrated"
                )
                lines.append(
                    "  3. Characters at different locations CANNOT interact in the same physical scene"
                )
                lines.append("")

            # 模糊位置的角色 - 灵活约束
            if vague_chars:
                lines.append("  [Characters with uncertain locations]")
                for name, loc, status in vague_chars:
                    lines.append(f"  💡 {name} current status: {status}")
                lines.append(
                    "  📝 If these characters need to appear, naturally explain their return or arrival."
                )
                lines.append("")

            lines.append("  ❌ [ABSOLUTELY FORBIDDEN GEOGRAPHIC ERRORS] (trigger regeneration):")
            lines.append(
                "  1. Characters from different cities/locations meeting casually without travel narration"
            )
            lines.append(
                "  2. Characters instantly teleporting from their location to another without process"
            )
            lines.append(
                "  3. Characters appearing at locations that contradict their current position"
            )
            lines.append("")
            lines.append("  ✅ [CORRECT approach]:")
            lines.append(
                "  - Character A at Location X, Character B at Location Y: they can only interact via communication"
            )
            lines.append(
                "  - For face-to-face interaction: MUST first narrate Character A traveling from X to Y"
            )
            lines.append("=" * 60)
        return "\n".join(lines)

    def _build_career_constraints(self, zh: bool) -> str:
        if not self.career_records:
            return ""
        lines = []
        if zh:
            lines.append("💼 【人物职业/职位】")
            for name, cr in self.career_records.items():
                emp = f"（{cr.employer}）" if cr.employer else ""
                lines.append(f"  - {name}：{cr.current_job}{emp}，级别={cr.level}")
            lines.append("  ⚠️ 职位变动必须合理递进，不可跳跃式晋升。")
        else:
            lines.append("[Character Careers]")
            for name, cr in self.career_records.items():
                emp = f" at {cr.employer}" if cr.employer else ""
                lines.append(f"  - {name}: {cr.current_job}{emp}, level={cr.level}")
            lines.append("  Warning: Career changes must be gradual, no unrealistic jumps.")
        return "\n".join(lines)

    def _build_commitment_constraints(self, zh: bool) -> str:
        pending = [c for c in self.active_commitments if c.status == "pending"]
        if not pending:
            return ""

        # ★ 方案2：关键承诺不过期，持续追踪
        # 将 critical 承诺的截止日期延长，避免被标记为"已过期"
        def get_effective_deadline(c: Commitment) -> int:
            """获取有效截止日期，critical承诺不过期"""
            if c.importance == "critical" and c.deadline_week > 0:
                # critical 承诺的有效期延长到当前周+8，避免过早标记为过期
                return max(c.deadline_week, self.current_week + 8)
            return c.deadline_week

        # Focus on urgent ones (due within 4 weeks or overdue)
        # 使用有效截止日期判断紧迫性
        urgent = [c for c in pending if 0 <= get_effective_deadline(c) <= self.current_week + 4]
        non_urgent = [
            c
            for c in pending
            if c.deadline_week < 0 or get_effective_deadline(c) > self.current_week + 4
        ]

        lines = []
        if zh:
            lines.append("🤝 【未兑现的承诺/约定 — 违反将导致故事被判定为不合格】")
            lines.append("")
            lines.append("  🚨 【硬性规则 — 违反将触发重新生成】：")
            lines.append("  1. 涉及承诺的角色不能做出与承诺直接冲突的行为")
            lines.append(
                "  2. 如果承诺涉及角色状态（如'离开'、'隐藏'），该角色不能在没有交代的情况下改变状态"
            )
            lines.append("  3. 关键承诺（critical）必须被妥善处理，不能被忽略")
            lines.append("")
            if urgent:
                lines.append("  ❗ 【即将到期或已过期的承诺】（必须处理）：")
                for c in urgent:
                    # ★ 关键承诺显示为"待兑现"而非"已过期"
                    if c.importance == "critical" and c.deadline_week <= self.current_week:
                        overdue = "【关键承诺，待兑现 — 必须在本轮故事中处理或回应】"
                    else:
                        overdue = (
                            "【已过期！必须在故事中解释或处理】"
                            if c.deadline_week <= self.current_week
                            else f"（第{c.deadline_week}周截止）"
                        )
                    lines.append(
                        f"  - [{c.importance}] {c.description} — 涉及：{'、'.join(c.parties)}{overdue}"
                    )
            if non_urgent:
                lines.append("  其他待兑现承诺：")
                for c in non_urgent[:5]:  # Limit to 5 to save tokens
                    lines.append(f"  - {c.description}（涉及：{'、'.join(c.parties)}）")
        else:
            lines.append("🤝 [Unfulfilled Commitments — Violations cause story rejection]")
            lines.append("")
            lines.append("  🚨 [HARD RULES — Violations trigger regeneration]:")
            lines.append(
                "  1. Characters involved in commitments CANNOT act in ways that directly conflict"
            )
            lines.append(
                "  2. If a commitment involves character status (e.g., 'departed', 'hidden'), that character CANNOT change status without explanation"
            )
            lines.append("  3. Critical commitments MUST be properly addressed, cannot be ignored")
            lines.append("")
            if urgent:
                lines.append("  ❗ [Due soon or overdue] (MUST be addressed):")
                for c in urgent:
                    # ★ 关键承诺显示为"待兑现"而非"已过期"
                    if c.importance == "critical" and c.deadline_week <= self.current_week:
                        overdue = "[CRITICAL - MUST address or respond in this round]"
                    else:
                        overdue = (
                            "[OVERDUE! MUST explain or address in story]"
                            if c.deadline_week <= self.current_week
                            else f"(due week {c.deadline_week})"
                        )
                    lines.append(
                        f"  - [{c.importance}] {c.description} — parties: {', '.join(c.parties)} {overdue}"
                    )
            if non_urgent:
                lines.append("  Other pending commitments:")
                for c in non_urgent[:5]:
                    lines.append(f"  - {c.description} (parties: {', '.join(c.parties)})")
        return "\n".join(lines)

    def _build_causal_constraints(self, zh: bool) -> str:
        active = self.get_active_causal_chains()
        if not active:
            return ""
        lines = []
        if zh:
            lines.append("⚡ 【悬而未决的因果链】")
            for cc in active:
                chars = f"（涉及：{'、'.join(cc.characters)}）" if cc.characters else ""
                lines.append(f"  - 起因：{cc.cause} → 预期后果：{cc.expected_consequence}{chars}")
            lines.append("  ⚠️ 以上因果关系应在合适时机在故事中体现，不能被遗忘。")
        else:
            lines.append("[Pending Causal Chains]")
            for cc in active:
                chars = f" (characters: {', '.join(cc.characters)})" if cc.characters else ""
                lines.append(f"  - Cause: {cc.cause} -> Expected: {cc.expected_consequence}{chars}")
            lines.append(
                "  Warning: These cause-effect chains should manifest in the story at appropriate times."
            )
        return "\n".join(lines)

    def _build_physical_constraints(self, zh: bool) -> str:
        if not self.physical_states:
            return ""
        lines = []
        if zh:
            lines.append("🏥 【人物身体状态】")
            for name, ps in self.physical_states.items():
                recovery = ""
                if ps.expected_recovery_week > 0:
                    if ps.expected_recovery_week <= self.current_week:
                        recovery = "（预计已恢复）"
                    else:
                        recovery = f"（预计第{ps.expected_recovery_week}周恢复）"
                lines.append(f"  - {name}：{ps.condition}（{ps.severity}）{recovery}")
            lines.append("  ⚠️ 人物行为必须符合其身体状态，受伤的人不能做剧烈运动。")
        else:
            lines.append("[Character Physical States]")
            for name, ps in self.physical_states.items():
                recovery = ""
                if ps.expected_recovery_week > 0:
                    if ps.expected_recovery_week <= self.current_week:
                        recovery = " (expected recovered)"
                    else:
                        recovery = f" (recovery ~week {ps.expected_recovery_week})"
                lines.append(f"  - {name}: {ps.condition} ({ps.severity}){recovery}")
            lines.append("  Warning: Character actions must be consistent with physical state.")
        return "\n".join(lines)

    def _build_dynamic_facts_constraints(self, zh: bool) -> str:
        """Build constraint text from AI-identified dynamic facts."""
        from src.game.constants import IMPORTANCE_ORDER

        active_facts = [
            f
            for f in self.dynamic_facts
            if f.active
            and f.constraint_text
            and not contains_precise_financial_fact(
                f.fact_type,
                f.subject,
                f.description,
                f.constraint_text,
                f.source_excerpt,
            )
        ]
        if not active_facts:
            return ""

        # Sort by importance: critical > important > normal > minor
        active_facts.sort(key=lambda f: IMPORTANCE_ORDER.get(f.importance, 2))

        # Limit to top 15 to save tokens
        display_facts = active_facts[:15]

        lines = []
        if zh:
            lines.append("🔍 【AI识别的世界状态约束】")
            for f in display_facts:
                importance_label = {
                    "critical": "⚠️必须遵守",
                    "important": "重要",
                    "normal": "",
                    "minor": "参考",
                }.get(f.importance, "")
                prefix = f"[{importance_label}] " if importance_label else ""
                lines.append(f"  - {prefix}{f.constraint_text}")
            lines.append("  ⚠️ 以上约束由AI从历史故事中自动提取，请在生成故事时严格遵守。")
        else:
            lines.append("[AI-Identified World State Constraints]")
            for f in display_facts:
                importance_label = {
                    "critical": "MUST follow",
                    "important": "Important",
                    "normal": "",
                    "minor": "Reference",
                }.get(f.importance, "")
                prefix = f"[{importance_label}] " if importance_label else ""
                lines.append(f"  - {prefix}{f.constraint_text}")
            lines.append(
                "  Warning: Above constraints were auto-extracted from story history. Strictly follow them."
            )
        return "\n".join(lines)

    def _build_character_profile_constraints(self, zh: bool) -> str:
        """Build constraint text from character behavioral profiles.

        Only includes profiles with evidence_count >= 2 (have been confirmed
        across at least 2 synthesis cycles, meaning ≥ 2 weeks of story evidence).
        """
        established = {
            name: p
            for name, p in self.character_profiles.items()
            if p.evidence_count >= 2 and p.constraint_text
        }
        if not established:
            return ""

        lines = []
        if zh:
            lines.append("🎭 【角色行为画像 — 性格一致性约束】")
            for name, p in established.items():
                level = "⚠️ 严格约束" if p.evidence_count >= 4 else "重要参考"
                lines.append(f"  [{level}] {name}：")
                lines.append(f"    {p.constraint_text}")
                if p.behavioral_boundaries:
                    lines.append(f"    ❌ 绝对不会：{'；'.join(p.behavioral_boundaries[:3])}")
            lines.append(
                "  ⚠️ 以上画像由AI从多轮故事中归纳而成。角色的言行举止、决策方式、情绪表达"
            )
            lines.append("  必须与画像一致。如需角色成长/转变，必须有明确的故事契机和过渡铺垫。")
        else:
            lines.append("[Character Behavioral Profiles — Personality Consistency Constraints]")
            for name, p in established.items():
                level = "STRICT" if p.evidence_count >= 4 else "Important"
                lines.append(f"  [{level}] {name}:")
                lines.append(f"    {p.constraint_text}")
                if p.behavioral_boundaries:
                    lines.append(f"    NEVER: {'; '.join(p.behavioral_boundaries[:3])}")
            lines.append(
                "  Warning: Profiles were synthesized from multiple story rounds. Character speech,"
            )
            lines.append(
                "  behavior, decisions, and emotions MUST be consistent. Any growth/change needs explicit story justification."
            )
        return "\n".join(lines)

    # -------------------- Serialization --------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize world model data for storage in PlayerState.world_model_data."""
        return {
            "character_locations": {
                n: loc.to_dict() for n, loc in self.character_locations.items()
            },
            "career_records": {n: cr.to_dict() for n, cr in self.career_records.items()},
            "active_commitments": [c.to_dict() for c in self.active_commitments],
            "causal_chains": [cc.to_dict() for cc in self.causal_chains],
            "physical_states": {n: ps.to_dict() for n, ps in self.physical_states.items()},
            "dynamic_facts": [
                df.to_dict()
                for df in self.dynamic_facts
                if hasattr(df, "to_dict")
                and not contains_precise_financial_fact(
                    getattr(df, "fact_type", ""),
                    getattr(df, "subject", ""),
                    getattr(df, "description", ""),
                    getattr(df, "constraint_text", ""),
                    getattr(df, "source_excerpt", ""),
                )
            ],
            "character_profiles": {n: cp.to_dict() for n, cp in self.character_profiles.items()},
            "location_graph": self.location_graph,
            "required_cast": self.required_cast,
            "character_knowledge_sets": {
                n: list(ks) for n, ks in self.character_knowledge_sets.items()
            },
        }


# ==================== Helpers ====================


def _extract_region(location_text: str) -> str:
    """Extract a coarse-grained region name from a location string.

    Heuristic: take the first 2-3 characters that look like a city/province name.
    For strings like '北京市朝阳区' -> '北京', '上海浦东' -> '上海'.
    """
    # Common Chinese city prefixes (2-char)
    common_prefixes = [
        "北京",
        "上海",
        "广州",
        "深圳",
        "天津",
        "重庆",
        "成都",
        "杭州",
        "武汉",
        "南京",
        "西安",
        "长沙",
        "苏州",
        "郑州",
        "东莞",
        "青岛",
        "沈阳",
        "大连",
        "厦门",
        "昆明",
        "贵阳",
        "福州",
        "济南",
        "哈尔滨",
        "长春",
        "合肥",
        "南宁",
        "太原",
        "石家庄",
        "兰州",
        "乌鲁木齐",
        "呼和浩特",
        "拉萨",
        "银川",
        "西宁",
        "海口",
        "香港",
        "澳门",
        "台北",
    ]
    for prefix in common_prefixes:
        if prefix in location_text:
            return prefix

    # Fallback: return first 2 chars (often the city name)
    return location_text[:2] if len(location_text) >= 2 else location_text
