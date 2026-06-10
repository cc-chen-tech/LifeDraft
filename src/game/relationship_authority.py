"""Authoritative handling for preset key people and relationships."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping


def extract_required_key_people(character_settings: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Return canonical preset key people from character settings."""
    relationships = character_settings.get("relationships")
    if isinstance(relationships, list):
        key_people = relationships
    elif isinstance(relationships, Mapping):
        key_people = relationships.get("key_people")
    else:
        key_people = []

    if not isinstance(key_people, list):
        return []

    people: List[Dict[str, str]] = []
    seen: set[str] = set()
    for item in key_people:
        if not isinstance(item, Mapping):
            continue

        name = _text(item.get("name"))
        if not name or name in seen:
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
        seen.add(name)

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
            "👥 【预设关键人物关系 — canonical name 必须严格使用，不得改名、不得替换】",
        ]
        for person in people:
            lines.append(f"  - {person['name']}：{_person_facts(person)}")
        lines.append(
            "  ⚠️ 以上人物是玩家预设关系网；如需导师、闺蜜、同期等关系，必须使用对应 canonical name。"
        )
        names = "、".join(person["name"] for person in people)
        lines.append(f"  [MUST] 本轮必须至少使用1位预设关键人物：{names}至少一位。")
        lines.append("  ⚠️ 不得把这些人物的身份、关系或剧情功能转移给新命名人物。")
        lines.append("  ✅ 非关键背景人物只能使用「路人」「陌生人」「同事」等通用称谓。")
        return "\n".join(lines)

    lines = [
        "[Preset Key People Relationships - canonical names MUST be used; do not rename or replace]",
    ]
    for person in people:
        lines.append(f"  - {person['name']}: {_person_facts(person)}")
    lines.append(
        "  These people are the player's preset relationship network; use the matching canonical name for mentor, friend, peer, or similar roles."
    )
    names = ", ".join(person["name"] for person in people)
    lines.append(f"  [MUST] Each round must use at least one preset key person: one of {names}.")
    lines.append("  Do not transfer these identities, relationships, or plot functions to new named people.")
    lines.append("  Generic background people may use labels such as passerby, stranger, or colleague.")
    return "\n".join(lines)


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
