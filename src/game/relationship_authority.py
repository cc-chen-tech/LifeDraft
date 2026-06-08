"""Authoritative handling for preset key people and relationships."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class CastCoverageResult:
    """Deterministic result for required-cast validation."""

    passed: bool
    present_names: List[str] = field(default_factory=list)
    missing_names: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


COMMON_CHINESE_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢"
    "邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉"
    "岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄林陆"
)


def extract_required_key_people(character_settings: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Return canonical key people from character settings."""
    relationships = character_settings.get("relationships")
    if not isinstance(relationships, Mapping):
        return []
    key_people = relationships.get("key_people")
    if not isinstance(key_people, list):
        return []

    people: List[Dict[str, str]] = []
    for item in key_people:
        if not isinstance(item, Mapping):
            continue
        name = _text(item.get("name"))
        if not name:
            continue
        people.append(
            {
                "name": name,
                "role": _text(item.get("role")),
                "relationship": _text(item.get("relationship")),
                "relationship_desc": _text(item.get("relationship_desc")),
                "description": _text(item.get("description")),
            }
        )
    return people


def build_required_cast_constraints(
    character_settings: Mapping[str, Any],
    language: str = "zh",
) -> str:
    """Build prompt constraints that make preset people authoritative."""
    people = extract_required_key_people(character_settings)
    if not people:
        return ""

    if language == "zh":
        lines = [
            "👥 【预设人物关系 — 必须使用 canonical name，不得改名或用新人物替换】",
        ]
        for person in people:
            facts = _person_facts(person)
            lines.append(f"  - {person['name']}：{facts}")
        lines.append("  ⚠️ 以上人物是玩家预设关系网；故事应优先围绕这些人物推进。")
        return "\n".join(lines)

    lines = [
        "[Preset Cast Relationships - use canonical names; do not rename or replace them]",
    ]
    for person in people:
        facts = _person_facts(person)
        lines.append(f"  - {person['name']}: {facts}")
    lines.append("  These people are the player's preset relationship network.")
    return "\n".join(lines)


def validate_required_cast_coverage(
    story_text: str,
    character_settings: Mapping[str, Any],
    language: str = "zh",
    minimum_required_mentions: int = 1,
) -> CastCoverageResult:
    """Validate that generated text uses enough preset key people."""
    people = extract_required_key_people(character_settings)
    if not people or minimum_required_mentions <= 0:
        return CastCoverageResult(passed=True)

    present = [person["name"] for person in people if person["name"] in story_text]
    missing = [person["name"] for person in people if person["name"] not in present]
    if len(present) >= minimum_required_mentions:
        return CastCoverageResult(passed=True, present_names=present, missing_names=missing)

    invented = _extract_likely_chinese_names(story_text, {person["name"] for person in people})
    issues: List[str] = []
    for person in people:
        if person["name"] in present:
            continue
        matching_substitutes = _substitutes_for_missing_person(story_text, person, invented)
        if matching_substitutes:
            issues.append(
                f"预设人物{person['name']}({ _person_facts(person) })缺失，"
                f"发现疑似替代人物{'、'.join(matching_substitutes)}。"
            )
    if not issues:
        issues.append(
            "故事未达到预设人物出场要求；请至少使用一个 canonical key_people 名字。"
        )

    return CastCoverageResult(
        passed=False,
        present_names=present,
        missing_names=missing,
        issues=issues,
    )


def canonicalize_key_person_candidate(
    candidate: Mapping[str, Any],
    character_settings: Mapping[str, Any],
) -> Dict[str, Any]:
    """Map an extracted substitute candidate back to a preset key person when facts match."""
    result = dict(candidate)
    candidate_name = _text(candidate.get("name"))
    if not candidate_name:
        return result

    people = extract_required_key_people(character_settings)
    if any(person["name"] == candidate_name for person in people):
        return result

    candidate_facts = _normal_tokens(
        " ".join(
            [
                _text(candidate.get("role")),
                _text(candidate.get("relationship")),
                _text(candidate.get("relationship_desc")),
                _text(candidate.get("description")),
            ]
        )
    )
    for person in people:
        person_facts = _normal_tokens(_person_facts(person))
        if candidate_facts and person_facts and candidate_facts.intersection(person_facts):
            result["name"] = person["name"]
            if not _text(result.get("role")) and person["role"]:
                result["role"] = person["role"]
            return result

    return result


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _person_facts(person: Mapping[str, str]) -> str:
    facts = [
        person.get("role", ""),
        person.get("relationship", ""),
        person.get("relationship_desc", ""),
        person.get("description", ""),
    ]
    return "；".join(fact for fact in facts if fact) or "关键人物"


def _normal_tokens(text: str) -> set[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    tokens = {token for token in re.split(r"[，。；、,;:\s]+", text.lower()) if token}
    important = [
        "闺蜜",
        "好友",
        "朋友",
        "大学好友",
        "导师",
        "产品导师",
        "同期",
        "同事",
        "产品经理",
        "数据分析",
    ]
    tokens.update(token for token in important if token in normalized)
    return tokens


def _extract_likely_chinese_names(text: str, allowed_names: set[str]) -> List[str]:
    surname_class = re.escape(COMMON_CHINESE_SURNAMES)
    pattern = re.compile(rf"([{surname_class}][\u4e00-\u9fff]{{1,2}})")
    names: List[str] = []
    for match in pattern.findall(text):
        candidate = match.strip("，。！？、；：“”‘’（）()《》")
        if not candidate or candidate in allowed_names:
            continue
        if any(candidate in allowed or allowed in candidate for allowed in allowed_names):
            continue
        if candidate not in names:
            names.append(candidate)
    return names


def _substitutes_for_missing_person(
    story_text: str,
    person: Mapping[str, str],
    invented_names: List[str],
) -> List[str]:
    facts = _normal_tokens(_person_facts(person))
    normalized_story = re.sub(r"\s+", "", story_text.lower())
    if not any(fact and fact in normalized_story for fact in facts):
        return []
    return invented_names
