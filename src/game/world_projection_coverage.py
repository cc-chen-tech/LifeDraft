"""Evidence-only detection for daily stories that require world projection."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

_SENTENCE_BOUNDARY = re.compile(r"[。！？!?；;]+")
_CLAUSE_BOUNDARY = re.compile(r"[，,]+")
_POS_PREFIX_FUNCTION_TAGS = frozenset({"c", "d", "e", "f", "o", "t", "u", "y"})
_POS_DETERMINER_TAGS = frozenset({"r"})
_STRUCTURAL_PARTICLE_TAGS = frozenset({"uj"})
_LOCATION_OBJECT_SUFFIXES = (
    "住所",
    "方向",
    "码头",
    "客栈",
    "花园",
    "果园",
    "山洞",
    "洞府",
    "宫殿",
    "高山",
    "山脉",
    "大海",
    "海域",
    "江岸",
    "江畔",
    "河岸",
    "河畔",
    "湖岸",
    "湖畔",
    "海岸",
    "街道",
    "道路",
    "小路",
    "柳巷",
    "小巷",
    "庭院",
    "院落",
    "卧室",
    "居室",
    "小屋",
    "房屋",
    "客房",
    "商店",
    "书店",
    "饭馆",
    "场馆",
    "车站",
    "广场",
    "港口",
    "海港",
    "岛屿",
    "村镇",
    "古镇",
    "城门",
    "城楼",
    "古塔",
    "石塔",
    "古寺",
    "寺庙",
    "石桥",
    "树林",
    "林地",
    "平原",
)

try:
    from jieba import Tokenizer as _JiebaTokenizer
    from jieba.posseg import POSTokenizer as _JiebaPOSTokenizer
except ImportError:  # The detector must fail closed when the local model is absent.
    _JiebaTokenizer = None
    _JiebaPOSTokenizer = None

_POS_LOCK = threading.RLock()
_pos_tokenizer: Any | None = None
_pos_tagger: Any | None = None
_LOCATION_TERMS = (
    "抵达",
    "到达",
    "前往",
    "来到",
    "离开",
    "搬到",
    "返回",
    "回到",
    "赶往",
    "进入",
    "现身",
    "身处",
    "位于",
    "落脚",
    "驻留",
    "当前位置改为",
    "当前位置变为",
    "所在地改为",
    "所在位置变为",
    "位置改为",
)
_FACT_TERMS = ("受伤", "康复", "失去", "获得", "成为", "不再", "状态变为")
_CAREER_TERMS = ("入职", "升职", "晋升", "调任", "辞职", "被解雇", "换了工作")
_HABIT_TERMS = ("养成了", "开始习惯", "不再习惯", "改掉了", "每天都会")
_COMMITMENT_CREATING_TERMS = ("承诺", "约定", "答应")
_COMMITMENT_LIFECYCLE_TERMS = ("兑现", "履行", "完成", "取消", "失约")
_COMMITMENT_EVIDENCE_TERMS = ("承诺", "约定", "任务", "诺言")
_CAUSAL_RESOLUTION_TERMS = ("解决", "化解", "后果", "结果", "因此", "导致")


@dataclass(frozen=True)
class WorldChangeSignals:
    """Matched evidence that extraction should have emitted a non-empty patch."""

    requires_nonempty_patch: bool
    categories: tuple[str, ...]
    matched_spans: tuple[str, ...]


class _RelativeSubjectAction(str, Enum):
    CARRY = "carry"
    REBIND = "rebind"
    RESET = "reset"


@dataclass(frozen=True)
class _RelativeSubjectBinding:
    action: _RelativeSubjectAction
    subject: str | None = None


def _tracked_character_names(tracked_state: Any) -> tuple[str, ...]:
    if not isinstance(tracked_state, Mapping):
        return ()
    locations = tracked_state.get("character_locations")
    if not isinstance(locations, Mapping):
        return ()
    return tuple(str(name) for name in locations if str(name).strip())


def _known_boundary_names(
    tracked_state: Any, tracked_names: Sequence[str]
) -> tuple[str, ...]:
    names = list(tracked_names)
    if not isinstance(tracked_state, Mapping):
        return tuple(names)
    for key in ("commitments", "active_commitments", "causal_chains"):
        records = tracked_state.get(key)
        if isinstance(records, Mapping):
            records = (
                (records,)
                if "parties" in records or "characters" in records
                else tuple(records.values())
            )
        if not isinstance(records, (list, tuple)):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            for field in ("parties", "characters"):
                people = record.get(field)
                if isinstance(people, str) and people.strip():
                    names.append(people.strip())
                elif isinstance(people, (list, tuple)):
                    names.extend(
                        person.strip()
                        for person in people
                        if isinstance(person, str) and person.strip()
                    )
    return tuple(dict.fromkeys(names))


def _known_location_names(tracked_state: Any) -> tuple[str, ...]:
    if not isinstance(tracked_state, Mapping):
        return ()
    names: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            names.append(value.strip())
        elif isinstance(value, Mapping):
            for field in ("name", "location", "label"):
                add(value.get(field))
        elif isinstance(value, (list, tuple)):
            for item in value:
                add(item)

    character_locations = tracked_state.get("character_locations")
    if isinstance(character_locations, Mapping):
        for value in character_locations.values():
            add(value)
    for key in ("known_locations", "locations", "landmarks"):
        values = tracked_state.get(key)
        if isinstance(values, Mapping):
            for name, value in values.items():
                add(name)
                add(value)
        else:
            add(values)
    return tuple(dict.fromkeys(names))


def _clause_contexts(
    story: str,
    options: Sequence[Any],
    tracked_names: Sequence[str],
    boundary_names: Sequence[str],
    known_location_names: Sequence[str],
) -> tuple[tuple[str, bool], ...]:
    source_texts = [str(story or "")]
    source_texts.extend(
        str(option.get("text") if isinstance(option, Mapping) else option or "")
        for option in options
    )
    contexts: list[tuple[str, bool]] = []
    for text in source_texts:
        for sentence in _SENTENCE_BOUNDARY.split(text):
            active_tracked_subject: str | None = None
            for clause in _CLAUSE_BOUNDARY.split(sentence):
                clause = clause.strip()
                if not clause:
                    continue
                candidate = clause.lstrip(" \t、，,；;：:—-")
                tracked_subject = _leading_tracked_name(candidate, tracked_names)
                if tracked_subject is not None:
                    active_tracked_subject = tracked_subject
                else:
                    relative_binding = _relative_subject_binding(
                        _pos_tokens(candidate),
                        tracked_names,
                        boundary_names,
                        known_location_names,
                    )
                    if relative_binding is not None:
                        if relative_binding.action is _RelativeSubjectAction.REBIND:
                            active_tracked_subject = relative_binding.subject
                        elif relative_binding.action is _RelativeSubjectAction.RESET:
                            active_tracked_subject = None
                    elif not (
                        active_tracked_subject
                        and _is_safe_subjectless_continuation(candidate)
                    ):
                        active_tracked_subject = None
                contexts.append((clause, active_tracked_subject is not None))
    return tuple(contexts)


def _has_tracked_entity(clause: str, tracked_names: Sequence[str]) -> bool:
    return any(name in clause for name in tracked_names)


def _get_pos_tagger() -> Any | None:
    """Build the package-bundled jieba tokenizer once, without network access."""
    global _pos_tagger, _pos_tokenizer
    with _POS_LOCK:
        if _pos_tagger is not None:
            return _pos_tagger
        if _JiebaTokenizer is None or _JiebaPOSTokenizer is None:
            return None
        try:
            tokenizer = _JiebaTokenizer()
            tagger = _JiebaPOSTokenizer(tokenizer=tokenizer)
        except Exception:
            return None
        _pos_tokenizer = tokenizer
        _pos_tagger = tagger
        return _pos_tagger


def _pos_tokens(candidate: str) -> tuple[tuple[str, str], ...]:
    """Return local POS tokens while serializing non-reentrant jieba access."""
    with _POS_LOCK:
        tagger = _get_pos_tagger()
        if tagger is None:
            return ()
        try:
            return tuple(
                (str(token.word), str(token.flag)) for token in tagger.cut(candidate)
            )
        except Exception:
            return ()


def _content_tokens(
    tokens: Sequence[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    return tuple(
        (word, tag) for word, tag in tokens if tag not in _POS_PREFIX_FUNCTION_TAGS
    )


def _initial_subject_tokens(
    tokens: Sequence[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    start = 0
    while start < len(tokens) and (
        tokens[start][1] in _POS_PREFIX_FUNCTION_TAGS
        or tokens[start][1] in _POS_DETERMINER_TAGS
    ):
        start += 1
    return tuple(tokens[start:])


def _joined_known_name(
    tokens: Sequence[tuple[str, str]], tracked_names: Sequence[str]
) -> str | None:
    joined = ""
    for word, _ in tokens:
        joined += word
        exact_match = next((name for name in tracked_names if name == joined), None)
        if exact_match is not None:
            return exact_match
        if not any(name.startswith(joined) for name in tracked_names):
            return None
    return None


def _leading_tracked_name(candidate: str, tracked_names: Sequence[str]) -> str | None:
    """Bind an exact leading raw span or a determiner-prefixed token span."""
    direct_match = next(
        (name for name in tracked_names if candidate.startswith(name)), None
    )
    if direct_match is not None:
        return direct_match
    return _joined_known_name(
        _initial_subject_tokens(_pos_tokens(candidate)), tracked_names
    )


def _relative_subject_tokens(
    tokens: Sequence[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    for index, (word, tag) in enumerate(tokens):
        if word != "的" and tag not in _STRUCTURAL_PARTICLE_TAGS:
            continue
        return _initial_subject_tokens(tokens[index + 1 :])
    return ()


def _relative_noun_span(
    tokens: Sequence[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    for index, (_, tag) in enumerate(tokens):
        if tag.startswith("v"):
            return tuple(tokens[:index])
    return tuple(tokens)


def _is_proven_location_or_object(
    tokens: Sequence[tuple[str, str]], known_location_names: Sequence[str]
) -> bool:
    noun_span = _relative_noun_span(tokens)
    if not noun_span:
        return False
    span_name = "".join(word for word, _ in noun_span)
    return (
        any(tag == "ns" for _, tag in noun_span)
        or span_name in known_location_names
        or span_name.endswith(_LOCATION_OBJECT_SUFFIXES)
    )


def _relative_subject_binding(
    tokens: Sequence[tuple[str, str]],
    tracked_names: Sequence[str],
    boundary_names: Sequence[str],
    known_location_names: Sequence[str],
) -> _RelativeSubjectBinding | None:
    subject_tokens = _relative_subject_tokens(tokens)
    if not subject_tokens:
        return None
    tracked_subject = _joined_known_name(subject_tokens, tracked_names)
    if tracked_subject is not None:
        return _RelativeSubjectBinding(_RelativeSubjectAction.REBIND, tracked_subject)
    if _joined_known_name(subject_tokens, boundary_names) is not None:
        return _RelativeSubjectBinding(_RelativeSubjectAction.RESET)
    if _is_proven_location_or_object(subject_tokens, known_location_names):
        return _RelativeSubjectBinding(_RelativeSubjectAction.CARRY)
    return _RelativeSubjectBinding(_RelativeSubjectAction.RESET)


def _valid_prepositional_prefix(tokens: Sequence[tuple[str, str]]) -> bool:
    content = _content_tokens(tokens)
    if not content:
        return True
    return content[0][1] == "p"


def _is_safe_subjectless_continuation(candidate: str) -> bool:
    """Permit only complete-token function prefixes before an action/location."""
    tokens = _pos_tokens(candidate)
    if not tokens:
        return False
    location_index = next(
        (index for index, (word, _) in enumerate(tokens) if word in _LOCATION_TERMS),
        None,
    )
    if location_index is not None:
        return _valid_prepositional_prefix(tokens[:location_index])
    content = _content_tokens(tokens)
    if not content:
        return False
    _, leading_tag = content[0]
    if leading_tag == "p":
        return True
    return leading_tag.startswith("v") and len(content) >= 2 and content[1][1] == "p"


def _known_record_terms(
    tracked_state: Any,
    keys: Sequence[str],
    content_fields: Sequence[str],
) -> tuple[str, ...]:
    if not isinstance(tracked_state, Mapping):
        return ()
    terms: list[str] = []

    def add_value(value: Any) -> None:
        if isinstance(value, str) and len(value.strip()) >= 2:
            terms.append(value.strip())
        elif isinstance(value, (list, tuple)):
            for item in value:
                add_value(item)

    for key in keys:
        records = tracked_state.get(key)
        if isinstance(records, Mapping):
            records = (
                (records,)
                if any(field in records for field in content_fields)
                else tuple(records.values())
            )
        if not isinstance(records, (list, tuple)):
            continue
        for record in records:
            if isinstance(record, Mapping):
                for field in content_fields:
                    add_value(record.get(field))
            else:
                add_value(record)
    return tuple(dict.fromkeys(terms))


def _matching_terms(clause: str, terms: Sequence[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if term in clause)


def detect_world_change_signals(
    story: str,
    options: Sequence[Any],
    tracked_state: Any = None,
) -> WorldChangeSignals:
    """Return correlated evidence only; this detector never constructs a patch."""
    tracked_names = _tracked_character_names(tracked_state)
    boundary_names = _known_boundary_names(tracked_state, tracked_names)
    known_location_names = _known_location_names(tracked_state)
    known_commitment_terms = _known_record_terms(
        tracked_state,
        ("commitments", "active_commitments"),
        ("description", "commitment", "task", "content", "details", "terms"),
    )
    known_causal_terms = _known_record_terms(
        tracked_state,
        ("causal_chains",),
        (
            "cause",
            "expected_consequence",
            "consequence",
            "description",
            "resolution",
            "details",
        ),
    )
    categories: list[str] = []
    matches: list[str] = []

    def record(category: str, found: Sequence[str]) -> None:
        if not found:
            return
        if category not in categories:
            categories.append(category)
        for term in found:
            if term not in matches:
                matches.append(term)

    for clause, has_location_subject in _clause_contexts(
        story,
        options,
        tracked_names,
        boundary_names,
        known_location_names,
    ):
        has_tracked_entity = _has_tracked_entity(clause, tracked_names)
        if has_location_subject:
            record("location_updates", _matching_terms(clause, _LOCATION_TERMS))
        if has_tracked_entity:
            record("fact_updates", _matching_terms(clause, _FACT_TERMS))
            record("career_updates", _matching_terms(clause, _CAREER_TERMS))
            record("habit_updates", _matching_terms(clause, _HABIT_TERMS))

        commitment_terms = _matching_terms(
            clause, _COMMITMENT_CREATING_TERMS + _COMMITMENT_LIFECYCLE_TERMS
        )
        has_commitment_evidence = bool(
            _matching_terms(clause, _COMMITMENT_EVIDENCE_TERMS)
            or _matching_terms(clause, known_commitment_terms)
        )
        if commitment_terms and (
            any(term in _COMMITMENT_CREATING_TERMS for term in commitment_terms)
            or has_commitment_evidence
        ):
            record("commitment_updates", commitment_terms)

        causal_matches = _matching_terms(clause, _CAUSAL_RESOLUTION_TERMS)
        if causal_matches and _matching_terms(clause, known_causal_terms):
            record("causal_updates", causal_matches)

    return WorldChangeSignals(
        requires_nonempty_patch=bool(categories),
        categories=tuple(categories),
        matched_spans=tuple(matches),
    )
