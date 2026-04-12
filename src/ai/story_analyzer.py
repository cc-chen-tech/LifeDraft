"""AI-driven Story Analyzer Agent.

Instead of relying on predefined extraction rules in the compression prompt,
this agent autonomously identifies ALL key facts, constraints, and narrative
elements from a generated story. The extracted facts are stored as
``DynamicFact`` objects in the WorldModel, giving it the flexibility to
capture information that rigid schemas would miss — such as character
emotional states, implicit promises, environmental details, possession
changes, knowledge revelations, and any other story-relevant fact.

Design Principles:
- The AI decides what is important, not hard-coded rules.
- Each fact carries a ``constraint_text`` that is directly injectable
  into future story-generation prompts.
- Facts have lifecycle management: importance, expiry, supersession.
- ★ 事实溯源：每个事实都记录来源摘录和哈希，便于后续验证追溯
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)


# ==================== Data Structures ====================


@dataclass
class DynamicFact:
    """A single world fact dynamically extracted by the AI analyzer.

    Unlike the fixed-schema fields (LocationInfo, CareerInfo, etc.),
    DynamicFact can represent *any* type of story-relevant information
    that the AI identifies.

    ★ 事实溯源：每个事实都记录其来源，以便后续验证时可以追溯到原文
    """

    # Core identification
    fact_id: str = ""  # Short unique id, e.g. "f_zhangwei_injury_w5"
    fact_type: str = ""  # AI-determined category, e.g.:
    #   "physical_state", "emotional_state",
    #   "possession", "knowledge", "environment",
    #   "social_dynamic", "secret", "habit",
    #   "implicit_promise", "threat", "goal",
    #   "relationship_shift", "financial", ...
    subject: str = ""  # Primary entity this fact is about
    description: str = ""  # What the fact is (human-readable)
    constraint_text: str = ""  # Direct constraint for future story generation,
    # e.g. "张伟右臂打着石膏，不能提重物或做剧烈运动"
    related_entities: List[str] = field(default_factory=list)

    # Lifecycle
    source_week: int = 0  # When this fact was established
    expiry_week: int = -1  # -1 = no expiry (permanent until superseded)
    importance: str = "normal"  # "critical" / "important" / "normal" / "minor"
    active: bool = True  # Whether this fact is still in effect

    # Supersession
    supersedes: str = ""  # fact_id that this fact replaces (if any)

    # ★ 事实溯源字段（新增）
    source_excerpt: str = ""  # 原文摘录，证明此事实的直接引用
    source_story_hash: str = ""  # 来源故事的哈希，用于快速定位原文

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "subject": self.subject,
            "description": self.description,
            "constraint_text": self.constraint_text,
            "related_entities": self.related_entities,
            "source_week": self.source_week,
            "expiry_week": self.expiry_week,
            "importance": self.importance,
            "active": self.active,
            "supersedes": self.supersedes,
            # ★ 溯源字段
            "source_excerpt": self.source_excerpt,
            "source_story_hash": self.source_story_hash,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DynamicFact":
        return cls(
            fact_id=d.get("fact_id", ""),
            fact_type=d.get("fact_type", ""),
            subject=d.get("subject", ""),
            description=d.get("description", ""),
            constraint_text=d.get("constraint_text", ""),
            related_entities=d.get("related_entities", []),
            source_week=d.get("source_week", 0),
            expiry_week=d.get("expiry_week", -1),
            importance=d.get("importance", "normal"),
            active=d.get("active", True),
            supersedes=d.get("supersedes", ""),
            # ★ 溯源字段
            source_excerpt=d.get("source_excerpt", ""),
            source_story_hash=d.get("source_story_hash", ""),
        )


# ==================== Story Analyzer Agent ====================


class StoryAnalyzer:
    """AI agent that autonomously identifies key facts and constraints
    from generated stories.

    Unlike the compression-prompt extraction (which uses rigid schemas
    like ``location_updates``, ``career_updates``), this agent lets the
    AI freely identify *any* narratively significant information and
    express it as constraints for future story generation.
    """

    def __init__(self, client):
        """
        Args:
            client: AIClient instance (or any object with a ``call`` method).
        """
        self.client = client

    def analyze_story(
        self,
        story_text: str,
        player_choice: str,
        existing_facts: List[DynamicFact],
        current_week: int,
        character_settings: Dict[str, Any],
        language: str,
    ) -> List[DynamicFact]:
        """Analyze a story and extract dynamic facts.

        Args:
            story_text: The full story text (event + continuation).
            player_choice: The choice the player made.
            existing_facts: Currently active dynamic facts for context.
            current_week: Current game week number.
            character_settings: Character settings for name references.
            language: Language code ('zh' or 'en').

        Returns:
            List of new/updated DynamicFact objects.
        """
        if not story_text:
            return []

        try:
            from config.prompts import get_story_analysis_prompt

            # ★ 计算故事文本的哈希，用于事实溯源
            story_hash = hashlib.md5(story_text.encode("utf-8")).hexdigest()[:16]

            # Build existing facts context for the AI
            existing_context = self._build_existing_facts_context(existing_facts, language)

            prompt = get_story_analysis_prompt(
                story_text=story_text,
                player_choice=player_choice,
                existing_facts_context=existing_context,
                character_settings=character_settings,
                current_week=current_week,
                language=language,
            )

            sys_prompt = get_system_prompt("story_analyzer", language)

            response = self.client.call(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.3,  # Low temperature for precise extraction
                max_tokens=4096,
            )

            # ★ 传递 story_hash 用于溯源
            return self._parse_analysis_response(response, current_week, existing_facts, story_hash)

        except Exception as e:
            logger.error(f"Story analysis failed: {e}")
            return []

    def _build_existing_facts_context(
        self, existing_facts: List[DynamicFact], language: str
    ) -> str:
        """Build a text summary of existing active facts for the AI."""
        active = [f for f in existing_facts if f.active]
        if not active:
            return ""

        lines = []
        if language == "zh":
            lines.append("【当前已记录的世界事实】")
            for f in active:
                lines.append(
                    f"- [{f.fact_type}] {f.subject}：{f.description}"
                    f"（约束：{f.constraint_text}）"
                )
        else:
            lines.append("[Currently Recorded World Facts]")
            for f in active:
                lines.append(
                    f"- [{f.fact_type}] {f.subject}: {f.description}"
                    f" (constraint: {f.constraint_text})"
                )
        return "\n".join(lines)

    def _parse_analysis_response(
        self,
        response: str,
        current_week: int,
        existing_facts: List[DynamicFact],
        story_hash: str = "",
    ) -> List[DynamicFact]:
        """Parse the AI response into DynamicFact objects.

        Args:
            response: Raw AI response text
            current_week: Current game week number
            existing_facts: Existing dynamic facts
            story_hash: ★ 来源故事的哈希，用于事实溯源

        Returns:
            List of new/updated DynamicFact objects
        """
        try:
            data = extract_json(response)
            if not data:
                logger.warning("Could not parse story analysis response as JSON")
                return []

            raw_facts = data.get("facts", [])
            results: List[DynamicFact] = []

            existing_ids = {f.fact_id for f in existing_facts}

            for raw in raw_facts:
                action = raw.get("action", "new")
                fact_type = raw.get("fact_type", "")
                subject = raw.get("subject", "")
                description = raw.get("description", "")
                constraint_text = raw.get("constraint_text", "")

                if not subject or not description:
                    continue

                if action == "new":
                    # Generate a fact_id
                    safe_subject = subject.replace(" ", "_")[:10]
                    safe_type = fact_type.replace(" ", "_")[:10]
                    fact_id = f"f_{safe_subject}_{safe_type}_w{current_week}"
                    # Avoid duplicate ids
                    counter = 0
                    base_id = fact_id
                    while fact_id in existing_ids:
                        counter += 1
                        fact_id = f"{base_id}_{counter}"

                    importance = raw.get("importance", "normal")
                    if importance not in ("critical", "important", "normal", "minor"):
                        importance = "normal"

                    expiry_week = raw.get("expiry_week", -1)
                    if not isinstance(expiry_week, int):
                        expiry_week = -1

                    fact = DynamicFact(
                        fact_id=fact_id,
                        fact_type=fact_type,
                        subject=subject,
                        description=description,
                        constraint_text=constraint_text,
                        related_entities=raw.get("related_entities", []),
                        source_week=current_week,
                        expiry_week=expiry_week,
                        importance=importance,
                        active=True,
                        supersedes=raw.get("supersedes", ""),
                        # ★ 事实溯源
                        source_excerpt=raw.get("source_excerpt", ""),
                        source_story_hash=story_hash,
                    )
                    results.append(fact)
                    existing_ids.add(fact_id)

                    # ★ 日志包含溯源信息
                    excerpt_preview = (
                        raw.get("source_excerpt", "")[:30] + "..."
                        if raw.get("source_excerpt")
                        else "无"
                    )
                    logger.info(
                        f"🔍 新动态事实: [{fact_type}] {subject} - "
                        f"{description[:40]}... (约束: {constraint_text[:40]}...) 溯源:[{excerpt_preview}]"
                    )

                elif action == "update":
                    # Find the existing fact to update
                    target_id = raw.get("target_fact_id", "")
                    if not target_id:
                        # Try matching by subject + type
                        for ef in existing_facts:
                            if ef.active and ef.subject == subject and ef.fact_type == fact_type:
                                target_id = ef.fact_id
                                break

                    if target_id:
                        # Create a new fact that supersedes the old one
                        safe_subject = subject.replace(" ", "_")[:10]
                        safe_type = fact_type.replace(" ", "_")[:10]
                        fact_id = f"f_{safe_subject}_{safe_type}_w{current_week}"
                        counter = 0
                        base_id = fact_id
                        while fact_id in existing_ids:
                            counter += 1
                            fact_id = f"{base_id}_{counter}"

                        fact = DynamicFact(
                            fact_id=fact_id,
                            fact_type=fact_type,
                            subject=subject,
                            description=description,
                            constraint_text=constraint_text,
                            related_entities=raw.get("related_entities", []),
                            source_week=current_week,
                            expiry_week=raw.get("expiry_week", -1),
                            importance=raw.get("importance", "normal"),
                            active=True,
                            supersedes=target_id,
                            # ★ 事实溯源
                            source_excerpt=raw.get("source_excerpt", ""),
                            source_story_hash=story_hash,
                        )
                        results.append(fact)
                        existing_ids.add(fact_id)
                        logger.info(
                            f"🔄 更新动态事实: [{fact_type}] {subject} - "
                            f"{description[:40]}... (取代: {target_id})"
                        )

                elif action == "invalidate":
                    # Mark an existing fact as inactive
                    target_id = raw.get("target_fact_id", "")
                    if target_id:
                        for ef in existing_facts:
                            if ef.fact_id == target_id:
                                ef.active = False
                                logger.info(
                                    f"❌ 失效动态事实: {target_id} - {ef.description[:40]}..."
                                )
                                break

            return results

        except Exception as e:
            logger.error(f"Failed to parse story analysis response: {e}")
            return []

    # ==================== Scheduled Commitment Extraction ====================

    def extract_scheduled_commitments(
        self,
        story_text: str,
        current_week: int,
        current_round: int,
        language: str = "zh",
    ) -> List[Dict[str, Any]]:
        """从故事中提取带有具体时间点的承诺，用于创建预定事件。

        Args:
            story_text: 故事文本
            current_week: 当前周数
            current_round: 当前轮次
            language: 语言

        Returns:
            预定承诺字典列表，每个包含：
            - description: 承诺描述
            - parties: 涉及人物
            - scheduled_week: 预定周数
            - scheduled_round: 预定轮次
            - importance: 重要程度
            - event_hint: 事件提示
        """
        if not story_text:
            return []

        try:
            from config.prompts.world_prompts import get_scheduled_commitment_extraction_prompt

            prompt = get_scheduled_commitment_extraction_prompt(
                story=story_text,
                current_week=current_week,
                current_round=current_round,
                language=language,
            )

            sys_prompt = get_system_prompt("story_analyzer", language)

            response = self.client.call(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.3,  # Low temperature for precise extraction
                max_tokens=2048,
            )

            return self._parse_scheduled_commitments_response(response)

        except Exception as e:
            logger.error(f"Failed to extract scheduled commitments: {e}")
            return []

    def _parse_scheduled_commitments_response(
        self,
        response: str,
    ) -> List[Dict[str, Any]]:
        """解析预定承诺提取的AI响应。

        Args:
            response: AI响应文本

        Returns:
            预定承诺字典列表
        """
        try:
            data = extract_json(response)
            if not data:
                logger.warning("Could not parse scheduled commitments response as JSON")
                return []

            commitments = data.get("scheduled_commitments", [])
            results: List[Dict[str, Any]] = []

            for c in commitments:
                # 验证必要字段
                description = c.get("description", "")
                scheduled_week = c.get("scheduled_week", -1)
                scheduled_round = c.get("scheduled_round", -1)

                if not description or scheduled_week < 0 or scheduled_round < 0:
                    continue

                # 验证轮次范围
                if scheduled_round not in (0, 1, 2):
                    logger.warning(f"Invalid scheduled_round: {scheduled_round}, skipping")
                    continue

                # 验证重要程度
                importance = c.get("importance", "normal")
                if importance not in ("critical", "normal", "minor"):
                    importance = "normal"

                result = {
                    "description": description,
                    "parties": c.get("parties", []),
                    "time_reference": c.get("time_reference", ""),
                    "scheduled_week": scheduled_week,
                    "scheduled_round": scheduled_round,
                    "importance": importance,
                    "event_hint": c.get("event_hint", ""),
                }
                results.append(result)

                logger.info(
                    f"📅 提取到预定承诺: {description[:40]}... "
                    f"(第{scheduled_week}周, 轮次{scheduled_round}, 重要度:{importance})"
                )

            return results

        except Exception as e:
            logger.error(f"Failed to parse scheduled commitments response: {e}")
            return []
