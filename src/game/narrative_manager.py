"""Narrative state management: storylines, facts, foreshadowing seeds, character habits.

Extracted from game_loop.py to reduce God Class complexity.
All methods accept a PlayerState instance as the first argument instead of
relying on ``self.player_state``, making the module stateless and testable.
"""

import logging
import math
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NarrativeManager:
    """Manages storylines, world facts, foreshadowing seeds, and character habits."""

    # ------------------------------------------------------------------
    # Storyline updates
    # ------------------------------------------------------------------

    @staticmethod
    def process_storyline_updates(player_state, storyline_updates: list) -> None:
        """Process storyline updates from story compression.

        Actions: new / resolved / continues.
        Also cleans up stale storylines with graduated expiry.
        """
        if not player_state or not storyline_updates:
            return

        current_week = player_state.week

        for update in storyline_updates:
            action = update.get("action", "")
            description = update.get("description", "")

            if not action or not description:
                continue

            if action == "new":
                new_storyline = {
                    "description": description,
                    "created_week": current_week,
                    "importance": update.get("importance", "medium"),
                    "status": "active",
                    "related_characters": update.get("related_characters", []),
                    "last_mentioned_week": current_week,
                }
                player_state.pending_storylines.append(new_storyline)
                logger.info(f"New pending storyline: {description[:50]}...")

            elif action == "resolved":
                resolved = False
                for i, sl in enumerate(player_state.pending_storylines):
                    if (
                        description.lower() in sl.get("description", "").lower()
                        or sl.get("description", "").lower() in description.lower()
                    ):
                        player_state.pending_storylines.pop(i)
                        logger.info(f"Resolved storyline: {sl.get('description', '')[:50]}...")
                        resolved = True
                        break
                if not resolved:
                    logger.debug(f"Could not match resolved storyline: {description[:50]}...")

            elif action == "continues":
                for sl in player_state.pending_storylines:
                    if (
                        description.lower() in sl.get("description", "").lower()
                        or sl.get("description", "").lower() in description.lower()
                    ):
                        sl["last_mentioned_week"] = current_week
                        logger.info(f"Continued storyline: {sl.get('description', '')[:50]}...")
                        break

        # Clean up stale storylines with graduated approach
        updated_storylines = []
        for sl in player_state.pending_storylines:
            weeks_since_mention = current_week - sl.get("last_mentioned_week", 0)
            importance = sl.get("importance", "medium")

            if weeks_since_mention > 20:
                logger.info(
                    f"Removing expired storyline ({weeks_since_mention} weeks dormant): {sl.get('description', '')[:50]}..."
                )
                continue
            if importance == "medium" and weeks_since_mention > 12:
                logger.info(
                    f"Removing stale medium storyline ({weeks_since_mention} weeks dormant): {sl.get('description', '')[:50]}..."
                )
                continue
            if importance == "high" and weeks_since_mention > 8:
                sl["importance"] = "medium"
                logger.info(
                    f"Demoted high->medium storyline ({weeks_since_mention} weeks dormant): {sl.get('description', '')[:50]}..."
                )

            updated_storylines.append(sl)

        player_state.pending_storylines = updated_storylines

    # ------------------------------------------------------------------
    # Overdue storyline escalation
    # ------------------------------------------------------------------

    @staticmethod
    def escalate_overdue_storylines(player_state) -> int:
        """检测并标记过期的高重要性剧情线。

        当一条 high 重要性剧情线长期未被提及或推进时（沉寂 > 4 周），
        将其标记为 overdue，使 prompt 构建时对其采用强制约束（"本轮必须处理"）。

        这解决了以下系统性问题：
        - pending_storylines 的 "至少涉及一条" 约束太弱，大量剧情线被长期忽略
        - 包含时间承诺的剧情线（如"下月初一"）没有升级机制，只会被降级后移除
        - 三套追踪系统（storylines / commitments / scheduled_events）互不联动

        Args:
            player_state: PlayerState 实例

        Returns:
            被升级标记为 overdue 的剧情线数量
        """
        if not player_state or not player_state.pending_storylines:
            return 0

        current_week = player_state.week
        escalated_count = 0

        # 时间相关关键词 — 包含这些词的剧情线更可能有隐含的时间承诺
        time_keywords = [
            "初一", "十五", "月底", "月初", "下月", "约定", "仪式",
            "承诺", "期限", "截止", "到期", "答应", "保证",
            "天后", "周后", "月后", "明天", "后天",
        ]

        for sl in player_state.pending_storylines:
            importance = sl.get("importance", "medium")
            if importance != "high":
                continue

            # 如果已经标记为 overdue，跳过
            if sl.get("overdue", False):
                continue

            weeks_since_mention = current_week - sl.get("last_mentioned_week", 0)

            # 判断是否包含时间承诺关键词
            desc = sl.get("description", "")
            has_time_ref = any(kw in desc for kw in time_keywords)

            # 升级条件：
            # - 含时间关键词的剧情线：沉寂 > 3 周即升级（它们更紧迫）
            # - 普通高重要性剧情线：沉寂 > 5 周才升级
            threshold = 3 if has_time_ref else 5

            if weeks_since_mention >= threshold:
                sl["overdue"] = True
                sl["overdue_since_week"] = current_week
                escalated_count += 1
                logger.warning(
                    f"🚨 剧情线升级为 overdue: {desc[:50]}... "
                    f"(沉寂{weeks_since_mention}周, 含时间引用={has_time_ref})"
                )

        if escalated_count > 0:
            logger.info(f"🚨 共 {escalated_count} 条剧情线被升级为 overdue")

        return escalated_count

    # ------------------------------------------------------------------
    # Fact updates
    # ------------------------------------------------------------------

    @staticmethod
    def process_fact_updates(player_state, fact_updates: list) -> None:
        """Process world fact updates from story compression.

        Actions: new / update / remove.
        Limits total facts to 50.
        """
        if not player_state or not fact_updates:
            return

        current_week = player_state.week

        for update in fact_updates:
            action = update.get("action", "")
            subject = update.get("subject", "")

            if not action or not subject:
                continue

            if action == "new":
                category = update.get("category", "situation")
                fact_text = update.get("fact", "")
                if not fact_text:
                    continue
                player_state.established_facts = [
                    f
                    for f in player_state.established_facts
                    if not (
                        f.get("subject", "").lower() == subject.lower()
                        and f.get("category", "") == category
                    )
                ]
                new_fact = {
                    "fact": fact_text,
                    "subject": subject,
                    "category": category,
                    "established_week": current_week,
                }
                player_state.established_facts.append(new_fact)
                logger.info(f"New world fact: [{category}] {subject}: {fact_text[:50]}...")

            elif action == "update":
                fact_text = update.get("fact", "")
                category = update.get("category", "")
                if not fact_text:
                    continue
                updated = False
                for f in player_state.established_facts:
                    if f.get("subject", "").lower() == subject.lower():
                        if category:
                            f["category"] = category
                        f["fact"] = fact_text
                        f["established_week"] = current_week
                        logger.info(f"Updated world fact: {subject}: {fact_text[:50]}...")
                        updated = True
                        break
                if not updated:
                    new_fact = {
                        "fact": fact_text,
                        "subject": subject,
                        "category": category or "situation",
                        "established_week": current_week,
                    }
                    player_state.established_facts.append(new_fact)
                    logger.info(
                        f"New world fact (from update): [{category}] {subject}: {fact_text[:50]}..."
                    )

            elif action == "remove":
                before_count = len(player_state.established_facts)
                player_state.established_facts = [
                    f
                    for f in player_state.established_facts
                    if f.get("subject", "").lower() != subject.lower()
                ]
                removed_count = before_count - len(player_state.established_facts)
                if removed_count > 0:
                    logger.info(f"Removed {removed_count} world fact(s) for: {subject}")
                else:
                    logger.debug(f"Could not find world fact to remove: {subject}")

        # Limit total facts
        if len(player_state.established_facts) > 50:
            player_state.established_facts = sorted(
                player_state.established_facts,
                key=lambda f: f.get("established_week", 0),
                reverse=True,
            )[:50]

    # ------------------------------------------------------------------
    # Foreshadowing seed selection
    # ------------------------------------------------------------------

    @staticmethod
    def select_foreshadowing_seed(player_state) -> Optional[Dict[str, Any]]:
        """Select and activate a mature foreshadowing seed based on probability.

        Returns the activated seed dict, or None.
        """
        if not player_state or not player_state.foreshadowing_seeds:
            return None

        current_week = player_state.week
        eligible_seeds: List[tuple] = []

        active_characters: set = set()
        active_storyline_keywords: set = set()
        for sl in player_state.pending_storylines:
            for char in sl.get("related_characters", []):
                active_characters.add(char.lower())
            desc = sl.get("description", "").lower()
            active_storyline_keywords.update(desc.split()[:5])

        for seed in player_state.foreshadowing_seeds:
            if seed.get("activated", False):
                continue

            planted_week = seed.get("planted_week", 0)
            base_maturity = seed.get("maturity_weeks", 8)
            obfuscation = seed.get("obfuscation_level", 0.5)
            weight = seed.get("narrative_weight", "supporting")
            weeks_since_planted = current_week - planted_week

            maturity_multiplier = 0.8 + obfuscation * 0.7
            effective_maturity = int(base_maturity * maturity_multiplier)

            if weeks_since_planted < effective_maturity:
                continue
            if weeks_since_planted > 60:
                continue

            overshoot = weeks_since_planted - effective_maturity
            peak_at = effective_maturity

            base_prob = 0.08
            peak_prob = 0.22

            if overshoot <= peak_at:
                prob = base_prob + (peak_prob - base_prob) * (overshoot / peak_at)
            else:
                decay_weeks = overshoot - peak_at
                prob = peak_prob * math.exp(-decay_weeks / 20)

            weight_multiplier = {"major": 1.8, "supporting": 1.0, "minor": 0.6}.get(weight, 1.0)
            prob *= weight_multiplier

            seed_characters = {c.lower() for c in seed.get("related_characters", [])}
            if seed_characters & active_characters:
                prob *= 2.0
                logger.debug(
                    f"Foreshadowing context match doubled: {seed.get('description', '')[:30]}..."
                )

            seed_storylines = seed.get("related_storylines", [])
            if seed_storylines:
                for ssl in seed_storylines:
                    if any(kw in ssl.lower() for kw in active_storyline_keywords if len(kw) > 1):
                        prob *= 1.5
                        break

            prob = max(prob, 0.03)
            prob = min(prob, 0.40)

            eligible_seeds.append((seed, prob))

        if not eligible_seeds:
            return None

        for seed, prob in eligible_seeds:
            if random.random() < prob:
                seed["activated"] = True
                seed["activation_week"] = current_week

                metrics = player_state.foreshadowing_metrics
                recovery_distance = current_week - seed.get("planted_week", 0)
                metrics["total_activated"] += 1
                metrics["recovery_distances"].append(recovery_distance)
                if len(metrics["recovery_distances"]) > 20:
                    metrics["recovery_distances"] = metrics["recovery_distances"][-20:]
                metrics["avg_recovery_distance"] = sum(metrics["recovery_distances"]) / len(
                    metrics["recovery_distances"]
                )

                logger.info(
                    f"Foreshadowing activated! "
                    f"seed='{seed.get('description', '')[:50]}...', "
                    f"type={seed.get('seed_type')}, weight={seed.get('narrative_weight')}, "
                    f"planted week {seed.get('planted_week', 0)}, "
                    f"distance {recovery_distance} weeks, prob {prob:.1%}"
                )
                return seed  # type: ignore[no-any-return]

        logger.debug(f"No foreshadowing activated this round ({len(eligible_seeds)} candidates)")
        return None

    # ------------------------------------------------------------------
    # Foreshadowing seed processing
    # ------------------------------------------------------------------

    @staticmethod
    def process_foreshadowing_seeds(player_state, new_seeds: list) -> None:
        """Process new foreshadowing seeds from story compression.

        Adds new seeds, cleans expired/activated seeds, limits total to 20 active.
        """
        if not player_state:
            return

        current_week = player_state.week
        metrics = player_state.foreshadowing_metrics

        # 1. Add new seeds
        for seed in new_seeds:
            desc = seed.get("description", "")
            if not desc:
                continue

            is_duplicate = False
            for existing in player_state.foreshadowing_seeds:
                if (
                    desc.lower() in existing.get("description", "").lower()
                    or existing.get("description", "").lower() in desc.lower()
                ):
                    is_duplicate = True
                    break
            if is_duplicate:
                logger.debug(f"Skipping duplicate foreshadowing seed: {desc[:30]}...")
                continue

            seed_type = seed.get("seed_type", "mystery")
            maturity_map = {
                "mystery": 8,
                "relationship": 6,
                "warning": 10,
                "opportunity": 5,
                "consequence": 12,
                "character_return": 8,
            }
            maturity = maturity_map.get(seed_type, 8)

            obfuscation = seed.get("obfuscation_level", 0.5)
            if isinstance(obfuscation, (int, float)):
                obfuscation = max(0.0, min(1.0, float(obfuscation)))
            else:
                obfuscation = 0.5

            narrative_weight = seed.get("narrative_weight", "supporting")
            if narrative_weight not in ("minor", "supporting", "major"):
                narrative_weight = "supporting"

            recycle_method = seed.get("recycle_method", "echo")
            valid_methods = (
                "revelation",
                "confirmation",
                "ironic_twist",
                "escalation",
                "echo",
            )
            if recycle_method not in valid_methods:
                recycle_method = "echo"

            related_storylines = []
            seed_chars = {c.lower() for c in seed.get("related_characters", [])}
            for sl in player_state.pending_storylines:
                sl_chars = {c.lower() for c in sl.get("related_characters", [])}
                if seed_chars & sl_chars:
                    related_storylines.append(sl.get("description", "")[:50])

            new_seed = {
                "description": desc,
                "original_context": seed.get("original_context", "")[:80],
                "planted_week": current_week,
                "related_characters": seed.get("related_characters", []),
                "seed_type": seed_type,
                "maturity_weeks": maturity,
                "activated": False,
                "activation_week": None,
                "obfuscation_level": obfuscation,
                "narrative_weight": narrative_weight,
                "recycle_method": recycle_method,
                "related_storylines": related_storylines,
            }
            player_state.foreshadowing_seeds.append(new_seed)
            metrics["total_planted"] += 1
            logger.info(
                f"New foreshadowing seed: [{seed_type}] {desc[:50]}... "
                f"(maturity {maturity}w, obfuscation {obfuscation:.1f}, "
                f"weight={narrative_weight}, recycle={recycle_method})"
            )
            if related_storylines:
                logger.info(f"  Related storylines: {related_storylines}")

        # 2. Clean expired / activated seeds
        cleaned_seeds = []
        for seed in player_state.foreshadowing_seeds:
            weeks_since_planted = current_week - seed.get("planted_week", 0)

            if seed.get("activated", False):
                activation_week = seed.get("activation_week", 0)
                if current_week - activation_week > 4:
                    logger.debug(f"Removing activated seed: {seed.get('description', '')[:30]}...")
                    continue

            if not seed.get("activated", False) and weeks_since_planted > 60:
                metrics["total_expired"] += 1
                logger.info(
                    f"Foreshadowing seed expired ({weeks_since_planted}w): {seed.get('description', '')[:30]}..."
                )
                continue

            cleaned_seeds.append(seed)

        player_state.foreshadowing_seeds = cleaned_seeds

        # 3. Limit active seeds to 20
        active_seeds = [
            s for s in player_state.foreshadowing_seeds if not s.get("activated", False)
        ]
        if len(active_seeds) > 20:
            weight_order = {"major": 0, "supporting": 1, "minor": 2}
            active_seeds.sort(
                key=lambda s: (
                    weight_order.get(s.get("narrative_weight", "supporting"), 1),
                    -(s.get("planted_week", 0)),
                )
            )
            seeds_to_remove = set(id(s) for s in active_seeds[20:])
            player_state.foreshadowing_seeds = [
                s
                for s in player_state.foreshadowing_seeds
                if s.get("activated", False) or id(s) not in seeds_to_remove
            ]
            logger.info("Foreshadowing seeds exceeded limit, keeping top 20 by weight+recency")

    # ------------------------------------------------------------------
    # Habit updates
    # ------------------------------------------------------------------

    @staticmethod
    def process_habit_updates(player_state, habit_updates: list) -> None:
        """Process character habit updates from story compression.

        Actions: new / strengthen / weaken / remove / change.
        Limits per-character habits to 10.
        """
        if not player_state or not habit_updates:
            return

        current_week = player_state.week
        strength_order = ["emerging", "moderate", "strong"]

        for update in habit_updates:
            action = update.get("action", "")
            character = update.get("character", "")
            habit_desc = update.get("habit", "")

            if not action or not character:
                continue

            if action == "new":
                if not habit_desc:
                    continue
                exists = False
                for h in player_state.character_habits:
                    if h.get("character", "").lower() == character.lower() and (
                        habit_desc.lower() in h.get("habit", "").lower()
                        or h.get("habit", "").lower() in habit_desc.lower()
                    ):
                        exists = True
                        h["last_seen_week"] = current_week
                        idx = (
                            strength_order.index(h.get("strength", "moderate"))
                            if h.get("strength", "moderate") in strength_order
                            else 1
                        )
                        if idx < len(strength_order) - 1:
                            h["strength"] = strength_order[idx + 1]
                        logger.info(
                            f"Habit exists, strengthened: {character} - {habit_desc[:30]}... -> {h['strength']}"
                        )
                        break

                if not exists:
                    category = update.get("category", "behavioral")
                    valid_categories = (
                        "behavioral",
                        "speech",
                        "emotional",
                        "social",
                        "lifestyle",
                    )
                    if category not in valid_categories:
                        category = "behavioral"
                    strength = update.get("strength", "emerging")
                    if strength not in strength_order:
                        strength = "emerging"
                    new_habit = {
                        "character": character,
                        "habit": habit_desc,
                        "category": category,
                        "established_week": current_week,
                        "last_seen_week": current_week,
                        "strength": strength,
                        "origin": update.get("origin", ""),
                    }
                    player_state.character_habits.append(new_habit)
                    logger.info(
                        f"New habit: {character} - [{category}/{strength}] {habit_desc[:50]}"
                    )

            elif action == "strengthen":
                for h in player_state.character_habits:
                    if h.get("character", "").lower() == character.lower() and (
                        habit_desc.lower() in h.get("habit", "").lower()
                        or h.get("habit", "").lower() in habit_desc.lower()
                    ):
                        h["last_seen_week"] = current_week
                        idx = (
                            strength_order.index(h.get("strength", "moderate"))
                            if h.get("strength", "moderate") in strength_order
                            else 1
                        )
                        if idx < len(strength_order) - 1:
                            h["strength"] = strength_order[idx + 1]
                        logger.info(
                            f"Habit strengthened: {character} - {habit_desc[:30]}... -> {h['strength']}"
                        )
                        break

            elif action == "weaken":
                for h in player_state.character_habits:
                    if h.get("character", "").lower() == character.lower() and (
                        habit_desc.lower() in h.get("habit", "").lower()
                        or h.get("habit", "").lower() in habit_desc.lower()
                    ):
                        h["last_seen_week"] = current_week
                        idx = (
                            strength_order.index(h.get("strength", "moderate"))
                            if h.get("strength", "moderate") in strength_order
                            else 1
                        )
                        if idx > 0:
                            h["strength"] = strength_order[idx - 1]
                            logger.info(
                                f"Habit weakened: {character} - {habit_desc[:30]}... -> {h['strength']}"
                            )
                        else:
                            player_state.character_habits.remove(h)
                            reason = update.get("reason", "natural decay")
                            logger.info(
                                f"Habit faded: {character} - {habit_desc[:30]}... (reason: {reason})"
                            )
                        break

            elif action == "remove":
                for h in player_state.character_habits:
                    if h.get("character", "").lower() == character.lower() and (
                        habit_desc.lower() in h.get("habit", "").lower()
                        or h.get("habit", "").lower() in habit_desc.lower()
                    ):
                        reason = update.get("reason", "unknown")
                        player_state.character_habits.remove(h)
                        logger.info(
                            f"Habit removed: {character} - {habit_desc[:30]}... (reason: {reason})"
                        )
                        break

            elif action == "change":
                old_habit = update.get("old_habit", "")
                new_habit_desc = update.get("new_habit", "")
                if not old_habit or not new_habit_desc:
                    continue
                found = False
                for h in player_state.character_habits:
                    if h.get("character", "").lower() == character.lower() and (
                        old_habit.lower() in h.get("habit", "").lower()
                        or h.get("habit", "").lower() in old_habit.lower()
                    ):
                        old_desc = h["habit"]
                        h["habit"] = new_habit_desc
                        h["last_seen_week"] = current_week
                        if update.get("category"):
                            h["category"] = update["category"]
                        if update.get("strength"):
                            h["strength"] = (
                                update["strength"]
                                if update["strength"] in strength_order
                                else h["strength"]
                            )
                        reason = update.get("reason", "unknown")
                        logger.info(
                            f"Habit changed: {character} - '{old_desc[:20]}' -> '{new_habit_desc[:20]}' (reason: {reason})"
                        )
                        found = True
                        break
                if not found:
                    category = update.get("category", "behavioral")
                    if category not in (
                        "behavioral",
                        "speech",
                        "emotional",
                        "social",
                        "lifestyle",
                    ):
                        category = "behavioral"
                    strength = update.get("strength", "emerging")
                    if strength not in strength_order:
                        strength = "emerging"
                    new_habit = {
                        "character": character,
                        "habit": new_habit_desc,
                        "category": category,
                        "established_week": current_week,
                        "last_seen_week": current_week,
                        "strength": strength,
                        "origin": update.get("reason", ""),
                    }
                    player_state.character_habits.append(new_habit)
                    logger.info(
                        f"Habit change (old not found, adding new): {character} - {new_habit_desc[:30]}"
                    )

        # Limit per-character habits to 10
        habits_by_char: Dict[str, list] = {}
        for h in player_state.character_habits:
            char = h.get("character", "")
            if char not in habits_by_char:
                habits_by_char[char] = []
            habits_by_char[char].append(h)

        cleaned_habits = []
        for char, habits in habits_by_char.items():
            if len(habits) > 10:
                strength_rank = {"strong": 0, "moderate": 1, "emerging": 2}
                habits.sort(
                    key=lambda h: (
                        strength_rank.get(h.get("strength", "moderate"), 1),
                        -(h.get("last_seen_week", 0)),
                    )
                )
                cleaned_habits.extend(habits[:10])
                logger.info(f"Character {char} habits exceeded limit, keeping top 10")
            else:
                cleaned_habits.extend(habits)

        player_state.character_habits = cleaned_habits
