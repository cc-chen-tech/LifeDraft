"""Round event generation service.

Handles the generation of events for each round in the game.
"""

import logging
import time
from typing import Any, Callable, Dict, Optional

from src.ai.models import GameEvent
from src.game.narrative_manager import NarrativeManager
from src.game.world_model_updater import WorldModelUpdater

logger = logging.getLogger(__name__)


class RoundEventGenerator:
    """Service for generating round events.

    This service handles:
    - Event generation with context building
    - Timeout handling and concurrency control
    - Fallback event generation
    """

    def __init__(
        self,
        player_state_getter: Callable[[], Any],
        ai_generator: Any,
        language_getter: Callable[[], str],
        character_introduction_service: Any,
        summary_selector: Any,
        relationship_service: Any,
        event_callback: Optional[Callable] = None,
    ):
        """
        Args:
            player_state_getter: Function that returns current player state
            ai_generator: EventGenerator instance
            language_getter: Function that returns current language
            character_introduction_service: CharacterIntroductionService instance
            summary_selector: HistoricalSummarySelector instance
            relationship_service: RelationshipMCPService instance
            event_callback: Optional callback when event is generated
        """
        self._get_player_state = player_state_getter
        self.ai_generator = ai_generator
        self._get_language = language_getter
        self.character_introduction_service = character_introduction_service
        self.summary_selector = summary_selector
        self.relationship_service = relationship_service
        self.event_callback = event_callback

        # Generation state
        self._generating: bool = False
        self._generating_start_time: Optional[float] = None
        self._GENERATION_TIMEOUT: float = 120.0  # seconds
        self._current_event: Optional[GameEvent] = None

    @property
    def player_state(self):
        return self._get_player_state()

    @property
    def language(self):
        return self._get_language()

    @property
    def current_event(self):
        return self._current_event

    @current_event.setter
    def current_event(self, value):
        self._current_event = value

    def generate_round_event(
        self,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        session: Optional[Any] = None,
    ) -> Optional[GameEvent]:
        """
        Generate an event for the current round within the week.
        Uses multi-round system: each week has multiple rounds.

        Args:
            stream_callback: Optional callback for streaming story text
            status_callback: Optional callback for reporting processing status

        Returns:
            GameEvent object for the current round
        """
        player_state = self.player_state
        if not player_state:
            raise ValueError("Game not started.")

        # ★ CRITICAL: Check if we already have a valid event with options
        if self._current_event and self._current_event.options:
            logger.info(
                f"Returning existing event (options count: {len(self._current_event.options)})"
            )
            return self._current_event

        # ★ CRITICAL: Resume from round_history if current_event is empty but story exists
        # This handles the "save & load" scenario where current_event_data is cleared after choice
        # but round_history contains the story for current round
        if not self._current_event or not self._current_event.options:
            current_week = player_state.week
            current_round = player_state.current_round
            round_history = player_state.round_history
            last_round_full_story = player_state.last_round_full_story

            logger.info(
                f"[Resume Check] current_week={current_week}, current_round={current_round}, "
                f"round_history_count={len(round_history) if round_history else 0}, "
                f"has_last_round_full_story={bool(last_round_full_story)}, "
                f"has_session={session is not None}"
            )

            # Check if we can resume from existing story
            # Case 1: round_history has current round's story
            # Case 2: last_round_full_story exists and matches current round (after choice, before next round)
            existing_story = None
            resume_source = None

            if round_history:
                last_entry = round_history[-1]
                entry_week = last_entry.get("week")
                entry_round = last_entry.get("round")

                logger.info(
                    f"[Resume Check] last_entry: week={entry_week}, round={entry_round}, "
                    f"has_event_desc={bool(last_entry.get('event_description'))}"
                )

                # Case 1: Current round story exists in round_history
                if entry_week == current_week and entry_round == current_round:
                    event_desc = last_entry.get("event_description", "")
                    story_continuation = last_entry.get("story_continuation", "")
                    existing_story = event_desc + (
                        f"\n\n{story_continuation}" if story_continuation else ""
                    )
                    resume_source = "round_history"
                    logger.info(
                        f"[Resume Check] Found current round story in round_history"
                    )

                # Case 2: Last round is current_round - 1, and last_round_full_story exists
                # This means story was generated but choice not made yet
                elif (
                    entry_week == current_week
                    and entry_round == current_round - 1
                    and last_round_full_story
                ):
                    existing_story = last_round_full_story
                    resume_source = "last_round_full_story"
                    logger.info(
                        f"[Resume Check] Found story in last_round_full_story (current_round={current_round}, last_entry_round={entry_round})"
                    )

            # Also check last_round_full_story if no round_history match
            elif last_round_full_story:
                existing_story = last_round_full_story
                resume_source = "last_round_full_story_only"
                logger.info(
                    f"[Resume Check] Using last_round_full_story (no round_history match)"
                )

            if existing_story and len(existing_story) > 100:
                # ★ Check options cache first
                cached_options = None
                if session:
                    cached_options = session.get_cached_options(
                        current_week, current_round
                    )

                if cached_options:
                    # Use cached options - instant response!
                    logger.info(
                        f"★ Resume mode (cached options): Using {len(cached_options)} cached options "
                        f"for 第{current_week + 1}周 round {current_round}"
                    )

                    # Create event with cached options
                    from src.ai.models import EventOption, GameEvent

                    options = [EventOption(**opt) for opt in cached_options]
                    event = GameEvent(
                        event_description=existing_story,
                        options=options,
                    )

                    self._current_event = event
                    player_state.current_event_data = event.model_dump()

                    if self.event_callback:
                        self.event_callback(event, player_state)

                    logger.info(
                        f"★ Resume mode complete (cached): Returned {len(options)} options instantly"
                    )
                    return event

                # No cache - generate options
                logger.info(
                    f"★ Resume mode detected ({resume_source}): Found existing story for 第{current_week + 1}周 "
                    f"round {current_round} ({len(existing_story)} chars), generating options only"
                )

                self._generating = True
                self._generating_start_time = time.time()

                try:
                    if status_callback:
                        status_callback("generating_options")

                    # Generate options only for existing story
                    event = self.ai_generator.generate_options_only(
                        story_description=existing_story,
                        player_state=player_state.to_dict(),
                        character_settings=player_state.character_settings,
                        language=self.language,
                    )

                    # ★ Cache the generated options
                    if session and event.options:
                        session.set_cached_options(
                            current_week,
                            current_round,
                            [opt.model_dump() for opt in event.options],
                        )

                    self._current_event = event
                    player_state.current_event_data = event.model_dump()

                    if self.event_callback:
                        self.event_callback(event, player_state)

                    logger.info(
                        f"★ Resume mode complete: Generated {len(event.options)} options for existing story"
                    )
                    self._generating = False
                    self._generating_start_time = None
                    return event

                except Exception as e:
                    logger.error(
                        f"Failed to generate options for existing story: {e}",
                        exc_info=True,
                    )
                    # Fall through to normal generation
                    self._generating = False
                    self._generating_start_time = None

        # ★ CRITICAL: Prevent concurrent generation with timeout auto-reset
        if self._generating:
            # Check if generation has timed out
            if self._generating_start_time:
                elapsed = time.time() - self._generating_start_time
                if elapsed > self._GENERATION_TIMEOUT:
                    logger.warning(
                        f"Generation timeout ({elapsed:.1f}s > {self._GENERATION_TIMEOUT}s), auto-resetting flag"
                    )
                    self._generating = False
                    self._generating_start_time = None
                else:
                    logger.warning(
                        f"Event generation in progress ({elapsed:.1f}s elapsed), raising error"
                    )
                    raise ValueError("Event generation in progress, please wait")
            else:
                logger.warning(
                    "Event generation in progress (no timestamp), raising error"
                )
                raise ValueError("Event generation in progress, please wait")

        self._generating = True
        self._generating_start_time = time.time()

        # current_week and current_round already defined above in resume mode check
        # Re-fetch here to ensure consistency
        current_week = player_state.week
        current_round = player_state.current_round

        # ★ 显示用周数（人类可读，从1开始）
        week_display = (
            f"第{current_week + 1}周" if current_week is not None else "未知周"
        )
        logger.info(f"Generating round event: {week_display}, round={current_round}")

        # ★ 步骤0: 检查是否有预定事件需要触发
        scheduled_events = player_state.get_pending_scheduled_events(
            current_week, current_round
        )
        if scheduled_events:
            logger.info(f"检测到 {len(scheduled_events)} 个预定事件需要触发")
            event = self._generate_scheduled_event(  # type: ignore[assignment]
                scheduled_events, player_state, stream_callback, status_callback
            )
            if event:
                self._current_event = event  # type: ignore[assignment]
                player_state.current_event_data = event.model_dump()
                # 标记预定事件已触发
                for se in scheduled_events:
                    player_state.mark_scheduled_event_triggered(se.get("event_id"))
                if self.event_callback:
                    self.event_callback(event, player_state)
                self._generating = False
                self._generating_start_time = None
                return event

        # Get round context from player state
        round_context = player_state.get_round_context()

        try:
            # 发送初始化状态
            if status_callback:
                status_callback("initializing")

            # 步骤1: 尝试生成新人物（存入待引入队列，不立即引入）
            self.character_introduction_service.maybe_generate_new_character(
                probability=0.08
            )

            # 步骤2: 检查是否有合适的引入机会
            new_character = None
            pending_entry = (
                self.character_introduction_service.check_introduction_opportunity()
            )
            if pending_entry:
                new_character = (
                    self.character_introduction_service.introduce_pending_character(
                        pending_entry
                    )
                )
                if new_character:
                    intro_ctx = pending_entry.get("introduction_context", "random")
                    logger.info(
                        f"本轮引入待引入人物: {new_character.get('name')} - {new_character.get('role')} (场景: {intro_ctx})"
                    )

            # 获取最新的状态（可能已包含新引入的人物）
            state_dict = player_state.to_dict()
            character_settings = state_dict.get("character_settings", {})

            # 随机选择历史总结加入提示词（如同回忆）
            if status_callback:
                status_callback("loading_context")
            historical_weekly, historical_yearly = (
                self.summary_selector.select_relevant_historical_summary(player_state)
            )

            # 检测关系事件触发
            relationship_events = []
            try:
                era_info = character_settings.get("era", {})
                era = era_info.get("era_description", "modern")
                relationship_events = self.relationship_service.get_triggered_events(
                    player_state, era=era, max_events=2
                )
                if relationship_events:
                    logger.info(
                        f"检测到{len(relationship_events)}个关系事件: {[e['event_type'] for e in relationship_events]}"
                    )
            except Exception as e:
                logger.warning(f"关系事件检测失败: {e}")

            # 构建世界模型用于约束和校验
            if status_callback:
                status_callback("building_world")
            world_model = None
            try:
                from src.game.world_model import WorldModel

                world_model = WorldModel.from_player_state(player_state)
                logger.info(
                    f"WorldModel built: {len(world_model.character_locations)} locations, "
                    f"{len(world_model.career_records)} careers, "
                    f"{len(world_model.active_commitments)} commitments, "
                    f"{len(world_model.causal_chains)} causal chains"
                )
            except Exception as e:
                logger.warning(f"WorldModel 构建失败，将跳过一致性校验: {e}")

            # 发送开始生成故事的状态
            if status_callback:
                status_callback("generating_story")

            event = self.ai_generator.generate_round_event(
                player_state=state_dict,
                language=self.language,
                round_number=current_round,
                round_context=round_context,
                character_settings=character_settings,
                stream_callback=stream_callback,
                relationship_events=relationship_events,
                historical_weekly_summary=historical_weekly,
                historical_yearly_summary=historical_yearly,
                game_date_info=player_state.get_game_date_info(),
                pending_storylines=player_state.pending_storylines,
                established_facts=player_state.established_facts,
                last_event_concluded=player_state.last_event_concluded,
                last_round_full_story=player_state.last_round_full_story,
                activated_foreshadowing=NarrativeManager.select_foreshadowing_seed(
                    player_state
                ),
                character_habits=player_state.character_habits,
                world_model=world_model,
                new_character=new_character,
                status_callback=status_callback,
            )

            # 如果有关系事件被触发，标记为已触发
            if relationship_events and event:
                for rel_event in relationship_events:
                    try:
                        self.relationship_service.mark_event_triggered(
                            player_state,
                            rel_event["character_name"],
                            rel_event["event_type"],
                        )
                        logger.info(
                            f"标记事件已触发: {rel_event['event_type']} for {rel_event['character_name']}"
                        )
                    except Exception as e:
                        logger.warning(f"标记事件触发失败: {e}")

            if not event:
                logger.error("AI generator returned None for round event!")
                event = self._generate_fallback_event(is_round=True)

            self._current_event = event

            # Save current event to player state for persistence
            player_state.current_event_data = event.model_dump()

            if self.event_callback:
                self.event_callback(event, player_state)

            logger.info(
                f"Successfully generated round event for 第{current_week + 1}周, round {current_round}"
            )
            self._generating = False  # Reset flag on success
            self._generating_start_time = None
            return event

        except Exception as e:
            logger.error(f"Failed to generate round event: {str(e)}", exc_info=True)
            event = self._generate_fallback_event(is_round=True)
            self._current_event = event
            player_state.current_event_data = event.model_dump()
            self._generating = False  # Reset flag on error
            self._generating_start_time = None
            return event

    def _generate_fallback_event(self, is_round: bool = True) -> GameEvent:
        """Generate a fallback event when AI generation fails."""
        from src.ai.models import EventOption

        player_state = self.player_state
        language = self.language

        if language == "zh":
            description = "一个平静的日子，没有特别的事情发生。"
            options = [
                EventOption(text="安静地度过", effects={}),
                EventOption(text="主动寻找有趣的事", effects={"mood": 5}),
                EventOption(text="专注于工作/学习", effects={"knowledge": 5}),
            ]
        else:
            description = "A quiet day with nothing special happening."
            options = [
                EventOption(text="Spend quietly", effects={}),
                EventOption(text="Look for something interesting", effects={"mood": 5}),
                EventOption(text="Focus on work/study", effects={"knowledge": 5}),
            ]

        return GameEvent(
            event_description=description,
            options=options,
        )

    def _generate_scheduled_event(
        self,
        scheduled_events: list,
        player_state,
        stream_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Optional[GameEvent]:
        """根据预定事件生成强制事件。

        当检测到有预定事件需要触发时，调用此方法生成事件。
        事件内容必须围绕兑现承诺展开。

        Args:
            scheduled_events: 预定事件列表
            player_state: PlayerState 实例
            stream_callback: 流式回调
            status_callback: 状态回调

        Returns:
            GameEvent 实例
        """
        if status_callback:
            status_callback("generating_scheduled_event")

        # 合并多个预定事件的信息（如果有多个）
        descriptions = []
        all_parties = set()
        event_hints = []
        max_importance = "normal"
        from src.game.constants import IMPORTANCE_ORDER

        for se in scheduled_events:
            descriptions.append(se.get("description", ""))
            all_parties.update(se.get("parties", []))
            if se.get("event_hint"):
                event_hints.append(se.get("event_hint"))
            # 取最高重要程度
            se_importance = se.get("importance", "normal")
            if IMPORTANCE_ORDER.get(se_importance, 2) < IMPORTANCE_ORDER.get(
                max_importance, 2
            ):
                max_importance = se_importance

        # 构建强制事件的提示
        combined_description = "；".join(descriptions)
        combined_hint = "；".join(event_hints) if event_hints else ""
        parties_str = "、".join(all_parties) if all_parties else ""

        logger.info(
            f"生成预定事件: {combined_description[:60]}... (涉及: {parties_str})"
        )

        try:
            # 使用AI生成事件内容，但必须包含承诺的核心元素
            state_dict = player_state.to_dict()
            character_settings = state_dict.get("character_settings", {})

            # 构建强制事件提示词
            prompt = self._build_scheduled_event_prompt(
                scheduled_events=scheduled_events,
                player_state=state_dict,
                character_settings=character_settings,
                language=self.language,
            )

            from src.ai.system_prompts import get_system_prompt

            sys_prompt = get_system_prompt("story_novelist", self.language)

            # 调用AI生成
            response = self.ai_generator.ai_client.call(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.85,
                max_tokens=8192,
                stream_callback=stream_callback,
            )

            # 解析响应
            from src.ai.utils import extract_json

            data = extract_json(response)

            if data:
                from src.ai.models import EventOption, GameEvent

                event_desc = data.get("event_description", "")
                options_data = data.get("options", [])

                options = []
                for opt in options_data:
                    options.append(
                        EventOption(
                            text=opt.get("text", ""),
                            effects=opt.get("effects", {}),
                        )
                    )

                if event_desc and options:
                    event = GameEvent(
                        event_description=event_desc,
                        options=options,
                    )
                    logger.info(f"成功生成预定事件: {event_desc[:60]}...")
                    return event

            # 如果解析失败，生成一个简单的事件
            logger.warning("解析预定事件响应失败，使用简化版本")
            return self._generate_simple_scheduled_event(scheduled_events, player_state)

        except Exception as e:
            logger.error(f"生成预定事件失败: {e}")
            return self._generate_simple_scheduled_event(scheduled_events, player_state)

    def _build_scheduled_event_prompt(
        self,
        scheduled_events: list,
        player_state: dict,
        character_settings: dict,
        language: str,
    ) -> str:
        """构建预定事件的提示词。"""

        # 合并预定事件信息
        descriptions = []
        all_parties = set()
        event_hints = []

        for se in scheduled_events:
            descriptions.append(se.get("description", ""))
            all_parties.update(se.get("parties", []))
            if se.get("event_hint"):
                event_hints.append(se.get("event_hint"))

        combined_description = "；".join(descriptions)
        combined_hint = "；".join(event_hints) if event_hints else ""
        parties_str = "、".join(all_parties) if all_parties else ""

        player_name = player_state.get("player_name", "主角")
        week = player_state.get("week", 0)
        current_round = player_state.get("current_round", 0)

        round_names = (
            ["周一", "周中", "周末"]
            if language == "zh"
            else ["Monday", "Midweek", "Weekend"]
        )
        round_name = (
            round_names[current_round]
            if current_round < len(round_names)
            else f"Round {current_round}"
        )

        if language == "zh":
            return f"""【强制事件】角色之前做出的承诺必须在本轮兑现。

承诺内容：{combined_description}
涉及人物：{parties_str}
事件提示：{combined_hint}

当前时间：第{week}周，{round_name}
玩家姓名：{player_name}

【要求】
1. 事件必须围绕兑现上述承诺展开
2. 必须涉及上述人物
3. 事件开头要自然衔接之前的承诺（如"记得之前答应过..."）
4. 事件描述应800-1200字，生动有深度
5. 提供3-4个选项，每个选项都要与承诺相关
6. 选项应呈现真实的权衡取舍

【输出格式】
返回JSON格式：
{{
  "event_description": "事件描述（800-1200字）",
  "options": [
    {{"text": "选项文本（最多15字）", "effects": {{"energy": -10, "mood": 5, ...}}}},
    ...
  ]
}}

只返回JSON，不要其他文本。"""
        else:
            return f"""[MANDATORY EVENT] The character must fulfill their previous commitment this round.

Commitment: {combined_description}
Characters involved: {parties_str}
Event hints: {combined_hint}

Current time: Week {week}, {round_name}
Player name: {player_name}

[Requirements]
1. The event must center on fulfilling the above commitment
2. Must involve the listed characters
3. Start naturally by referencing the previous promise (e.g., "Remembering the promise to...")
4. Event description: 800-1200 words, vivid and deep
5. Provide 3-4 options, each related to the commitment
6. Options should present real trade-offs

[Output Format]
Return JSON:
{{
  "event_description": "Event description (800-1200 words)",
  "options": [
    {{"text": "Option text (max 15 chars)", "effects": {{"energy": -10, "mood": 5, ...}}}},
    ...
  ]
}}

Return ONLY JSON, no other text."""

    def _generate_simple_scheduled_event(
        self,
        scheduled_events: list,
        player_state,
    ) -> GameEvent:
        """生成一个简单的预定事件（当AI生成失败时的后备方案）。"""
        from src.ai.models import EventOption, GameEvent

        # 合并描述
        descriptions = [se.get("description", "") for se in scheduled_events]
        combined_desc = "；".join(descriptions)

        language = self.language

        if language == "zh":
            event_desc = f"到了兑现承诺的时候了。{combined_desc}。你需要做出选择。"
            options = [
                EventOption(text="认真兑现承诺", effects={"mood": 10, "energy": -10}),
                EventOption(text="敷衍了事", effects={"mood": -5}),
                EventOption(text="找借口推迟", effects={"mood": -15}),
            ]
        else:
            event_desc = f"It's time to fulfill your commitment. {combined_desc}. You need to make a choice."
            options = [
                EventOption(
                    text="Fulfill the commitment seriously",
                    effects={"mood": 10, "energy": -10},
                ),
                EventOption(text="Do it half-heartedly", effects={"mood": -5}),
                EventOption(text="Make an excuse to delay", effects={"mood": -15}),
            ]

        return GameEvent(
            event_description=event_desc,
            options=options,
        )
