"""Story generation service.

Handles the core story text generation (Step 1 of the two-stage pipeline),
consistency validation with retry, and life-phase determination.
"""

import json
import logging
import os
from typing import Any, Callable, Dict, Optional

from pydantic import ValidationError

from config.feature_flags import get_feature
from config.prompts import get_round_event_prompt, get_story_only_prompt
from config.prompts._helpers import extract_overused_phrases
from src.ai.client import AIClient
from src.ai.models import EventOption, GameEvent
from src.ai.system_prompts import get_system_prompt
from src.ai.vector_store import get_vector_store, is_vector_search_enabled

logger = logging.getLogger(__name__)


def _normalize_punctuation(text: str, language: str = "zh") -> str:
    """将英文标点统一替换为中文标点，并进行繁简转换（仅中文模式）。"""
    if not text or language != "zh":
        return text

    # ★ 繁简转换：AI 模型偶尔输出繁体字，统一转为简体
    try:
        from opencc import OpenCC

        converter = OpenCC("t2s")
        text = converter.convert(text)
        # 补充 opencc 未覆盖的异体字映射
        _VARIANT_MAP = {
            "擡": "抬",
            "裏": "里",
        }
        for variant, standard in _VARIANT_MAP.items():
            text = text.replace(variant, standard)
    except Exception:
        pass  # opencc 不可用时静默跳过

    # 成对引号需要交替处理
    result = []
    dquote_open = False
    squote_open = False
    for ch in text:
        if ch in ('"', '"'):
            ch = "“" if not dquote_open else "”"
            dquote_open = not dquote_open
        elif ch in ("'", "'"):
            ch = "‘" if not squote_open else "’"
            squote_open = not squote_open
        result.append(ch)
    text = "".join(result)

    # 直接映射替换
    replacements = {
        ",": "，",
        ".": "。",
        "!": "！",
        "?": "？",
        ":": "：",
        ";": "；",
        "(": "（",
        ")": "）",
    }
    for en, zh in replacements.items():
        text = text.replace(en, zh)

    # 省略号规范化（含中文句号省略号）
    text = text.replace("...", "……").replace("..", "……")
    text = text.replace("。。。", "……")

    # 清理中文标点后多余的空格
    import re

    text = re.sub(r"""([，。！？：；、……""''（）])\s+""", r"\1", text)

    return text


class StoryGenerator:
    """Generates story text for events and rounds."""

    def __init__(self, client: AIClient, quality_level=None):
        self.client = client

        # ★ 质量级别配置
        from src.ai.harness.quality_level import PROFILES, QualityLevel

        if quality_level is None:
            quality_level = QualityLevel.EXPERT
        elif isinstance(quality_level, str):
            quality_level = QualityLevel(quality_level)
        self.quality_level = quality_level
        self.harness_profile = PROFILES[self.quality_level]

        # Harness 约束监控系统（通过环境变量控制）
        self._harness_enabled = os.environ.get("ENABLE_CONSTRAINT_HARNESS", "").lower() in (
            "true",
            "1",
            "yes",
        )
        self._harness_registry: Any = None
        self._preflight_checker: Any = None
        self._validation_pipeline: Any = None
        self._diagnostics: Any = None
        self._retry_controller: Any = None
        self._harness_metrics: Any = None
        self._polish_controller: Any = None
        self._master_retry_counts: Dict[str, int] = {}
        self._last_retry_key: Optional[str] = None

        if self._harness_enabled:
            try:
                from src.ai.harness import default_registry
                from src.ai.harness.diagnostics import \
                    ConstraintViolationDiagnostic
                from src.ai.harness.metrics import HarnessMetrics
                from src.ai.harness.preflight_checker import PreflightChecker
                from src.ai.harness.retry_controller import RetryController
                from src.ai.harness.validation_pipeline import \
                    ValidationPipeline

                self._harness_registry = default_registry
                self._preflight_checker = PreflightChecker(default_registry)
                self._validation_pipeline = ValidationPipeline(default_registry)
                self._diagnostics = ConstraintViolationDiagnostic()
                self._retry_controller = RetryController(profile=self.harness_profile)
                self._harness_metrics = HarnessMetrics()
                if self.harness_profile.enable_polish:
                    from src.ai.harness.polish_controller import \
                        PolishController

                    self._polish_controller = PolishController(client=self.client)
                logger.info(
                    f"Constraint Harness system initialized successfully "
                    f"(quality_level={self.quality_level.value})"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Constraint Harness: {e}")
                self._harness_enabled = False

        # ★ 三大叙事系统环境变量控制
        self._style_engine_enabled = (
            os.environ.get("ENABLE_NARRATIVE_STYLE_ENGINE", "false").lower() == "true"
        )
        self._creative_enabled = (
            os.environ.get("ENABLE_CREATIVE_ENHANCEMENT", "false").lower() == "true"
        )
        self._epic_enabled = os.environ.get("ENABLE_EPIC_NARRATIVE", "false").lower() == "true"

        # 延迟初始化（在有 style_id 时初始化）
        self._style_manifest: Any = None
        self._prompt_builder: Any = None
        self._style_validator: Any = None
        self._character_arc_engine: Any = None
        self._world_breathing_engine: Any = None
        self._conflict_tower: Any = None
        self._fate_echo_db: Any = None
        self._emotional_arc: Any = None
        self._novelty_scorer: Any = None
        self._foreshadowing_lib: Any = None
        self._hook_injector: Any = None
        self._preference_learner: Any = None
        self._narrative_systems_initialized = False

    # -------------------- Narrative Systems --------------------

    def _init_narrative_systems(self, style_id: str, player_state: Dict[str, Any]) -> None:
        """根据 style_id 初始化三大叙事系统（延迟初始化，首次调用时执行）。

        非侵入式：任何子系统初始化失败只 logger.warning()，不影响核心流程。
        """
        if self._narrative_systems_initialized:
            return

        self._narrative_systems_initialized = True

        # --- 风格引擎 ---
        if self._style_engine_enabled:
            try:
                from src.ai.narrative.style_manifest import get_style
                from src.ai.narrative.style_prompt_builder import \
                    StyleAwarePromptBuilder
                from src.ai.narrative.style_validator import \
                    StyleAwareValidator

                self._style_manifest = get_style(style_id)
                if not self._style_manifest and not style_id:
                    # Use default style when no style_id is matched
                    self._style_manifest = get_style("chinese_classic_saga")
                    logger.info("Using default style: chinese_classic_saga")
                if self._style_manifest:
                    self._prompt_builder = StyleAwarePromptBuilder(self._style_manifest)
                    self._style_validator = StyleAwareValidator(self._style_manifest)
                    logger.info(f"Style engine initialized: {self._style_manifest.style_id}")
                else:
                    logger.warning(f"Style '{style_id}' not found, style engine disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize style engine: {e}")

        # --- 史诗叙事 ---
        if self._epic_enabled:
            try:
                from src.ai.narrative.character_arc import CharacterArcEngine

                self._character_arc_engine = CharacterArcEngine(style=self._style_manifest)
                arc_state = player_state.get("character_arc_state")
                if arc_state and hasattr(self._character_arc_engine, "from_state_dict"):
                    self._character_arc_engine.from_state_dict(arc_state)
            except Exception as e:
                logger.warning(f"Failed to init CharacterArcEngine: {e}")

            try:
                from src.ai.narrative.world_breathing import \
                    WorldBreathingEngine

                era = ""
                cs = player_state.get("character_settings") or {}
                if isinstance(cs, dict) and "era" in cs:
                    era = cs["era"].get("era_description", "modern")
                self._world_breathing_engine = WorldBreathingEngine(
                    style=self._style_manifest, era=era
                )
                wb_state = player_state.get("world_breathing_events")
                if wb_state and hasattr(self._world_breathing_engine, "from_state_list"):
                    self._world_breathing_engine.from_state_list(wb_state)
            except Exception as e:
                logger.warning(f"Failed to init WorldBreathingEngine: {e}")

            try:
                from src.ai.narrative.conflict_tower import ConflictTower

                self._conflict_tower = ConflictTower(style=style_id or None)
                ct_state = player_state.get("conflict_tower_state")
                if ct_state and hasattr(self._conflict_tower, "from_state_dict"):
                    self._conflict_tower.from_state_dict(ct_state)
            except Exception as e:
                logger.warning(f"Failed to init ConflictTower: {e}")

            try:
                from src.ai.narrative.fate_echo import FateEchoDatabase

                self._fate_echo_db = FateEchoDatabase(style=self._style_manifest)
                fe_state = player_state.get("fate_echo_state")
                if fe_state and hasattr(self._fate_echo_db, "from_state_list"):
                    self._fate_echo_db.from_state_list(fe_state)
            except Exception as e:
                logger.warning(f"Failed to init FateEchoDatabase: {e}")

        # --- 创意增强 ---
        if self._creative_enabled:
            try:
                from src.ai.creative.emotional_arc import EmotionalArcAnalyzer

                self._emotional_arc = EmotionalArcAnalyzer()
            except Exception as e:
                logger.warning(f"Failed to init EmotionalArcAnalyzer: {e}")
            try:
                from src.ai.creative.novelty_scorer import NoveltyScorer

                self._novelty_scorer = NoveltyScorer()
            except Exception as e:
                logger.warning(f"Failed to init NoveltyScorer: {e}")
            try:
                from src.ai.creative.foreshadowing_tech import (
                    ForeshadowingTechniqueLibrary, HookInjector)

                self._foreshadowing_lib = ForeshadowingTechniqueLibrary()
                self._hook_injector = HookInjector()
            except Exception as e:
                logger.warning(f"Failed to init ForeshadowingTechniqueLibrary: {e}")
            try:
                from src.ai.creative.preference_learner import \
                    PreferenceLearner

                self._preference_learner = PreferenceLearner()
            except Exception as e:
                logger.warning(f"Failed to init PreferenceLearner: {e}")

        logger.info(
            f"Narrative systems init: style={self._style_engine_enabled}, "
            f"epic={self._epic_enabled}, creative={self._creative_enabled}"
        )

    def _gather_narrative_hints(
        self,
        player_state: Dict[str, Any],
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """收集所有叙事系统产出的 hint 文本，供 prompt 构建使用。"""
        hints: Dict[str, str] = {}

        if self._style_engine_enabled and self._prompt_builder:
            try:
                from config.prompts._helpers import \
                    _build_style_constraints_text

                hints["style_constraints"] = _build_style_constraints_text(
                    self._prompt_builder, "zh"
                )
            except Exception as e:
                logger.warning(f"Style constraints build failed: {e}")

            # 章节开头/结尾约束
            if self._style_engine_enabled and self._prompt_builder:
                try:
                    # 章节开头约束
                    previous_summary = ""
                    dh = player_state.get("decision_history", [])
                    if dh and isinstance(dh[-1], dict):
                        previous_summary = dh[-1].get("event", "")[:200]
                    chapter_opening = self._prompt_builder.build_chapter_opening(previous_summary)
                    if chapter_opening:
                        hints["chapter_opening"] = chapter_opening

                    # 章节结尾约束
                    chapter_ending = self._prompt_builder.build_chapter_ending_hint()
                    if chapter_ending:
                        hints["chapter_ending"] = chapter_ending

                    # 三幕结构提示
                    hints["three_act_hint"] = (
                        "[SHOULD] 戏剧结构: 本段故事应有清晰的起承转合——开头铺垫引入情境，中段推进发展或制造转折，结尾收束或留下悬念。"
                    )
                except Exception as e:
                    logger.warning(f"Chapter hints build failed: {e}")

        if self._epic_enabled:
            if self._character_arc_engine:
                try:
                    from config.prompts._helpers import _build_arc_context

                    player_name = self._extract_player_name(player_state)
                    hints["arc_hint"] = _build_arc_context(self._character_arc_engine, player_name)
                except Exception as e:
                    logger.warning(f"Arc hint build failed: {e}")

            if self._conflict_tower:
                try:
                    hints["conflict_directive"] = self._conflict_tower.get_conflict_directive()
                except Exception as e:
                    logger.warning(f"Conflict directive failed: {e}")

            if self._world_breathing_engine:
                try:
                    week = player_state.get("week", 0)
                    self._world_breathing_engine.advance_to_week(week)
                    active = self._world_breathing_engine.get_active_events(week)
                    snippets = []
                    for ev in active[:3]:
                        eid = ev.get("id", "")
                        if eid:
                            s = self._world_breathing_engine.generate_permeation_snippet(eid)
                            if s:
                                snippets.append(s)
                    if snippets:
                        hints["world_event_context"] = "\n".join(snippets)
                except Exception as e:
                    logger.warning(f"World event context failed: {e}")

            if self._fate_echo_db:
                try:
                    week = player_state.get("week", 0)
                    pending = self._fate_echo_db.get_pending_echoes(week)
                    if pending:
                        prop_id = pending[0].get("id", "")
                        style_key = self._style_manifest.style_id if self._style_manifest else None
                        if prop_id:
                            hint = self._fate_echo_db.generate_echo_hint(prop_id, style=style_key)
                            if hint:
                                hints["fate_echo_hint"] = hint
                except Exception as e:
                    logger.warning(f"Fate echo hint failed: {e}")

        if self._creative_enabled:
            if self._preference_learner:
                try:
                    decision_history = player_state.get("decision_history", [])
                    prefs = self._preference_learner.learn(decision_history)
                    style_key = self._style_manifest.style_id if self._style_manifest else None
                    hints["preference_hint"] = self._preference_learner.build_preference_hint(
                        prefs, style=style_key
                    )
                except Exception as e:
                    logger.warning(f"Preference hint failed: {e}")

            if self._foreshadowing_lib and activated_foreshadowing:
                try:
                    style_key = self._style_manifest.style_id if self._style_manifest else ""
                    hints["foreshadowing_technique_hint"] = (
                        self._foreshadowing_lib.build_recovery_hint(
                            activated_foreshadowing, style=style_key
                        )
                    )
                except Exception as e:
                    logger.warning(f"Foreshadowing technique hint failed: {e}")

            # 节奏平坦检测与主动干预
            if self._emotional_arc:
                try:
                    recent_texts = [
                        d.get("event", "")
                        for d in player_state.get("decision_history", [])[-3:]
                        if isinstance(d, dict) and d.get("event")
                    ]
                    if len(recent_texts) >= 3:
                        style_key = self._style_manifest.style_id if self._style_manifest else None
                        is_flat = self._emotional_arc.detect_flatline(recent_texts, style=style_key)
                        if is_flat:
                            intervention = self._emotional_arc.suggest_intervention(
                                history=recent_texts, style=style_key
                            )
                            if intervention:
                                hints["pacing_intervention"] = f"[MUST] 节奏干预: {intervention}"
                                logger.info("Pacing flatline detected, intervention injected")
                except Exception as e:
                    logger.warning(f"Pacing intervention check failed: {e}")

        return hints

    def _post_generation_analysis(self, story_text: str, player_state: Dict[str, Any]) -> None:
        """生成后分析：情感弧线、新颖度、弧光更新（非阻塞）。"""
        if self._creative_enabled:
            if self._emotional_arc and story_text:
                try:
                    self._emotional_arc.analyze(story_text)
                except Exception as e:
                    logger.warning(f"Emotional arc analysis failed: {e}")
            if self._novelty_scorer and story_text:
                try:
                    history = [
                        d.get("event", "")
                        for d in player_state.get("decision_history", [])
                        if isinstance(d, dict) and d.get("event")
                    ]
                    self._novelty_scorer.score(story_text, history)
                except Exception as e:
                    logger.warning(f"Novelty scoring failed: {e}")

        if self._epic_enabled and self._character_arc_engine and story_text:
            try:
                player_name = self._extract_player_name(player_state)
                if player_name:
                    arc = self._character_arc_engine.arcs.get(player_name)
                    if arc:
                        self._character_arc_engine.process_event(arc, {"story_text": story_text})
            except Exception as e:
                logger.warning(f"Character arc update failed: {e}")

    def _resolve_temperature(
        self,
        attempt: int,
        base_temperature: float,
        temperature_decay: float,
        scene_type: str = "",
    ) -> float:
        """温度优先级链：
        1. Harness 重试温度（attempt>0 时递减）
        2. StyleManifest.global_parameters.temperature
        3. temperature_schedule（场景类型微调）
        4. PreferenceLearner 调节
        5. 默认 base_temperature
        """
        if attempt > 0:
            return max(0.7, base_temperature - (attempt * temperature_decay))

        if self._style_engine_enabled and self._style_manifest:
            try:
                style_temp = self._style_manifest.global_parameters.temperature
                if style_temp and style_temp != 0.85:
                    if scene_type and self._prompt_builder:
                        try:
                            sched = self._prompt_builder.get_scene_temperature(scene_type)
                            if sched != style_temp:
                                return float(sched)
                        except Exception:
                            pass
                    return float(style_temp)
            except Exception:
                pass

        if self._creative_enabled and self._preference_learner:
            try:
                adjusted = self._preference_learner.adjust_temperature(base_temperature)
                if adjusted != base_temperature:
                    return float(adjusted)
            except Exception:
                pass

        return base_temperature

    @staticmethod
    def _extract_player_name(player_state: Dict[str, Any]) -> str:
        """从 player_state 中提取主角名称。"""
        name = player_state.get("player_name", "")
        if not name:
            cs = player_state.get("character_settings") or {}
            if isinstance(cs, dict):
                identity = cs.get("identity", {})
                if isinstance(identity, dict):
                    name = identity.get("name", "")
        return str(name)

    # -------------------- Public API --------------------

    def generate_event(
        self,
        player_state: Dict[str, Any],
        language: str = "en",
        retry_count: int = 3,
        character_settings: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        four_week_summary: Optional[str] = None,
        yearly_summary: Optional[str] = None,
        opening_story: Optional[str] = None,
        last_event_description: Optional[str] = None,
        game_date_info: Optional[Dict[str, Any]] = None,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        last_event_concluded: bool = True,
        last_round_full_story: str = "",
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
        character_habits: Optional[list] = None,
        option_generator=None,
        cache=None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> GameEvent:
        """
        Generate a game event (story + options) based on player state.

        Two-stage pipeline:
          Step 1: Generate pure story text (this class)
          Step 2: Generate options based on the story (OptionGenerator)

        Args:
            player_state: Current player state dictionary
            language: Language code ('en' or 'zh')
            retry_count: Number of retries on failure
            character_settings: Optional character settings
            stream_callback: Optional streaming callback
            four_week_summary: Recent 4-week summary for context
            yearly_summary: Yearly summary for context
            opening_story: Opening story text for continuity
            last_event_description: Last event description for continuity
            game_date_info: Game-internal date info
            pending_storylines: Pending storylines for continuity
            established_facts: Established world facts for consistency
            last_event_concluded: Whether last event was concluded
            last_round_full_story: Full story of last round
            activated_foreshadowing: Activated foreshadowing seed
            character_habits: Character habits for behavioral consistency
            option_generator: OptionGenerator instance for Step 2
            cache: EventCache instance for caching results

        Returns:
            GameEvent object

        Raises:
            ValueError: If generation fails after retries
        """
        current_phase = self._get_phase_from_state(player_state)

        # Derive last_event_description from decision history if not provided
        if not last_event_description:
            decision_history = player_state.get("decision_history", [])
            if decision_history:
                last_event_description = decision_history[-1].get("event")

        # ★ 向量检索：获取相关历史片段
        vector_context = ""
        if is_vector_search_enabled():
            try:
                vector_store = get_vector_store()
                # 使用当前情境作为查询
                query_context = last_event_description or ""
                if pending_storylines:
                    query_context += " " + " ".join(str(s) for s in pending_storylines[:3])
                vector_context = vector_store.get_relevant_context(query_context, max_chars=1500)
                if vector_context:
                    logger.info(
                        f"[VectorStore] Injected {len(vector_context)} chars of vector context"
                    )
            except Exception as e:
                logger.error(f"Vector search failed, constraint degraded: {e}")
                vector_context = (
                    "[注意: 历史上下文检索暂不可用，请完全基于已提供的约束信息生成故事]"
                )

        # ★ 动态提取历史故事中的高频重复短语，生成禁用列表
        decision_history = player_state.get("decision_history", [])
        overused_phrases = extract_overused_phrases(decision_history, language=language)
        if overused_phrases:
            logger.info(f"[AntiRepeat] Injected dynamic ban list ({len(overused_phrases)} chars)")

        # ★ 叙事系统初始化 + hint 收集
        narrative_hints: Dict[str, str] = {}
        style_id = player_state.get("narrative_style_id") or (character_settings or {}).get(
            "narrative_style_id", ""
        )
        self._init_narrative_systems(style_id, player_state)
        narrative_hints = self._gather_narrative_hints(
            player_state, activated_foreshadowing=activated_foreshadowing
        )

        story_prompt = get_story_only_prompt(
            player_state,
            language,
            current_phase,
            character_settings,
            opening_story,
            last_event_description,
            four_week_summary,
            yearly_summary,
            game_date_info,
            pending_storylines,
            established_facts,
            last_event_concluded,
            last_round_full_story,
            activated_foreshadowing,
            character_habits,
            vector_context=vector_context,  # ★ 注入向量检索上下文
            overused_phrases=overused_phrases,  # ★ 注入动态禁用列表
            quality_level=self.quality_level.value,  # ★ 注入质量级别约束
            player_name=self._extract_player_name(player_state),  # ★ 注入主角名称
            **narrative_hints,  # ★ 注入叙事系统 hints
        )

        # ★ 约束完整性检查
        self._log_constraint_completeness(story_prompt)

        # ★ Harness: 位置A — preflight 检查（构建 prompt 之后、调用 AI 之前）
        preflight_result = None
        validation_context = None
        if self._harness_enabled:
            try:
                validation_context = self._extract_validation_context(
                    player_state,
                    character_settings,
                    pending_storylines,
                    established_facts,
                    last_event_description,
                    character_habits=character_habits,
                )
                validation_context["narrative_hints"] = narrative_hints
                preflight_result = self._preflight_checker.check_prompt_completeness(
                    story_prompt, validation_context
                )
                if not preflight_result.all_present:
                    logger.warning(
                        f"Harness preflight: missing {preflight_result.missing_constraints}"
                    )
            except Exception as e:
                logger.warning(f"Harness preflight check failed: {e}")

        sys_prompt = get_system_prompt("story_novelist", language)
        last_error: Optional[str] = None

        # ★ StateTracker: 跟踪生成过程的状态变化
        state_tracker = None
        if get_feature("generation_state_tracking"):
            try:
                from src.ai.generation_state import (StateTracker,
                                                     TransitionReason)

                state_tracker = StateTracker(
                    initial_model=getattr(self.client, "model", ""),
                    initial_temperature=0.85,
                )
            except Exception as e:
                logger.warning(f"Failed to create StateTracker: {e}")

        # ★ ReactiveCompressor: 上下文超限时自动压缩
        reactive_compressor = None
        if get_feature("reactive_compression"):
            try:
                from src.ai.reactive_compressor import ReactiveCompressor

                reactive_compressor = ReactiveCompressor()
            except Exception as e:
                logger.warning(f"Failed to create ReactiveCompressor: {e}")

        # ★ 优化：使用渐进式温度策略
        # - 初次生成：0.85 (平衡创意性与准确性)
        # - 第一次重试：0.75 (更保守)
        # - 第二次重试：0.7 (最保守，确保符合约束)
        base_temperature = 0.85
        temperature_decay = 0.15  # 每次重试降低 0.15

        for attempt in range(retry_count):
            try:
                # Step 1: Generate story text (pure narrative, no JSON)
                prompt = story_prompt
                if attempt > 0 and last_error:
                    if language == "zh":
                        prompt += f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题。】"
                    else:
                        prompt += f"\n\n[Previous attempt failed: {last_error}. Please avoid the same issue.]"

                # ★ 温度优先级链：Harness重试 > Style > Schedule > Preference > 默认
                current_temp = self._resolve_temperature(
                    attempt, base_temperature, temperature_decay
                )

                # ★ StateTracker: 记录温度调整
                if state_tracker and attempt > 0:
                    try:

                        state_tracker.transition(
                            TransitionReason.TEMPERATURE_ADJUST,
                            temperature=current_temp,
                        )
                    except Exception:
                        pass

                logger.info(
                    f"Story generation attempt {attempt + 1}/{retry_count}, temperature={current_temp}"
                )

                # Only stream on first attempt
                cb = stream_callback if attempt == 0 else None
                story_text = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=prompt,
                    temperature=current_temp,  # ★ 动态调整温度
                    max_tokens=8192,
                    stream_callback=cb,
                    frequency_penalty=0.3,  # ★ 惩罚重复词汇，减少车轲辘话
                    presence_penalty=0.3,  # ★ 鼓励使用新词汇/新主题
                )

                story_text = story_text.strip()
                story_text = _normalize_punctuation(story_text, language)
                logger.info(f"Generated story with {len(story_text)} characters")
                logger.debug(f"Story preview (first 200 chars): {story_text[:200]}...")
                logger.debug(f"Story preview (last 200 chars): ...{story_text[-200:]}")

                # ★ Harness: 位置B — AI 生成故事文本之后
                if self._harness_enabled and story_text and validation_context:
                    try:
                        import time as _time

                        _harness_start = _time.time()

                        harness_validation = self._validation_pipeline.validate(
                            story_text, validation_context
                        )

                        if not harness_validation.passed:
                            diagnostic_report = self._diagnostics.generate_report(
                                story_text, harness_validation
                            )
                            should_retry, correction_hint = self._retry_controller.should_retry(
                                harness_validation, diagnostic_report, attempt=attempt
                            )

                            if should_retry and correction_hint:
                                logger.warning(
                                    f"Harness recommends retry: "
                                    f"{len(harness_validation.critical_failures)} critical failures"
                                )
                                # 将修正指令追加到下一次重试的 prompt 中
                                last_error = correction_hint

                        _harness_latency = (_time.time() - _harness_start) * 1000

                        # 记录 metrics
                        self._harness_metrics.record_generation(
                            game_id=(
                                player_state.get("game_id")
                                if isinstance(player_state, dict)
                                else getattr(player_state, "game_id", None)
                            ),
                            week=(
                                player_state.get("current_week")
                                if isinstance(player_state, dict)
                                else getattr(player_state, "current_week", None)
                            ),
                            attempts=attempt + 1,
                            preflight_result=(
                                {
                                    "all_present": preflight_result.all_present,
                                    "missing_constraints": preflight_result.missing_constraints,
                                }
                                if preflight_result
                                else None
                            ),
                            validation_result={
                                "passed": harness_validation.passed,
                                "score": harness_validation.score,
                                "detailed_checks": harness_validation.detailed_checks,
                            },
                            latency_ms=_harness_latency,
                        )

                        # 如果 harness 建议重试且有修正指令，跳过本次直接进入下一轮
                        if not harness_validation.passed and last_error == correction_hint:
                            if attempt < retry_count - 1:
                                # ★ StateTracker: 记录 harness 重试
                                if state_tracker:
                                    try:
                                        from src.ai.generation_state import \
                                            TransitionReason

                                        state_tracker.transition(
                                            TransitionReason.HARNESS_RETRY,
                                            metrics={"harness_score": harness_validation.score},
                                        )
                                    except Exception:
                                        pass

                                # ★ ReactiveCompressor: harness 重试时压缩上下文
                                if reactive_compressor:
                                    try:
                                        prompt_tokens = reactive_compressor.estimate_tokens(prompt)
                                        if reactive_compressor.should_compact(prompt_tokens, 8192):
                                            compact_texts = {
                                                k: v for k, v in narrative_hints.items() if v
                                            }
                                            if vector_context:
                                                compact_texts["vector_context"] = vector_context
                                            if overused_phrases:
                                                compact_texts["overused_phrases"] = overused_phrases
                                            result = reactive_compressor.compact(compact_texts)
                                            logger.info(
                                                f"ReactiveCompressor: {result.original_token_count} -> "
                                                f"{result.compressed_token_count} tokens, "
                                                f"removed: {result.removed_sections}"
                                            )
                                            if state_tracker:
                                                try:
                                                    from src.ai.generation_state import \
                                                        TransitionReason

                                                    state_tracker.transition(
                                                        TransitionReason.CONTEXT_COMPACT,
                                                        context_budget_factor=result.budget_factor,
                                                    )
                                                except Exception:
                                                    pass
                                    except Exception as e:
                                        logger.warning(
                                            f"ReactiveCompressor failed (non-blocking): {e}"
                                        )

                                logger.info(f"Harness triggered retry (attempt {attempt + 1})")
                                continue
                    except Exception as e:
                        logger.warning(f"Harness post-validation failed (non-blocking): {e}")

                # ★ 叙事系统后处理（非阻塞）
                self._post_generation_analysis(story_text, player_state)

                # Step 2: Generate options based on the story
                if option_generator is None:
                    raise ValueError("option_generator is required")

                if status_callback:
                    status_callback("generating_options")

                logger.info("Step 2: Generating options based on the story...")
                event = option_generator.generate_options_only(
                    story_description=story_text,
                    player_state=player_state,
                    character_settings=character_settings,
                    language=language,
                    retry_count=retry_count,
                )
                logger.info(f"Generated {len(event.options)} options")
                for i, opt in enumerate(event.options):
                    logger.info(f"Option {i+1}: {opt.text}")

                # Validate and fix relationship names
                option_generator.validate_and_fix_relationships(event, character_settings)

                # Validate event quality
                option_generator.validate_event_quality(event)

                # Cache the event
                if cache:
                    cache.set(player_state, language, event)

                logger.info(f"Successfully generated event with {len(event.options)} options")

                # ★ StateTracker: 将状态机 metrics 附加到 event
                if state_tracker:
                    try:
                        state_metrics = state_tracker.to_metrics()
                        if not hasattr(event, "metadata"):
                            event.metadata = {}
                        if isinstance(getattr(event, "metadata", None), dict):
                            event.metadata["generation_state"] = state_metrics
                        logger.debug(f"StateTracker metrics: {state_metrics}")
                    except Exception as e:
                        logger.warning(f"Failed to attach state metrics: {e}")

                return event  # type: ignore[no-any-return]

            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == retry_count - 1:
                    raise ValueError(
                        f"Failed to generate valid event after {retry_count} attempts: {e}"
                    )
                continue

            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error during event generation: {e}")
                if attempt == retry_count - 1:
                    raise ValueError(f"Event generation failed: {e}")
                continue

        raise ValueError("Event generation failed after all retries")

    def generate_round_event(
        self,
        player_state: Dict[str, Any],
        language: str,
        round_number: int,
        round_context: str,
        character_settings: Optional[Dict[str, Any]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        relationship_events: Optional[list] = None,
        historical_weekly_summary: Optional[str] = None,
        historical_yearly_summary: Optional[str] = None,
        game_date_info: Optional[Dict[str, Any]] = None,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        last_event_concluded: bool = True,
        last_round_full_story: str = "",
        activated_foreshadowing: Optional[Dict[str, Any]] = None,
        character_habits: Optional[list] = None,
        world_model=None,
        option_generator=None,
        new_character: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> GameEvent:
        """
        Generate a single round's story and options.

        Args:
            player_state: Current player state dictionary
            language: Language code ('zh' or 'en')
            round_number: Round number within week (0=Mon, 1=Mid, 2=Weekend)
            round_context: Previous rounds' summaries and choices
            character_settings: Character background settings
            stream_callback: Optional callback for streaming story text
            relationship_events: Triggered relationship events
            historical_weekly_summary: Random historical weekly summary
            historical_yearly_summary: Random historical yearly summary
            game_date_info: Game-internal date info
            pending_storylines: Pending storylines for continuity
            established_facts: Established world facts for consistency
            last_event_concluded: Whether last event was concluded
            last_round_full_story: Full story of last round
            activated_foreshadowing: Activated foreshadowing seed
            character_habits: Character habits for behavioral consistency
            world_model: Optional WorldModel instance for consistency constraints
            option_generator: OptionGenerator instance for Step 2

        Returns:
            GameEvent with story and options
        """
        logger.info(
            f"Generating round event: round={round_number}, "
            f"context_length={len(round_context)}, "
            f"rel_events={len(relationship_events) if relationship_events else 0}, "
            f"stream_callback={stream_callback is not None}"
        )

        # ★ 向量检索：获取相关历史片段
        vector_context = ""
        if is_vector_search_enabled():
            try:
                vector_store = get_vector_store()
                # 使用当前情境作为查询
                query_context = round_context or ""
                if pending_storylines:
                    query_context += " " + " ".join(str(s) for s in pending_storylines[:3])
                vector_context = vector_store.get_relevant_context(query_context, max_chars=1500)
                if vector_context:
                    logger.info(
                        f"[VectorStore] Injected {len(vector_context)} chars of vector context"
                    )
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # ★ 动态提取历史故事中的高频重复短语，生成禁用列表
        decision_history = player_state.get("decision_history", [])
        overused_phrases = extract_overused_phrases(decision_history, language=language)
        if overused_phrases:
            logger.info(
                f"[AntiRepeat] Round: Injected dynamic ban list ({len(overused_phrases)} chars)"
            )

        # ★ 叙事系统初始化 + hint 收集（round）
        narrative_hints_round: Dict[str, str] = {}
        style_id = player_state.get("narrative_style_id") or (character_settings or {}).get(
            "narrative_style_id", ""
        )
        self._init_narrative_systems(style_id, player_state)
        narrative_hints_round = self._gather_narrative_hints(
            player_state, activated_foreshadowing=activated_foreshadowing
        )

        # Get round story prompt
        prompt = get_round_event_prompt(
            player_state,
            language,
            round_number,
            round_context,
            character_settings,
            relationship_events=relationship_events,
            historical_weekly_summary=historical_weekly_summary,
            historical_yearly_summary=historical_yearly_summary,
            game_date_info=game_date_info,
            pending_storylines=pending_storylines,
            established_facts=established_facts,
            last_event_concluded=last_event_concluded,
            last_round_full_story=last_round_full_story,
            activated_foreshadowing=activated_foreshadowing,
            character_habits=character_habits,
            world_model=world_model,
            new_character=new_character,
            vector_context=vector_context,  # ★ 注入向量检索上下文
            overused_phrases=overused_phrases,  # ★ 注入动态禁用列表
            quality_level=self.quality_level.value,  # ★ 注入质量级别约束
            player_name=self._extract_player_name(player_state),  # ★ 注入主角名称
            **narrative_hints_round,  # ★ 注入叙事系统 hints
        )

        # Step 1: Generate story text (with optional streaming)
        sys_prompt = get_system_prompt("story_novelist", language)

        # ★ StateTracker: 跟踪 round 生成过程的状态变化
        state_tracker_round = None
        if get_feature("generation_state_tracking"):
            try:
                from src.ai.generation_state import StateTracker

                state_tracker_round = StateTracker(
                    initial_model=getattr(self.client, "model", ""),
                    initial_temperature=0.75,
                )
            except Exception as e:
                logger.warning(f"Failed to create StateTracker (round): {e}")

        # ★ ReactiveCompressor: round 级别的上下文压缩
        reactive_compressor_round = None
        if get_feature("reactive_compression"):
            try:
                from src.ai.reactive_compressor import ReactiveCompressor

                reactive_compressor_round = ReactiveCompressor()
            except Exception as e:
                logger.warning(f"Failed to create ReactiveCompressor (round): {e}")

        # ★ Harness: preflight 检查（generate_round_event）
        preflight_result = None
        validation_context = None
        if self._harness_enabled:
            try:
                validation_context = self._extract_validation_context(
                    player_state,
                    character_settings,
                    pending_storylines,
                    established_facts,
                    last_event_description=None,
                    character_habits=character_habits,
                )
                preflight_result = self._preflight_checker.check_prompt_completeness(
                    prompt, validation_context
                )
                if not preflight_result.all_present:
                    logger.warning(
                        f"Harness preflight (round): missing {preflight_result.missing_constraints}"
                    )
            except Exception as e:
                logger.warning(f"Harness preflight check failed (round): {e}")

        # ★ 动态温度策略：根据上下文调整温度
        # - 有未完结剧情线或上一轮未结束时，使用更保守的温度
        # - 新事件可以更有创意
        has_pending = pending_storylines and len(pending_storylines) > 0
        needs_continuation = not last_event_concluded
        if has_pending or needs_continuation:
            base_round_temp = 0.65  # 更保守，确保剧情连贯
        else:
            base_round_temp = 0.75  # 允许更多创意
        temperature_decay = 0.15

        # ★ 重试次数由质量级别决定
        retry_count = self.harness_profile.max_retries + 1
        last_error = None
        story_text = None
        best_story_text = ""  # 记录所有尝试中生成的最佳故事，避免全部失败后直接 fallback

        # 提前提取可用人物，供后续 option 校验使用
        from config.prompts._helpers import _collect_available_people
        from src.ai.quick_validator import quick_validate_story

        available_people_names = [
            p.get("name", "")
            for p in _collect_available_people(character_settings)
            if p.get("name")
        ]

        for attempt in range(retry_count):
            try:
                current_temp = self._resolve_temperature(
                    attempt, base_round_temp, temperature_decay
                )

                current_prompt = prompt
                if attempt > 0 and last_error:
                    if language == "zh":
                        current_prompt += (
                            f"\n\n【上次生成失败，原因：{last_error}。请避免同样的问题。】"
                        )
                    else:
                        current_prompt += f"\n\n[Previous attempt failed: {last_error}. Please avoid the same issue.]"

                logger.info(
                    f"Dynamic temperature: {current_temp} "
                    f"(pending={has_pending}, continuation={needs_continuation}, "
                    f"attempt={attempt + 1}/{retry_count})"
                )

                cb = stream_callback if attempt == 0 else None
                story_text = self.client.call(
                    system_prompt=sys_prompt,
                    user_prompt=current_prompt,
                    temperature=current_temp,
                    max_tokens=8192,
                    stream_callback=cb,
                    frequency_penalty=0.4,
                    presence_penalty=0.4,
                )
                logger.info(f"Generated round story with {len(story_text)} characters")
                story_text = _normalize_punctuation(story_text, language)

                # 记录最佳故事（即使后续校验失败，也保留作为最终 fallback）
                if len(story_text) > len(best_story_text):
                    best_story_text = story_text

                # Step 1.4: Quick rule-based validation
                quick_result = quick_validate_story(
                    story_text=story_text,
                    character_settings=character_settings,
                    available_people=available_people_names,
                    language=language,
                )

                if not quick_result.passed:
                    logger.warning(f"Quick validation failed: {quick_result.issues}")
                elif quick_result.warnings:
                    logger.info(f"Quick validation warnings: {quick_result.warnings}")

                # ★ Harness: 位置B — AI 生成故事文本之后（generate_round_event）
                harness_should_retry = False
                harness_correction = None
                if self._harness_enabled and story_text and validation_context:
                    try:
                        import time as _time

                        _harness_start = _time.time()

                        harness_validation = self._validation_pipeline.validate(
                            story_text, validation_context, profile=self.harness_profile
                        )

                        if not harness_validation.passed:
                            diagnostic_report = self._diagnostics.generate_report(
                                story_text, harness_validation
                            )
                            should_retry, correction_hint = self._retry_controller.should_retry(
                                harness_validation, diagnostic_report, attempt=attempt
                            )
                            if should_retry and correction_hint:
                                logger.warning(
                                    f"Harness (round) recommends retry: "
                                    f"{len(harness_validation.critical_failures)} critical failures"
                                )
                                harness_should_retry = True
                                harness_correction = correction_hint
                                # ★ StateTracker: 记录 round 级 harness 重试
                                if state_tracker_round:
                                    try:
                                        from src.ai.generation_state import \
                                            TransitionReason

                                        state_tracker_round.transition(
                                            TransitionReason.HARNESS_RETRY,
                                            metrics={"harness_score": harness_validation.score},
                                        )
                                    except Exception:
                                        pass

                                # ★ ReactiveCompressor: round 级 harness 重试时压缩上下文
                                if reactive_compressor_round:
                                    try:
                                        prompt_tokens = reactive_compressor_round.estimate_tokens(
                                            current_prompt
                                        )
                                        if reactive_compressor_round.should_compact(
                                            prompt_tokens, 8192
                                        ):
                                            compact_texts = {
                                                k: v for k, v in narrative_hints_round.items() if v
                                            }
                                            if vector_context:
                                                compact_texts["vector_context"] = vector_context
                                            if overused_phrases:
                                                compact_texts["overused_phrases"] = overused_phrases
                                            result = reactive_compressor_round.compact(
                                                compact_texts
                                            )
                                            logger.info(
                                                f"ReactiveCompressor (round): "
                                                f"{result.original_token_count} -> "
                                                f"{result.compressed_token_count} tokens, "
                                                f"removed: {result.removed_sections}"
                                            )
                                            if state_tracker_round:
                                                try:
                                                    state_tracker_round.transition(
                                                        TransitionReason.CONTEXT_COMPACT,
                                                        context_budget_factor=result.budget_factor,
                                                    )
                                                except Exception:
                                                    pass
                                    except Exception as e:
                                        logger.warning(
                                            f"ReactiveCompressor (round) failed (non-blocking): {e}"
                                        )

                        _harness_latency = (_time.time() - _harness_start) * 1000

                        self._harness_metrics.record_generation(
                            game_id=(
                                player_state.get("game_id")
                                if isinstance(player_state, dict)
                                else getattr(player_state, "game_id", None)
                            ),
                            week=(
                                player_state.get("current_week")
                                if isinstance(player_state, dict)
                                else getattr(player_state, "current_week", None)
                            ),
                            attempts=attempt + 1,
                            preflight_result=(
                                {
                                    "all_present": preflight_result.all_present,
                                    "missing_constraints": preflight_result.missing_constraints,
                                }
                                if preflight_result
                                else None
                            ),
                            validation_result={
                                "passed": harness_validation.passed,
                                "score": harness_validation.score,
                                "detailed_checks": harness_validation.detailed_checks,
                            },
                            latency_ms=_harness_latency,
                        )
                    except Exception as e:
                        logger.warning(f"Harness post-validation failed (round, non-blocking): {e}")

                if harness_should_retry and harness_correction and attempt < retry_count - 1:
                    last_error = harness_correction
                    continue

                # ★ 叙事系统后处理（round，非阻塞）
                self._post_generation_analysis(story_text, player_state)

                # Step 1.5: AI-based consistency validation (if world_model is provided)
                if world_model and story_text:
                    story_text = self._validate_and_retry_story(
                        story_text=story_text,
                        world_model=world_model,
                        player_state=player_state,
                        character_settings=character_settings or {},
                        language=language,
                        original_prompt=current_prompt,
                        sys_prompt=sys_prompt,
                        stream_callback=stream_callback,
                        status_callback=status_callback,
                    )

                # 成功生成并校验通过，跳出重试循环
                break

            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                last_error = str(e)
                logger.warning(f"Round attempt {attempt + 1} failed: {e}")
                if attempt == retry_count - 1:
                    break
                continue
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error during round event generation: {e}")
                if attempt == retry_count - 1:
                    break
                continue

        # Step 2: Generate options based on the story
        try:
            # 如果最后一次尝试没有成功生成故事，但之前某次生成了有效的故事文本，使用它
            if not story_text or len(story_text) <= 50:
                if best_story_text and len(best_story_text) > 50:
                    logger.info(
                        f"All validation attempts failed, using best story from previous attempt "
                        f"({len(best_story_text)} chars)"
                    )
                    story_text = best_story_text
                else:
                    raise ValueError("All generation attempts failed")

            if option_generator is None:
                raise ValueError("option_generator is required")

            if status_callback:
                status_callback("generating_options")

            event = option_generator.generate_options_only(
                story_description=story_text,
                player_state=player_state,
                character_settings=character_settings,
                language=language,
            )

            # Validate relationships
            option_generator.validate_and_fix_relationships(event, character_settings)

            # Validate options consistency
            option_issues = option_generator.validate_options_consistency(
                event=event,
                story_description=story_text,
                available_people=available_people_names,
                language=language,
            )
            if option_issues:
                logger.warning(f"Options consistency issues found: {option_issues}")

            # ★ StateTracker: 将状态机 metrics 附加到 round event
            if state_tracker_round:
                try:
                    state_metrics = state_tracker_round.to_metrics()
                    if not hasattr(event, "metadata"):
                        event.metadata = {}
                    if isinstance(getattr(event, "metadata", None), dict):
                        event.metadata["generation_state"] = state_metrics
                    logger.debug(f"StateTracker (round) metrics: {state_metrics}")
                except Exception as e:
                    logger.warning(f"Failed to attach state metrics (round): {e}")

            return event  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Failed to generate round event: {e}")
            # ★ 如果故事已生成但后续步骤（如选项生成）失败，保留真实故事而非使用 fallback
            # 优先使用最后一次的 story_text，否则回退到所有尝试中的最佳故事
            effective_story = (
                story_text if (story_text and len(story_text) > 50) else best_story_text
            )
            if effective_story and len(effective_story) > 50:
                logger.info(
                    f"Using already-generated story ({len(effective_story)} chars) with fallback options"
                )
                fallback_desc = effective_story
            else:
                fallback_desc = (
                    "这一天平静地度过了。" if language == "zh" else "This day passed quietly."
                )
            return GameEvent(
                event_description=fallback_desc,
                options=[
                    EventOption(
                        text="继续前进" if language == "zh" else "Move forward",
                        effects={"energy": 0, "mood": 0, "knowledge": 0, "wealth": 0},
                    ),
                    EventOption(
                        text="思考一下" if language == "zh" else "Think it over",
                        effects={"energy": -5, "mood": 5, "knowledge": 5, "wealth": 0},
                    ),
                ],
            )

    # -------------------- Internal --------------------

    def _validate_and_retry_story(
        self,
        story_text: str,
        world_model,
        player_state: Dict[str, Any],
        character_settings: Dict[str, Any],
        language: str,
        original_prompt: str,
        sys_prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Validate story consistency and retry once if CRITICAL issues found.

        Optimized strategy:
        - Only retry for truly critical issues (causal breaks, major contradictions)
        - Use tiered validation: check only the most important constraints first

        Returns:
            Original or regenerated story text
        """
        # ★ 诊断日志：确认进入时 stream_callback 状态
        logger.info(
            f"[_validate_and_retry_story] Entered with stream_callback={stream_callback is not None}"
        )

        # FAST 模式：直接跳过 AI 一致性校验
        if self.harness_profile.skip_ai_consistency_check:
            return story_text

        retry_key = f"{player_state.get('week', 0)}-{player_state.get('current_round', 0)}"

        # 防循环守卫：按级别差异化控制
        if self.quality_level.value == "master":
            # MASTER：允许最多 2 次局部修正
            if self._master_retry_counts.get(retry_key, 0) >= 2:
                logger.info(
                    f"[Validation] Skipping consistency check for round {retry_key} "
                    f"(already retried 2 times in master mode)"
                )
                return story_text
        else:
            # EXPERT：保持原有布尔守卫（每轮最多 1 次）
            if self._last_retry_key == retry_key:
                logger.info(
                    f"[Validation] Skipping consistency check for round {retry_key} "
                    f"(already retried this round)"
                )
                return story_text

        try:
            from src.ai.consistency_validator import ConsistencyValidator

            # ★ 发送校验状态，让用户知道正在检查故事一致性
            if status_callback:
                logger.info("★ 发送 validating 状态提示")
                status_callback("validating")

            validator = ConsistencyValidator(self.client)
            validation = validator.validate_story(
                story_text=story_text,
                world_model=world_model,
                player_state_dict=player_state,
                character_settings=character_settings,
                language=language,
            )

            # ★ 校验完成后，如果通过则立即返回，避免不必要的处理
            if validation.passed:
                logger.info("[Validation] Story passed consistency check")
                return story_text

            if not validation.has_critical_issues:
                logger.info(
                    f"[Validation] 一致性校验有 {len(validation.warning_issues)} 个WARNING，不触发重试"
                )
                return story_text

            # CRITICAL issues found - trigger local fix (not full regeneration)
            logger.info(
                f"[Validation] 一致性校验发现 {len(validation.critical_issues)} 个CRITICAL问题，"
                f"触发局部修正（非全文重新生成）"
            )
            for issue in validation.critical_issues:
                logger.warning(f"  CRITICAL [{issue.dimension}]: {issue.description[:80]}")

            # 构建局部修正 prompt
            if language == "en":
                fix_prompt = f"""You are a professional story editor. Below is a completed story that has some issues requiring correction.

Please **only modify the problematic paragraphs** and keep the rest of the content completely unchanged. Output the full story text after modification.

[Original Story]
{story_text}

[Issues to Fix]
"""
                for issue in validation.critical_issues:
                    fix_prompt += f"\n- [{issue.dimension}] {issue.description}"
                    if issue.fix_suggestion:
                        fix_prompt += f"\n  Suggested fix: {issue.fix_suggestion}"

                fix_prompt += """

[Correction Requirements]
1. Only modify sentences or paragraphs directly related to the above issues
2. Keep the overall structure, plot direction, and character relationships unchanged
3. Ensure the modified content flows naturally with the surrounding context
4. Output the corrected full story text directly, without any explanations or markers
"""
                fix_system_prompt = (
                    "You are a precise story editor who excels at fixing specific "
                    "issues while preserving the overall narrative."
                )
            else:
                fix_prompt = f"""你是一位专业的故事编辑。以下是一段已完成的故事，但存在一些需要修正的问题。

请**仅修改有问题的段落**，保留其余内容完全不变。修改后输出完整的故事文本。

【原始故事】
{story_text}

【需要修正的问题】
"""
                for issue in validation.critical_issues:
                    fix_prompt += f"\n- [{issue.dimension}] {issue.description}"
                    if issue.fix_suggestion:
                        fix_prompt += f"\n  修正建议：{issue.fix_suggestion}"

                fix_prompt += """

【修正要求】
1. 只修改与上述问题直接相关的句子或段落
2. 保持故事的整体结构、情节走向和人物关系不变
3. 确保修改后的内容与上下文自然衔接
4. 直接输出修正后的完整故事文本，不要添加任何解释或标记
"""
                fix_system_prompt = (
                    "你是一位精准的故事编辑，擅长在保持整体不变的前提下修正具体问题。"
                )

            # ★ 发送局部修正状态提示
            if status_callback:
                logger.info("[Validation] 发送 retrying + retry 状态（局部修正）")
                status_callback("retrying")
                status_callback("retry")  # 让前端清空旧故事，准备接收修正后的内容

            # 记录防循环守卫
            if self.quality_level.value == "master":
                self._master_retry_counts[retry_key] = (
                    self._master_retry_counts.get(retry_key, 0) + 1
                )
            else:
                self._last_retry_key = retry_key

            logger.info(
                f"Local fix call with temperature=0.5, stream_callback={stream_callback is not None}"
            )

            # 用较低温度进行局部修正
            fixed_story = self.client.call(
                system_prompt=fix_system_prompt,
                user_prompt=fix_prompt,
                temperature=0.5,  # 低温度确保精确修正
                max_tokens=8192,
                stream_callback=stream_callback,
                frequency_penalty=0.3,
                presence_penalty=0.3,
            )

            if fixed_story:
                logger.info(f"局部修正完成，故事长度: {len(fixed_story)} (原: {len(story_text)})")
                fixed_story = _normalize_punctuation(fixed_story, language)
                return fixed_story

            logger.warning("局部修正返回空结果，回退到原始故事")
            return story_text

        except Exception as e:
            logger.error(f"Story validation/retry failed: {e}")
            return story_text

    def _log_constraint_completeness(self, prompt: str) -> None:
        """检查 prompt 中是否包含关键约束标记"""
        expected_markers = {
            "可用人物": "人物名单约束",
            "世界事实": "已建立事实约束",
        }
        missing = []
        for marker, desc in expected_markers.items():
            if marker not in prompt:
                missing.append(desc)
        if missing:
            logger.warning(f"Constraint completeness check FAILED - missing: {missing}")
        else:
            logger.debug("Constraint completeness check passed")

    def _extract_validation_context(
        self,
        player_state: dict,
        character_settings: Optional[dict] = None,
        pending_storylines: Optional[list] = None,
        established_facts: Optional[list] = None,
        last_event_description: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """从生成参数中提取 Harness 验证所需的上下文。

        Args:
            player_state: 当前玩家状态
            character_settings: 角色设定
            pending_storylines: 待处理剧情线
            established_facts: 已建立事实
            last_event_description: 上一事件描述
            **kwargs: 额外参数（如 character_habits）

        Returns:
            供验证管道使用的上下文 dict
        """
        # 提取可用人物名称列表
        available_people: list = []
        if character_settings:
            # 尝试从 character_settings 中提取人物名
            try:
                from config.prompts._helpers import _collect_available_people

                people = _collect_available_people(character_settings)
                available_people = [p.get("name", "") for p in people if p.get("name")]
            except Exception:
                pass

        if not available_people and isinstance(player_state, dict):
            # fallback: 从 player_state 的 relationships 中提取
            relationships = player_state.get("relationships", {})
            if isinstance(relationships, dict):
                available_people = list(relationships.keys())

        # 提取 overdue 剧情线
        overdue_storylines: list = []
        high_storylines: list = []
        medium_storylines: list = []
        if pending_storylines:
            for sl in pending_storylines:
                if isinstance(sl, dict):
                    if sl.get("overdue"):
                        overdue_storylines.append(sl)
                    priority = sl.get("priority", "").lower()
                    if priority == "high":
                        high_storylines.append(sl)
                    elif priority == "medium":
                        medium_storylines.append(sl)

        # 提取 last_location
        last_location = ""
        if isinstance(player_state, dict):
            last_location = player_state.get("current_location", "") or player_state.get(
                "location", ""
            )
        else:
            last_location = getattr(player_state, "current_location", "") or getattr(
                player_state, "location", ""
            )

        # 提取 era 和 era_type
        era = ""
        era_type = ""
        if isinstance(character_settings, dict):
            era_info = character_settings.get("era", {})
            if isinstance(era_info, dict):
                era = era_info.get("era_description", "")
            elif isinstance(era_info, str):
                era = era_info

        era_str = str(era).lower()
        if "现代" in era_str or "当代" in era_str or "未来" in era_str or "202" in era_str or "201" in era_str or "200" in era_str:
            era_type = "modern"
        elif any(kw in era_str for kw in ["唐", "宋", "元", "明", "清", "汉", "秦", "周", "春秋", "战国", "三国", "晋", "隋", "古代", " medieval", "ancient", "historic"]):
            era_type = "ancient"
        elif any(kw in era_str for kw in [" medieval", "ancient", " historic"]):
            era_type = "ancient"

        return {
            "available_people": available_people,
            "established_facts": established_facts or [],
            "pending_storylines": pending_storylines or [],
            "overdue_storylines": overdue_storylines,
            "high_storylines": high_storylines,
            "medium_storylines": medium_storylines,
            "last_location": last_location,
            "character_habits": kwargs.get("character_habits", []),
            "era": era,
            "era_type": era_type,
        }

    @staticmethod
    def _get_phase_from_state(player_state: Dict[str, Any]) -> str:
        """Determine life phase from player state."""
        week = player_state.get("week", 0)
        if week < 24:
            return "early_career"
        elif week < 48:
            return "establishing"
        elif week < 72:
            return "growth"
        else:
            return "consolidation"
