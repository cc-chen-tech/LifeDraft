"""World model update management: locations, careers, commitments, causal chains,
story analysis, and character profile synthesis.

Extracted from game_loop.py to reduce God Class complexity.
Static methods accept a PlayerState instance; AI-dependent methods require
an AIClient and language parameter.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from src.game.constants import (DEFAULT_CAREER_LEVEL, GENERIC_CHARACTER_NAMES,
                                IMPORTANCE_ORDER, ROLE_KEYWORDS,
                                VALID_CAREER_LEVELS)

logger = logging.getLogger(__name__)


class WorldModelUpdater:
    """Manages incremental updates to the world model."""

    # ------------------------------------------------------------------
    # Location updates
    # ------------------------------------------------------------------

    @staticmethod
    def process_location_updates(player_state, location_updates: list) -> None:
        """处理从故事压缩中提取的位置变动更新。

        更新 world_model_data.character_locations。
        """
        if not player_state or not location_updates:
            return

        current_week = player_state.week
        wm_data = player_state.world_model_data
        locations = wm_data.get("character_locations", {})

        for update in location_updates:
            action = update.get("action", "")
            character = update.get("character", "")
            if not action or not character:
                continue

            if action == "move":
                to_loc = update.get("to", "")
                if not to_loc:
                    continue
                region = to_loc[:2] if len(to_loc) > 2 else to_loc
                locations[character] = {
                    "location": to_loc,
                    "region": region,
                    "since_week": current_week,
                    "travel_mode": update.get("mode", "resident"),
                    "from": update.get("from", ""),
                    "reason": update.get("reason", ""),
                }
                logger.info(
                    f"📍 位置更新: {character} -> {to_loc} ({update.get('mode', 'resident')})"
                )

            elif action == "confirm":
                loc = update.get("location", "")
                if not loc:
                    continue
                if character not in locations:
                    region = loc[:2] if len(loc) > 2 else loc
                    locations[character] = {
                        "location": loc,
                        "region": region,
                        "since_week": current_week,
                        "travel_mode": "resident",
                        "reason": update.get("reason", ""),
                    }
                    logger.info(f"📍 位置确认(新): {character} @ {loc}")
                else:
                    locations[character]["location"] = loc
                    logger.info(f"📍 位置确认: {character} @ {loc}")

        wm_data["character_locations"] = locations

    # ------------------------------------------------------------------
    # Career updates
    # ------------------------------------------------------------------

    @staticmethod
    def process_career_updates(player_state, career_updates: list) -> None:
        """处理从故事压缩中提取的职业变动更新。

        更新 world_model_data.career_records。
        """
        if not player_state or not career_updates:
            return

        current_week = player_state.week
        wm_data = player_state.world_model_data
        careers = wm_data.get("career_records", {})

        for update in career_updates:
            action = update.get("action", "")
            character = update.get("character", "")
            if not action or not character:
                continue

            new_role = update.get("new_role", "")
            employer = update.get("employer", "")
            level = update.get("level", DEFAULT_CAREER_LEVEL)

            if level not in VALID_CAREER_LEVELS:
                level = DEFAULT_CAREER_LEVEL

            if character in careers:
                old_record = careers[character]
                history = old_record.get("history", [])
                history.append(
                    {
                        "job": old_record.get("current_job", ""),
                        "employer": old_record.get("employer", ""),
                        "level": old_record.get("level", ""),
                        "from_week": old_record.get("since_week", 0),
                        "to_week": current_week,
                        "action": action,
                    }
                )
                careers[character] = {
                    "current_job": new_role or old_record.get("current_job", ""),
                    "employer": employer or old_record.get("employer", ""),
                    "level": level,
                    "since_week": current_week,
                    "history": history,
                }
            else:
                careers[character] = {
                    "current_job": new_role,
                    "employer": employer,
                    "level": level,
                    "since_week": current_week,
                    "history": [],
                }

            logger.info(
                f"💼 职业更新: {character} [{action}] -> {new_role} @ {employer} (level: {level})"
            )

        wm_data["career_records"] = careers

    # ------------------------------------------------------------------
    # Commitment updates
    # ------------------------------------------------------------------

    @staticmethod
    def process_commitment_updates(player_state, commitment_updates: list) -> None:
        """处理从故事压缩中提取的承诺/约定更新。

        更新 world_model_data.active_commitments。
        """
        if not player_state or not commitment_updates:
            return

        current_week = player_state.week
        wm_data = player_state.world_model_data
        commitments = wm_data.get("active_commitments", [])

        for update in commitment_updates:
            action = update.get("action", "")
            if not action:
                continue

            if action == "new":
                desc = update.get("description", "")
                if not desc:
                    continue
                commitment = {
                    "description": desc,
                    "parties": update.get("parties", []),
                    "deadline_week": update.get("deadline_week", -1),
                    "status": "pending",
                    "created_week": current_week,
                    "importance": update.get("importance", "normal"),
                }
                commitments.append(commitment)
                logger.info(f"🤝 新承诺: {desc[:40]}... (parties: {update.get('parties', [])})")

            elif action in ("fulfilled", "broken", "expired"):
                desc = update.get("description", "")
                if not desc:
                    continue

                # ★ 方案4：增强承诺匹配逻辑
                # 尝试找到匹配的 pending 承诺
                matched = False
                for c in commitments:
                    if c.get("status") != "pending":
                        continue

                    existing_desc = c.get("description", "").lower()
                    update_desc = desc.lower()

                    # 精确匹配：描述互相包含
                    if update_desc in existing_desc or existing_desc in update_desc:
                        matched = True
                    # 模糊匹配：提取关键词（人物名+关键动作）
                    else:
                        # 提取人物名进行匹配
                        existing_parties = [p.lower() for p in c.get("parties", [])]
                        update_parties = [p.lower() for p in update.get("parties", [])]

                        # 如果涉及相同的人物，且描述中有相似的关键词
                        has_common_party = any(p in existing_parties for p in update_parties)

                        # 提取关键动词进行匹配
                        key_verbs = [
                            "仪式",
                            "约定",
                            "承诺",
                            "答应",
                            "保证",
                            "同意",
                            "参加",
                            "出席",
                            "完成",
                        ]
                        existing_has_verb = any(v in existing_desc for v in key_verbs)
                        update_has_verb = any(v in update_desc for v in key_verbs)

                        if has_common_party and existing_has_verb and update_has_verb:
                            # 有共同人物且都包含关键动词，认为是匹配
                            matched = True
                            logger.info(
                                f"🤝 承诺模糊匹配: '{desc[:40]}...' ~ '{c.get('description', '')[:40]}...'"
                            )

                    if matched:
                        c["status"] = action
                        c["resolved_week"] = current_week
                        logger.info(f"🤝 承诺{action}: {c.get('description', '')[:40]}...")
                        break

                if not matched:
                    logger.warning(f"🤝 未能找到匹配的承诺: {desc[:40]}...")

        # Clean up: remove resolved commitments older than 10 weeks
        active = [
            c
            for c in commitments
            if c.get("status") == "pending"
            or (current_week - c.get("resolved_week", current_week)) < 10
        ]
        wm_data["active_commitments"] = active

    # ------------------------------------------------------------------
    # Causal chain updates
    # ------------------------------------------------------------------

    @staticmethod
    def process_causal_updates(player_state, causal_updates: list) -> None:
        """处理从故事压缩中提取的因果链更新。

        更新 world_model_data.causal_chains。
        """
        if not player_state or not causal_updates:
            return

        current_week = player_state.week
        wm_data = player_state.world_model_data
        chains = wm_data.get("causal_chains", [])

        for update in causal_updates:
            action = update.get("action", "")
            if not action:
                continue

            if action == "new":
                cause = update.get("cause", "")
                expected = update.get("expected_consequence", "")
                if not cause or not expected:
                    continue
                chain = {
                    "cause": cause,
                    "expected_consequence": expected,
                    "characters": update.get("characters", []),
                    "created_week": current_week,
                    "resolved": False,
                }
                chains.append(chain)
                logger.info(f"⛓️ 新因果链: {cause[:30]}... → {expected[:30]}...")

            elif action == "resolved":
                cause = update.get("cause", "")
                if not cause:
                    continue
                for c in chains:
                    if not c.get("resolved") and (
                        cause.lower() in c.get("cause", "").lower()
                        or c.get("cause", "").lower() in cause.lower()
                    ):
                        c["resolved"] = True
                        c["resolved_week"] = current_week
                        c["resolution"] = update.get("resolution", "")
                        logger.info(f"⛓️ 因果链解决: {cause[:30]}...")
                        break

        # Clean up: remove resolved chains older than 20 weeks
        active = [
            c
            for c in chains
            if not c.get("resolved") or (current_week - c.get("resolved_week", current_week)) < 20
        ]
        wm_data["causal_chains"] = active

    # ------------------------------------------------------------------
    # Story Analyzer (requires AI)
    # ------------------------------------------------------------------

    @staticmethod
    def run_story_analyzer(
        player_state,
        full_story: str,
        player_choice: str,
        ai_client,
        language: str,
    ) -> None:
        """Run the AI Story Analyzer to dynamically extract key facts.

        Updates world_model_data.dynamic_facts with newly identified constraints.

        Args:
            player_state: Current PlayerState instance.
            full_story: The complete story text (event + continuation).
            player_choice: The player's choice text.
            ai_client: AIClient instance for AI calls.
            language: Language code ('en' or 'zh').
        """
        if not player_state or not full_story:
            return

        try:
            from src.ai.story_analyzer import DynamicFact, StoryAnalyzer

            analyzer = StoryAnalyzer(ai_client)

            # Load existing dynamic facts
            wm_data = player_state.world_model_data
            existing_raw = wm_data.get("dynamic_facts", [])
            existing_facts = []
            for df_d in existing_raw:
                try:
                    existing_facts.append(DynamicFact.from_dict(df_d))
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning(f"Skipping invalid dynamic fact: {e}")
                except Exception as e:
                    logger.exception(f"Unexpected error parsing dynamic fact: {e}")

            # Run analysis
            new_facts = analyzer.analyze_story(
                story_text=full_story,
                player_choice=player_choice,
                existing_facts=existing_facts,
                current_week=player_state.week,
                character_settings=player_state.character_settings or {},
                language=language,
            )

            if new_facts:
                # Apply supersession
                for nf in new_facts:
                    if nf.supersedes:
                        for ef in existing_facts:
                            if ef.fact_id == nf.supersedes:
                                ef.active = False
                                logger.info(f"🔄 动态事实被取代: {ef.fact_id}")
                                break

                # Merge: keep active existing + add new
                all_facts = [ef for ef in existing_facts if ef.active] + new_facts

                # Expire old facts
                current_week = player_state.week
                all_facts = [
                    f
                    for f in all_facts
                    if f.active and (f.expiry_week < 0 or f.expiry_week > current_week)
                ]

                # Limit total facts to 500
                if len(all_facts) > 500:
                    all_facts.sort(
                        key=lambda f: (
                            IMPORTANCE_ORDER.get(f.importance, 2),
                            -(f.source_week),
                        )
                    )
                    removed = all_facts[500:]
                    all_facts = all_facts[:500]
                    logger.info(f"动态事实超过上限，移除 {len(removed)} 个低优先级事实")

                wm_data["dynamic_facts"] = [f.to_dict() for f in all_facts]
                logger.info(
                    f"🔍 Story Analyzer 完成：新增 {len(new_facts)} 个事实，"
                    f"总计 {len(all_facts)} 个活跃事实"
                )
            else:
                logger.info("🔍 Story Analyzer 完成：未发现新的关键事实")

        except (ImportError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"Story Analyzer 执行失败（不影响主流程）: {e}")
        except Exception as e:
            logger.exception(f"Story Analyzer 执行失败（unexpected，不影响主流程）: {e}")

    # ------------------------------------------------------------------
    # Character profile synthesis (requires AI)
    # ------------------------------------------------------------------

    @staticmethod
    def synthesize_character_profiles(player_state, ai_client, language: str) -> None:
        """Synthesize character behavioral profiles from this week's story evidence.

        Called once at the end of each week. Extracts behavioral observations
        from the week's round history and uses AI to build/update per-character
        behavioral profiles.

        Only profiles characters that appeared in at least 2 story rounds this week.
        Limits to top 3 most-mentioned characters to control AI call costs.

        Args:
            player_state: Current PlayerState instance.
            ai_client: AIClient instance for AI calls.
            language: Language code ('en' or 'zh').
        """
        if not player_state:
            return

        try:
            from src.ai.profile_synthesizer import ProfileSynthesizer

            current_week = player_state.week
            wm_data = player_state.world_model_data
            profiles = wm_data.get("character_profiles", {})

            # 1. Collect behavioral evidence from this week's round history
            week_rounds = [
                r for r in player_state.round_history if r.get("week") == current_week - 1
            ]
            if not week_rounds:
                week_rounds = [
                    r for r in player_state.round_history if r.get("week") == current_week
                ]

            if len(week_rounds) < 2:
                logger.debug("不足2轮故事，跳过角色画像合成")
                return

            # 2. Extract character mentions and behavioral observations
            char_evidence: Dict[str, List[str]] = {}
            protagonist_name = player_state.player_name or "主角"

            for r in week_rounds:
                story = r.get("event_description", "")
                continuation = r.get("story_continuation", "")
                choice = r.get("choice", "")
                full_text = story + " " + (continuation or "")

                all_chars = set()
                all_chars.add(protagonist_name)

                cs = player_state.character_settings or {}
                key_people = cs.get("relationships", {}).get("key_people", [])
                for person in key_people:
                    p_name = person.get("name", "")
                    if p_name and p_name in full_text:
                        all_chars.add(p_name)

                for char_name in player_state.characters.keys():
                    if char_name in full_text:
                        all_chars.add(char_name)

                round_name = r.get("date_info", {}).get("date_string", f"第{r.get('round', 0)+1}轮")

                for char in all_chars:
                    if char not in char_evidence:
                        char_evidence[char] = []

                    if char == protagonist_name and choice:
                        char_evidence[char].append(f"[{round_name}] 面对事件时选择了：{choice}")

                    for sentence in (
                        full_text.replace("。", "。\n")
                        .replace("！", "！\n")
                        .replace("？", "？\n")
                        .split("\n")
                    ):
                        sentence = sentence.strip()
                        if char in sentence and len(sentence) > 10:
                            char_evidence[char].append(f"[{round_name}] {sentence[:100]}")

            # 3. Filter: only characters with >= 2 evidence items, limit to top 3
            eligible = {name: evs for name, evs in char_evidence.items() if len(evs) >= 2}
            if not eligible:
                return

            sorted_chars = sorted(eligible.items(), key=lambda x: -len(x[1]))[:3]

            # 4. Synthesize profiles for eligible characters in parallel
            cs = player_state.character_settings or {}
            synthesizer = ProfileSynthesizer(ai_client)

            def _synthesize_one(char_name: str, evidence_list: list) -> tuple:
                """Synthesize profile for a single character. Returns (name, profile) or (name, None)."""
                try:
                    traits: list = []
                    if char_name == protagonist_name:
                        personality = cs.get("personality", {})
                        raw_traits = personality.get("traits", [])
                        if isinstance(raw_traits, list):
                            traits = raw_traits
                        elif isinstance(raw_traits, str):
                            traits = [raw_traits]
                    else:
                        for person in cs.get("relationships", {}).get("key_people", []):
                            if person.get("name") == char_name:
                                p = person.get("personality", "")
                                if p:
                                    traits = [p]
                                break

                    existing = profiles.get(char_name)
                    existing_dict = existing if isinstance(existing, dict) else None

                    evidence_limited = evidence_list[-8:]

                    new_profile = synthesizer.synthesize(
                        char_name=char_name,
                        traits=traits,
                        evidence=evidence_limited,
                        existing_profile=existing_dict,
                        language=language,
                    )
                    return (char_name, new_profile)
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"角色画像合成失败 ({char_name}): {e}")
                    return (char_name, None)
                except Exception as e:
                    logger.exception(f"角色画像合成失败 ({char_name}, unexpected): {e}")
                    return (char_name, None)

            with ThreadPoolExecutor(max_workers=min(len(sorted_chars), 3)) as executor:
                futures = [
                    executor.submit(_synthesize_one, char_name, evidence_list)
                    for char_name, evidence_list in sorted_chars
                ]
                for future in futures:
                    char_name, new_profile = future.result()
                    if new_profile is None:
                        continue
                    existing_before = profiles.get(char_name)
                    old_count = 0
                    if isinstance(existing_before, dict):
                        old_count = existing_before.get("evidence_count", 0)
                    new_profile["last_updated_week"] = current_week
                    profiles[char_name] = new_profile
                    logger.info(
                        f"角色画像{'更新' if old_count > 0 else '创建'}: {char_name} "
                        f"(evidence={new_profile['evidence_count']}, "
                        f"traits={new_profile['behavioral_traits'][:2]}...)"
                    )

            # 5. Save back and limit total profiles to 8
            if len(profiles) > 8:
                sorted_profiles = sorted(
                    profiles.items(),
                    key=lambda x: -(x[1].get("evidence_count", 0) if isinstance(x[1], dict) else 0),
                )
                profiles = dict(sorted_profiles[:8])

            wm_data["character_profiles"] = profiles
            logger.info(f"🎭 角色画像合成完成：{len(profiles)} 个角色有画像")

        except (ImportError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"角色画像合成失败（不影响主流程）: {e}")
        except Exception as e:
            logger.exception(f"角色画像合成失败（unexpected，不影响主流程）: {e}")

    # ------------------------------------------------------------------
    # Scheduled Events updates
    # ------------------------------------------------------------------

    @staticmethod
    def process_scheduled_events(
        player_state,
        scheduled_commitments: list,
        current_round: int,
    ) -> None:
        """处理从故事中提取的预定承诺，创建 ScheduledEvent。

        将带有具体时间点的承诺转换为预定事件，存储到 player_state.scheduled_events。

        Args:
            player_state: PlayerState 实例
            scheduled_commitments: 从 StoryAnalyzer.extract_scheduled_commitments() 返回的列表
            current_round: 当前轮次
        """
        if not player_state or not scheduled_commitments:
            return

        from src.game.scheduled_events import \
            create_scheduled_event_from_commitment
        from src.game.daily_timeline import is_daily_timeline, resolve_scheduled_date

        current_week = player_state.week

        for commitment in scheduled_commitments:
            description = commitment.get("description", "")
            parties = commitment.get("parties", [])
            scheduled_week = commitment.get("scheduled_week", -1)
            scheduled_round = commitment.get("scheduled_round", -1)
            importance = commitment.get("importance", "normal")
            event_hint = commitment.get("event_hint", "")

            if not description or scheduled_week < 0 or scheduled_round < 0:
                continue

            # 检查是否已存在相同的预定事件
            existing = player_state.scheduled_events
            duplicate = False
            for e in existing:
                if (
                    e.get("status") == "pending"
                    and e.get("description") == description
                    and e.get("scheduled_week") == scheduled_week
                    and e.get("scheduled_round") == scheduled_round
                ):
                    duplicate = True
                    break

            if duplicate:
                logger.debug(f"跳过重复的预定事件: {description[:40]}...")
                continue

            # 创建预定事件
            event = create_scheduled_event_from_commitment(
                description=description,
                parties=parties,
                scheduled_week=scheduled_week,
                scheduled_round=scheduled_round,
                current_week=current_week,
                current_round=current_round,
                importance=importance,
                event_hint=event_hint,
            )
            if is_daily_timeline(player_state):
                time_reference = str(commitment.get("time_reference") or "").strip()
                if time_reference:
                    try:
                        event.scheduled_date = resolve_scheduled_date(
                            player_state.timeline["current_date"], time_reference
                        )
                    except ValueError:
                        event.scheduled_date = ""
                if not event.scheduled_date:
                    from datetime import date, timedelta

                    start_date = date.fromisoformat(player_state.timeline["start_date"])
                    legacy_index = max(0, scheduled_week * 7 + (0, 2, 6)[scheduled_round])
                    event.scheduled_date = (start_date + timedelta(days=legacy_index)).isoformat()

            # 添加到 player_state
            player_state.add_scheduled_event(event)
            logger.info(
                f"📅 创建预定事件: {description[:40]}... "
                f"(第{scheduled_week}周, 轮次{scheduled_round})"
            )

    @staticmethod
    def extract_and_create_scheduled_events(
        player_state,
        full_story: str,
        ai_client,
        language: str,
    ) -> None:
        """从故事中提取预定承诺并创建预定事件。

        这是一个便捷方法，整合了提取和创建两个步骤。

        Args:
            player_state: PlayerState 实例
            full_story: 完整的故事文本
            ai_client: AIClient 实例
            language: 语言代码
        """
        if not player_state or not full_story:
            return

        try:
            from src.ai.story_analyzer import StoryAnalyzer

            analyzer = StoryAnalyzer(ai_client)

            # 提取预定承诺
            commitments = analyzer.extract_scheduled_commitments(
                story_text=full_story,
                current_week=player_state.week,
                current_round=player_state.current_round,
                language=language,
            )

            if commitments:
                # 创建预定事件
                WorldModelUpdater.process_scheduled_events(
                    player_state=player_state,
                    scheduled_commitments=commitments,
                    current_round=player_state.current_round,
                )

        except (ImportError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"提取预定承诺失败（不影响主流程）: {e}")
        except Exception as e:
            logger.exception(f"提取预定承诺失败（unexpected，不影响主流程）: {e}")

    @staticmethod
    def cleanup_triggered_scheduled_events(player_state, keep_weeks: int = 10) -> int:
        """清理已触发的旧预定事件。

        Args:
            player_state: PlayerState 实例
            keep_weeks: 保留最近多少周的事件

        Returns:
            清理的事件数量
        """
        if not player_state:
            return 0

        current_week = player_state.week
        to_remove = []

        for event in player_state.scheduled_events:
            if event.get("status") in ("triggered", "skipped", "merged"):
                scheduled_week = event.get("scheduled_week", 0)
                if current_week - scheduled_week > keep_weeks:
                    to_remove.append(event.get("event_id"))

        # 移除旧事件
        player_state.scheduled_events = [
            e for e in player_state.scheduled_events if e.get("event_id") not in to_remove
        ]

        if to_remove:
            logger.info(f"清理了 {len(to_remove)} 个旧的预定事件")

        return len(to_remove)

    # ------------------------------------------------------------------
    # Character sync from story
    # ------------------------------------------------------------------

    @staticmethod
    def sync_story_characters_to_settings(
        player_state,
        story_text: str,
        relationships_in_effects: Optional[Dict[str, int]] = None,
    ) -> None:
        """将故事中出现的人物同步到 character_settings 中。

        这个方法用于处理 AI 在故事中自行引入的人物，将他们正式添加到
        relationships.key_people 列表中，以保证后续故事的一致性。

        Args:
            player_state: PlayerState 实例
            story_text: 故事文本
            relationships_in_effects: 选项效果中的关系变化字典
        """
        if not player_state or not story_text:
            return

        character_settings = player_state.character_settings or {}
        if "relationships" not in character_settings:
            character_settings["relationships"] = {"key_people": []}
        if "key_people" not in character_settings["relationships"]:
            character_settings["relationships"]["key_people"] = []

        existing_names = set()
        protected_role_tokens = set()
        for person in character_settings["relationships"]["key_people"]:
            if isinstance(person, dict) and person.get("name"):
                existing_names.add(person["name"])
                for key in ("role", "relationship", "relationship_desc", "description"):
                    value = str(person.get(key) or "").strip()
                    if len(value) >= 2 and value not in GENERIC_CHARACTER_NAMES:
                        protected_role_tokens.add(value.lower())

        # 从家庭成员中收集
        family = character_settings.get("family", {})
        for member in family.get("family_members", []):
            if isinstance(member, dict) and member.get("name"):
                existing_names.add(member["name"])

        # 从 relationships_in_effects 中提取人物名
        new_names_from_effects = set()
        if relationships_in_effects:
            for name in relationships_in_effects.keys():
                # 排除通用称谓
                if name not in GENERIC_CHARACTER_NAMES and name not in existing_names:
                    new_names_from_effects.add(name)

        # 推断角色的辅助函数
        def infer_role_from_story(name: str, story: str) -> str:
            """根据故事上下文推断人物角色"""
            # 检查名字周围的上下文
            name_lower = name.lower()
            story_lower = story.lower()

            # 尝试匹配中英文关键词
            for lang in ["zh", "en"]:
                for keyword, role in ROLE_KEYWORDS[lang].items():
                    if keyword.lower() in story_lower:
                        # 检查关键词是否在名字附近（前后50字符内）
                        idx = story_lower.find(name_lower)
                        if idx >= 0:
                            context_start = max(0, idx - 50)
                            context_end = min(len(story_lower), idx + len(name) + 50)
                            context = story_lower[context_start:context_end]
                            if keyword.lower() in context:
                                return role

            return "故事中结识"

        def conflicts_with_preset_role(name: str, story: str, inferred_role: str) -> bool:
            """Return True when a new name is introduced as a substitute for preset roles."""
            if not protected_role_tokens:
                return False

            inferred = inferred_role.strip().lower()
            if inferred and inferred in protected_role_tokens:
                return True

            name_lower = name.lower()
            story_lower = story.lower()
            idx = story_lower.find(name_lower)
            if idx < 0:
                return False

            context_start = max(0, idx - 30)
            context_end = min(len(story_lower), idx + len(name_lower) + 30)
            context = story_lower[context_start:context_end]
            return any(token in context for token in protected_role_tokens)

        # 同步人物
        added_count = 0
        for name in new_names_from_effects:
            # 检查是否在故事文本中出现（避免添加效果中有但故事中没有的人物）
            if name in story_text or name.lower() in story_text.lower():
                # 创建基础人物条目
                affinity = (
                    relationships_in_effects.get(name, 50) if relationships_in_effects else 50
                )
                inferred_role = infer_role_from_story(name, story_text)
                if conflicts_with_preset_role(name, story_text, inferred_role):
                    logger.info(
                        "跳过疑似预设关系替身的新人物同步: %s role=%s",
                        name,
                        inferred_role,
                    )
                    continue
                new_person = {
                    "name": name,
                    "role": inferred_role,
                    "affinity": affinity,
                    "relationship_desc": "在故事中相遇",
                    "how_we_met": "在故事中自然出现",
                }
                character_settings["relationships"]["key_people"].append(new_person)
                existing_names.add(name)
                added_count += 1
                logger.info(f"✨ 同步故事人物到角色设定: {name}")

                # 同步到 player_state.relationships 字典
                if hasattr(player_state, "relationships") and isinstance(
                    player_state.relationships, dict
                ):
                    player_state.relationships[name] = affinity
                    logger.debug(f"已同步 {name} 的亲和度到 player_state.relationships")

        if added_count > 0:
            player_state.character_settings = character_settings
            logger.info(f"共同步了 {added_count} 个故事人物到角色设定")
