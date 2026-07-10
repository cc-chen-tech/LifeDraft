"""AI-driven story consistency validator."""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.ai.system_prompts import get_system_prompt
from src.ai.utils import extract_json

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyIssue:
    """Single consistency issue found in a story."""

    dimension: str  # "geographic" / "career" / "personality" / "temporal" / "commitment" / "causal" / "fabrication"
    severity: str  # "CRITICAL" / "WARNING"
    description: str  # Human-readable description of the issue
    fix_suggestion: str  # Suggested fix for the issue


@dataclass
class ValidationResult:
    """Result of consistency validation."""

    passed: bool
    issues: List[ConsistencyIssue] = field(default_factory=list)
    fix_instructions: str = ""  # Concatenated fix instructions for retry prompt injection

    @property
    def has_critical_issues(self) -> bool:
        return any(i.severity == "CRITICAL" for i in self.issues)

    @property
    def critical_issues(self) -> List[ConsistencyIssue]:
        return [i for i in self.issues if i.severity == "CRITICAL"]

    @property
    def warning_issues(self) -> List[ConsistencyIssue]:
        return [i for i in self.issues if i.severity == "WARNING"]


class ConsistencyValidator:
    """
    AI-driven story consistency validator.

    Uses a second AI call to check generated stories against the world model
    for consistency across 7 dimensions: geographic, career, personality,
    temporal, commitment, causal, and fabrication.
    """

    def __init__(self, client):
        """
        Initialize the validator.

        Args:
            client: AIClient instance (or any object with a ``call`` method)
        """
        self.client = client

    def validate_story(
        self,
        story_text: str,
        world_model,
        player_state_dict: Dict[str, Any],
        character_settings: Dict[str, Any],
        language: str,
        story_history: Optional[List[Dict[str, Any]]] = None,
        run_ai_validation: bool = True,
    ) -> ValidationResult:
        """
        Validate a generated story for consistency with the world model.

        Args:
            story_text: The generated story text to validate
            world_model: WorldModel instance with current world state
            player_state_dict: Player state as dict for context
            character_settings: Character settings for personality reference
            language: Language code ('zh' or 'en')
            story_history: 可选的历史故事列表

        Returns:
            ValidationResult with pass/fail status, issues, and fix instructions
        """
        if not story_text or not world_model:
            return ValidationResult(passed=True)

        try:
            # P1-7 deterministic authority runs before any model-based judge.
            # It also runs in fast mode, where the optional AI judge is skipped.
            ledger = getattr(world_model, "continuity_ledger", None)
            if ledger is not None:
                from src.game.state import PlayerState

                state = PlayerState.from_dict(player_state_dict)
                authoritative = ledger.validate_story(
                    story_text,
                    date_info=state.get_game_date_info(),
                    week=state.week,
                    round_number=state.current_round,
                )
                if not authoritative.passed:
                    ledger.record_validation_conflicts(
                        authoritative.issues,
                        week=state.week,
                        round_number=state.current_round,
                        story_text=story_text,
                    )
                    source_state = getattr(world_model, "continuity_source_state", None)
                    if source_state is not None:
                        ledger.persist(source_state)
                    logger.warning(
                        "Authoritative continuity ledger rejected candidate: codes=%s week=%s round=%s",
                        [issue.code for issue in authoritative.issues],
                        state.week,
                        state.current_round,
                    )
                    issues = [
                        ConsistencyIssue(
                            dimension=issue.category,
                            severity="CRITICAL",
                            description=issue.message,
                            fix_suggestion=(
                                f"保持 {issue.subject} 的权威事实：{issue.expected}；"
                                f"删除或明确过渡冲突内容：{issue.observed}"
                            ),
                        )
                        for issue in authoritative.issues
                    ]
                    return ValidationResult(
                        passed=False,
                        issues=issues,
                        fix_instructions=authoritative.fix_instructions,
                    )

            if not run_ai_validation:
                return ValidationResult(passed=True)

            # Build the validation prompt
            from config.prompts import get_consistency_validation_prompt

            constraints_text = world_model.build_constraints_text(language)

            # ★ 获取已建立行为画像的角色名单
            profiled_characters = []
            if hasattr(world_model, "get_established_profile_names"):
                profiled_characters = world_model.get_established_profile_names()

            # ★ 将已建立画像的角色名单传给 prompt
            prompt = get_consistency_validation_prompt(
                story_text=story_text,
                constraints_text=constraints_text,
                character_settings=character_settings,
                language=language,
                profiled_characters=profiled_characters,
            )

            system_prompt = get_system_prompt("consistency_validator", language)

            response = self.client.call(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=4096,
            )

            # ★ 解析 AI 的验证结果（已移除硬性判断逻辑）
            return self._parse_validation_response(response, language)

        except Exception as e:
            logger.error(f"Consistency validation failed: {e}")
            # On error, pass through (don't block story generation)
            return ValidationResult(passed=True)

    def _parse_validation_response(self, response: str, language: str) -> ValidationResult:
        """
        Parse the AI validation response into a ValidationResult.
        ★ 已移除所有硬性判断逻辑，完全依赖 AI 的判断结果。

        Args:
            response: Raw AI response text
            language: Language code

        Returns:
            Parsed ValidationResult
        """
        try:
            data = extract_json(response)
            if not data:
                logger.warning("Could not parse validation response as JSON, treating as pass")
                return ValidationResult(passed=True)

            issues = []
            raw_issues = data.get("issues", [])

            for raw in raw_issues:
                dimension = raw.get("dimension", "unknown")
                # ★ 直接使用 AI 返回的 severity，不做硬性升级
                severity = raw.get("severity", "WARNING").upper()
                if severity not in ("CRITICAL", "WARNING"):
                    severity = "WARNING"

                description = raw.get("description", "")
                fix_suggestion = raw.get("fix_suggestion", "")
                reasoning = raw.get("reasoning", "")  # ★ AI 的判断理由

                # ★ 将判断理由附加到 fix_suggestion
                if reasoning:
                    fix_suggestion = (
                        f"{fix_suggestion}（判断理由：{reasoning}）"
                        if language == "zh"
                        else f"{fix_suggestion} (Reasoning: {reasoning})"
                    )

                if description:
                    issues.append(
                        ConsistencyIssue(
                            dimension=dimension,
                            severity=severity,
                            description=description,
                            fix_suggestion=fix_suggestion,
                        )
                    )

            # ★ 使用 AI 返回的 should_retry 字段来判断是否通过
            should_retry = data.get("should_retry", False)
            retry_reason = data.get("retry_reason", "")

            # ★ 如果 AI 没有返回 should_retry，回退到传统逻辑：有 CRITICAL 就不通过
            if "should_retry" not in data:
                has_critical = any(i.severity == "CRITICAL" for i in issues)
                should_retry = has_critical
                if should_retry:
                    retry_reason = "存在严重问题" if language == "zh" else "Critical issues found"

            passed = not should_retry

            # Build fix instructions for retry
            fix_instructions = ""
            if not passed:
                # ★ 按维度分组问题，提供更有针对性的修正指导
                critical_by_dimension: dict[str, Any] = {}
                for issue in issues:
                    if issue.severity == "CRITICAL":
                        dim = issue.dimension
                        if dim not in critical_by_dimension:
                            critical_by_dimension[dim] = []
                        critical_by_dimension[dim].append(issue)

                fix_parts = []

                # ★ 地理位置问题 - 特殊强调
                if "geographic" in critical_by_dimension:
                    if language == "zh":
                        fix_parts.append("\n⛔【地理位置错误 - 最严重的问题】")
                        for issue in critical_by_dimension["geographic"]:
                            fix_parts.append(f"  ❗ {issue.description}")
                            fix_parts.append(f"  → 修正方案：{issue.fix_suggestion}")
                        fix_parts.append(
                            "  提示：人物必须在其当前位置出现，如需移动必须先交代。可使用通讯方式（电话/信件/法术通讯）代替面对面交流。"
                        )
                    else:
                        fix_parts.append("\n⛔[GEOGRAPHIC ERRORS - MOST CRITICAL]")
                        for issue in critical_by_dimension["geographic"]:
                            fix_parts.append(f"  ❗ {issue.description}")
                            fix_parts.append(f"  → Fix: {issue.fix_suggestion}")
                        fix_parts.append(
                            "  Note: Characters MUST appear at their current location. For travel, narrate it first. Use communication (phone/letters/magic) instead of face-to-face."
                        )

                # ★ 其他 CRITICAL 问题
                for dim, issue_list in critical_by_dimension.items():
                    if dim == "geographic":
                        continue  # 已处理
                    dim_label = (
                        {
                            "career": "职业/身份",
                            "personality": "性格",
                            "temporal": "时间",
                            "commitment": "承诺",
                            "causal": "因果",
                            "fabrication": "编造事实",
                        }.get(dim, dim)
                        if language == "zh"
                        else dim
                    )

                    if language == "zh":
                        fix_parts.append(f"\n⚠️【{dim_label}问题】")
                    else:
                        fix_parts.append(f"\n⚠️[{dim_label.upper()} ISSUES]")

                    for issue in issue_list:
                        if language == "zh":
                            fix_parts.append(f"  - {issue.description}")
                            fix_parts.append(f"  → 修正方案：{issue.fix_suggestion}")
                        else:
                            fix_parts.append(f"  - {issue.description}")
                            fix_parts.append(f"  → Fix: {issue.fix_suggestion}")

                if language == "zh":
                    fix_instructions = (
                        "\n\n"
                        + "=" * 50
                        + "\n【一致性修正要求 - 必须严格遵守】\n"
                        + "=" * 50
                        + "\n上一次生成的故事存在以下逻辑矛盾，请在本次生成中修正："
                    )
                    fix_instructions += "\n".join(fix_parts)
                    if retry_reason:
                        fix_instructions += f"\n\n💡 AI判断理由：{retry_reason}"
                    fix_instructions += (
                        "\n" + "=" * 50 + "\n请重新生成故事，确保严格遵守以上修正要求。"
                    )
                else:
                    fix_instructions = (
                        "\n\n"
                        + "=" * 50
                        + "\n[CONSISTENCY FIX REQUIREMENTS - MUST STRICTLY FOLLOW]\n"
                        + "=" * 50
                        + "\nThe previous story had these logical contradictions. Fix them in this generation:"
                    )
                    fix_instructions += "\n".join(fix_parts)
                    if retry_reason:
                        fix_instructions += f"\n\n💡 AI reasoning: {retry_reason}"
                    fix_instructions += (
                        "\n"
                        + "=" * 50
                        + "\nPlease regenerate the story, strictly following the above fix requirements."
                    )

                # Also add warnings as reference
                warning_parts = []
                for issue in issues:
                    if issue.severity == "WARNING":
                        if language == "zh":
                            warning_parts.append(f"- 【建议改进】{issue.description}")
                        else:
                            warning_parts.append(f"- [Suggested improvement] {issue.description}")

                if warning_parts:
                    if language == "zh":
                        fix_instructions += "\n\n以下问题建议改进但非强制：\n" + "\n".join(
                            warning_parts
                        )
                    else:
                        fix_instructions += (
                            "\n\nThe following issues are suggested improvements but not mandatory:\n"
                            + "\n".join(warning_parts)
                        )

            result = ValidationResult(
                passed=passed, issues=issues, fix_instructions=fix_instructions
            )

            # Log results
            if issues:
                critical_count = len([i for i in issues if i.severity == "CRITICAL"])
                warning_count = len([i for i in issues if i.severity == "WARNING"])
                logger.info(
                    f"一致性校验结果: {'通过' if passed else '不通过(AI判断)'} "
                    f"(CRITICAL: {critical_count}, WARNING: {warning_count}, should_retry: {should_retry})"
                )
                if retry_reason:
                    logger.info(f"  AI判断理由: {retry_reason}")
                for issue in issues:
                    # ★ 输出完整的问题描述，不再截断
                    logger.info(f"  [{issue.severity}][{issue.dimension}] {issue.description}")
            else:
                logger.info("一致性校验结果: 通过（无问题）")

            return result

        except Exception as e:
            logger.error(f"Failed to parse validation response: {e}")
            return ValidationResult(passed=True)

    def validate_with_history(
        self,
        story_text: str,
        story_history: List[Dict[str, Any]],
        dynamic_facts: List[Any],
        character_settings: Dict[str, Any],
        language: str,
    ) -> ValidationResult:
        """
        ★ 增强验证：结合数据库历史故事进行交叉验证。

        这个方法用于检测故事中提到的过往事件是否在历史记录中有据可查，
        以及检查关键事实是否在故事压缩时被遗漏。

        Args:
            story_text: 待验证的故事文本
            story_history: 数据库中的历史故事列表
            dynamic_facts: 已提取的动态事实列表
            character_settings: 角色设定
            language: 语言代码

        Returns:
            ValidationResult 包含验证结果
        """
        if not story_text or not story_history:
            return ValidationResult(passed=True)

        try:
            # 构建历史故事摘要
            history_summary = self._build_history_summary(story_history, language)

            # 构建已提取事实摘要
            facts_summary = self._build_facts_summary(dynamic_facts, language)

            if language == "zh":
                prompt = f"""请检查以下故事与历史记录是否匹配。

【待检查的故事】
{story_text}

【历史故事摘要】
{history_summary}

【已提取的关键事实】
{facts_summary}

【检查重点】
1. **捐造检测**：故事中提到的过往事件、回忆是否在历史记录中能找到依据？
2. **事实遗漏**：历史故事中是否有重要事件未被提取为关键事实？（如重要承诺、关键决策、状态变化）
3. **因果连贯性**：历史中的重大事件在当前故事中是否有合理的后续影响？

【输出格式 - JSON】
{{
  "issues": [
    {{
      "dimension": "fabrication/fact_missing/causal",
      "severity": "CRITICAL/WARNING",
      "description": "问题描述",
      "evidence": "来自历史记录的证据（如果有）",
      "fix_suggestion": "修正建议"
    }}
  ]
}}

- 捐造的过往事件：CRITICAL
- 重要事实遗漏：WARNING
- 因果断裂：CRITICAL
- 只返回JSON"""
            else:
                prompt = f"""Check if the following story matches historical records.

[Story to Check]
{story_text}

[Historical Story Summary]
{history_summary}

[Extracted Key Facts]
{facts_summary}

[Check Focus]
1. **Fabrication Detection**: Are past events/memories mentioned in the story supported by historical records?
2. **Fact Missing**: Are there important events in historical stories not extracted as key facts? (important promises, key decisions, state changes)
3. **Causal Continuity**: Do major historical events have reasonable follow-up effects in current story?

[Output Format - JSON]
{{
  "issues": [
    {{
      "dimension": "fabrication/fact_missing/causal",
      "severity": "CRITICAL/WARNING",
      "description": "Issue description",
      "evidence": "Evidence from historical records (if any)",
      "fix_suggestion": "Fix suggestion"
    }}
  ]
}}

- Fabricated past events: CRITICAL
- Important facts missing: WARNING
- Broken causality: CRITICAL
- Return ONLY JSON"""

            system_prompt = get_system_prompt("consistency_validator", language)

            response = self.client.call(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=4096,
            )

            return self._parse_validation_response(response, language)

        except Exception as e:
            logger.error(f"History validation failed: {e}")
            return ValidationResult(passed=True)

    def _build_history_summary(self, story_history: List[Dict[str, Any]], language: str) -> str:
        """构建历史故事摘要。"""
        if not story_history:
            return "无历史记录" if language == "zh" else "No historical records"

        lines = []
        for item in story_history[-10:]:  # 只取最近10个故事
            week = item.get("week", "?")
            story = item.get("story", "")
            choice = item.get("choice", "")
            # 截取每个故事的关键部分
            story_preview = story[:300] + "..." if len(story) > 300 else story
            if language == "zh":
                lines.append(f"[第{week}周] {story_preview}\n玩家选择: {choice}")
            else:
                lines.append(f"[Week {week}] {story_preview}\nPlayer choice: {choice}")

        return "\n\n".join(lines)

    def _build_facts_summary(self, dynamic_facts: List[Any], language: str) -> str:
        """构建已提取事实摘要。"""
        if not dynamic_facts:
            return "无已提取事实" if language == "zh" else "No extracted facts"

        lines = []
        for f in dynamic_facts:
            if hasattr(f, "active") and not f.active:
                continue

            fact_type = getattr(f, "fact_type", "unknown")
            subject = getattr(f, "subject", "")
            description = getattr(f, "description", "")
            source_week = getattr(f, "source_week", "?")
            source_excerpt = getattr(f, "source_excerpt", "")

            if language == "zh":
                line = f"- [{fact_type}] {subject}: {description} (来源:第{source_week}周)"
                if source_excerpt:
                    line += f" 原文:「{source_excerpt[:50]}...」"
            else:
                line = f"- [{fact_type}] {subject}: {description} (source: week {source_week})"
                if source_excerpt:
                    line += f' excerpt: "{source_excerpt[:50]}..."'
            lines.append(line)

        return "\n".join(lines[:20])  # 最多20个事实
