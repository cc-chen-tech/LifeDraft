"""Authoritative, source-linked narrative continuity ledger.

Narrative prose is display output. This ledger is the durable authority for
identity, chronology, committed events, health, and relationship state.
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.game.relationship_authority import extract_required_key_people

LEDGER_VERSION = 1
MAX_TIMELINE_ENTRIES = 600
MAX_CONFLICTS = 100

_DECEASED_WORDS = ("已经去世", "已去世", "已故", "去世", "死亡", "身亡", "病逝", "亡故")
_MEMORY_WORDS = (
    "回忆",
    "想起",
    "梦中",
    "梦里",
    "梦境",
    "幻觉",
    "曾经",
    "往事",
    "照片",
    "遗像",
)
_ACTIVE_VERBS = (
    "走",
    "跑",
    "来到",
    "进入",
    "拍",
    "说",
    "问",
    "答",
    "笑",
    "拿",
    "递",
    "决定",
    "参加",
    "主持",
    "工作",
)
_TRANSITION_WORDS = (
    "转任",
    "转行",
    "离职",
    "辞职",
    "退休",
    "晋升",
    "被任命",
    "出任",
    "竞聘",
    "改行",
    "成为",
    "卸任",
)
_ROLLBACK_WORDS = (
    "尚未",
    "还没有",
    "仍未",
    "没有办理",
    "未办理",
    "未完成",
    "重新提交",
    "再去提交",
    "准备办理",
    "计划办理",
)
_ROLE_TITLES = (
    "副校长",
    "校长",
    "老师",
    "教师",
    "教授",
    "医生",
    "律师",
    "产品经理",
    "工程师",
    "创业者",
    "导演",
    "摄影师",
    "剪辑师",
    "记者",
    "护士",
    "会计",
    "警察",
    "军人",
    "导师",
    "社区协调员",
    "同事",
    "父亲",
    "母亲",
)
_CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛雷贺倪汤滕殷毕郝邬安常乐于傅皮卞齐康伍余元顾孟平黄和穆萧尹姚邵汪祁毛禹狄米贝明臧计伏成戴宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄江童颜郭梅盛林钟徐邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫房裘缪干解应宗丁宣邓郁单杭洪包左石崔吉龚程嵇邢裴陆荣翁荀羊甄曲封芮储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶黎乔苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎连茹习艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权盖益桓公"
)


@dataclass(frozen=True)
class ContinuityIssue:
    code: str
    category: str
    subject: str
    expected: str
    observed: str
    message: str


@dataclass
class ContinuityValidationResult:
    passed: bool
    issues: List[ContinuityIssue] = field(default_factory=list)

    @property
    def fix_instructions(self) -> str:
        if not self.issues:
            return ""
        lines = ["\n\n【权威事实账本冲突，必须修正后重新生成】"]
        for issue in self.issues:
            lines.append(f"- {issue.subject}：{issue.message}")
        lines.append("不得用新叙事覆盖账本；合法变化必须在故事中明确交代后再提交。")
        return "\n".join(lines)


class ContinuityLedger:
    """Versioned continuity authority stored inside ``PlayerState``."""

    def __init__(self, data: Optional[Mapping[str, Any]] = None):
        raw = copy.deepcopy(dict(data or {}))
        self.version = int(raw.get("version") or LEDGER_VERSION)
        self.immutable_identities: Dict[str, Dict[str, Any]] = dict(
            raw.get("immutable_identities") or {}
        )
        self.timeline: List[Dict[str, Any]] = list(raw.get("timeline") or [])
        self.completed_events: Dict[str, Dict[str, Any]] = dict(
            raw.get("completed_events") or {}
        )
        mutable = dict(raw.get("mutable_states") or {})
        self.mutable_states: Dict[str, Dict[str, Dict[str, Any]]] = {
            "health": dict(mutable.get("health") or {}),
            "relationships": dict(mutable.get("relationships") or {}),
            "facts": dict(mutable.get("facts") or {}),
        }
        self.corrections: List[Dict[str, Any]] = list(raw.get("corrections") or [])
        self.conflicts: List[Dict[str, Any]] = list(raw.get("conflicts") or [])

    @classmethod
    def from_player_state(cls, player_state: Any) -> "ContinuityLedger":
        stored = _value(player_state, "continuity_ledger", {})
        ledger = cls(stored if isinstance(stored, Mapping) else {})
        ledger.seed_authoritative_identities(player_state)
        return ledger

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ContinuityLedger":
        return cls.from_player_state(state)

    def seed_authoritative_identities(self, player_state: Any) -> None:
        settings = _value(player_state, "character_settings", {}) or {}
        if not isinstance(settings, Mapping):
            settings = {}

        player_name = _text(_value(player_state, "player_name", ""))
        if player_name:
            occupation = settings.get("occupation") or settings.get("background") or {}
            role = ""
            employer = ""
            if isinstance(occupation, Mapping):
                role = _text(occupation.get("occupation") or occupation.get("role"))
                employer = _text(occupation.get("employer"))
            self._seed_identity(
                player_name,
                roles=[role] if role else [],
                relationships=["主角"],
                description=employer,
                age_baseline=_int_or_none(_value(player_state, "age", None)),
                life_status="alive",
                source_path="player_state",
            )

        for person in extract_required_key_people(settings):
            self._seed_identity(
                person["name"],
                roles=[person.get("role", "")],
                relationships=[person.get("relationship", "")],
                description="；".join(
                    part
                    for part in [
                        person.get("relationship_desc", ""),
                        person.get("description", ""),
                    ]
                    if part
                ),
                life_status=_life_status(person),
                source_path="character_settings.relationships.key_people",
            )

        family = settings.get("family") or {}
        family_members: Iterable[Any] = []
        if isinstance(family, Mapping):
            family_members = family.get("family_members") or family.get("members") or []
        if isinstance(family_members, list):
            for member in family_members:
                if not isinstance(member, Mapping):
                    continue
                name = _text(member.get("name"))
                if not name:
                    continue
                role = _text(member.get("role") or member.get("relation"))
                relationship = _text(member.get("relationship") or role)
                description = _text(
                    member.get("description") or member.get("relationship_desc")
                )
                self._seed_identity(
                    name,
                    roles=[role],
                    relationships=[relationship],
                    description=description,
                    life_status=_life_status(member),
                    source_path="character_settings.family.family_members",
                )

    def _seed_identity(
        self,
        name: str,
        *,
        roles: Iterable[str],
        relationships: Iterable[str],
        description: str,
        life_status: str,
        source_path: str,
        age_baseline: Optional[int] = None,
    ) -> None:
        clean_name = _text(name)
        if not clean_name:
            return
        role_values = _unique_text(roles)
        relationship_values = _unique_text(relationships)
        existing = self.immutable_identities.get(clean_name)
        if existing:
            existing["roles"] = _unique_text(
                list(existing.get("roles") or []) + role_values
            )
            existing["relationships"] = _unique_text(
                list(existing.get("relationships") or []) + relationship_values
            )
            if existing.get("life_status") != "deceased" and life_status == "deceased":
                existing["life_status"] = "deceased"
            return
        self.immutable_identities[clean_name] = {
            "canonical_name": clean_name,
            "aliases": [],
            "roles": role_values,
            "relationships": relationship_values,
            "description": description,
            "life_status": life_status,
            "age_baseline": age_baseline,
            "source": {"kind": "character_settings", "path": source_path},
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": LEDGER_VERSION,
            "immutable_identities": copy.deepcopy(self.immutable_identities),
            "timeline": copy.deepcopy(self.timeline[-MAX_TIMELINE_ENTRIES:]),
            "completed_events": copy.deepcopy(self.completed_events),
            "mutable_states": copy.deepcopy(self.mutable_states),
            "corrections": copy.deepcopy(self.corrections),
            "conflicts": copy.deepcopy(self.conflicts[-MAX_CONFLICTS:]),
        }

    def persist(self, player_state: Any) -> None:
        data = self.to_dict()
        if isinstance(player_state, dict):
            player_state["continuity_ledger"] = data
        else:
            player_state.continuity_ledger = data

    def build_constraints_text(self, language: str = "zh") -> str:
        if language != "zh":
            return self._build_constraints_en()
        lines = ["\n【权威连续性事实账本 — 叙事不得覆盖，只能通过明确事件变更】"]
        if self.immutable_identities:
            lines.append("不可变身份：")
            for name, identity in self.immutable_identities.items():
                facts = _unique_text(
                    list(identity.get("roles") or [])
                    + list(identity.get("relationships") or [])
                    + (["已去世"] if identity.get("life_status") == "deceased" else [])
                )
                if identity.get("age_baseline") is not None:
                    facts.append(f"初始年龄{identity['age_baseline']}岁")
                lines.append(f"- {name}：{'；'.join(facts) or 'canonical identity'}")
        if self.timeline:
            lines.append("最近已提交时间线：")
            for entry in self.timeline[-8:]:
                lines.append(
                    f"- [{entry.get('event_id')}] {_date_label(entry.get('date_info') or {})}："
                    f"{entry.get('summary') or entry.get('choice') or '已提交事件'}"
                )
        if self.completed_events:
            lines.append("已完成事件（不得回滚成未办理）：")
            for record in list(self.completed_events.values())[-12:]:
                lines.append(
                    f"- {record.get('subject')}：{record.get('fact')}"
                    f"（来源 {record.get('source_event_id')}）"
                )
        for category, title in (("health", "当前健康"), ("relationships", "当前关系")):
            records = self.mutable_states.get(category) or {}
            if records:
                lines.append(f"{title}（变化必须有来源事件）：")
                for subject, record in records.items():
                    lines.append(
                        f"- {subject}：{record.get('fact')}（来源 {record.get('source_event_id')}）"
                    )
        current_facts = self.mutable_states.get("facts") or {}
        if current_facts:
            lines.append("当前可变事实（变化必须有来源事件）：")
            for record in list(current_facts.values())[-20:]:
                lines.append(
                    f"- [{record.get('category')}] {record.get('subject')}：{record.get('fact')}"
                    f"（来源 {record.get('source_event_id')}）"
                )
        return "\n".join(lines)

    def _build_constraints_en(self) -> str:
        lines = [
            "\n[Authoritative Continuity Ledger - narrative cannot overwrite these facts]"
        ]
        for name, identity in self.immutable_identities.items():
            facts = list(identity.get("roles") or []) + list(
                identity.get("relationships") or []
            )
            if identity.get("life_status") == "deceased":
                facts.append("deceased")
            lines.append(f"- {name}: {'; '.join(facts) or 'canonical identity'}")
        return "\n".join(lines)

    def validate_story(
        self,
        story_text: str,
        *,
        date_info: Mapping[str, Any],
        week: int,
        round_number: int,
    ) -> ContinuityValidationResult:
        if not story_text:
            return ContinuityValidationResult(passed=True)
        issues: List[ContinuityIssue] = []
        issues.extend(self._validate_dates(story_text, date_info))
        issues.extend(self._validate_ages(story_text, date_info))
        issues.extend(self._validate_identities(story_text))
        issues.extend(self._validate_canonical_role_ownership(story_text))
        issues.extend(self._validate_completed_events(story_text))
        return ContinuityValidationResult(passed=not issues, issues=issues)

    def _validate_dates(
        self, story_text: str, date_info: Mapping[str, Any]
    ) -> List[ContinuityIssue]:
        expected_year = _int_or_none(date_info.get("year"))
        expected_month = _int_or_none(date_info.get("month"))
        claims: List[tuple[Optional[int], int, str]] = []
        for match in re.finditer(r"(?:(\d{4})年)?(\d{1,2})月", story_text):
            context = story_text[
                max(0, match.start() - 24) : min(len(story_text), match.end() + 12)
            ]
            if any(word in context for word in _MEMORY_WORDS):
                continue
            claims.append(
                (_int_or_none(match.group(1)), int(match.group(2)), match.group(0))
            )
        for match in re.finditer(
            r"([一二两三四五六七八九十]{1,3})月(?:初|中|底|末)?", story_text
        ):
            context = story_text[
                max(0, match.start() - 24) : min(len(story_text), match.end() + 12)
            ]
            if any(word in context for word in _MEMORY_WORDS):
                continue
            month = _chinese_number(match.group(1))
            if month is not None:
                claims.append((None, month, match.group(0)))
        issues = []
        for year, month, observed in claims:
            if (
                expected_year is not None and year is not None and year != expected_year
            ) or (expected_month is not None and month != expected_month):
                expected = f"{expected_year or ''}年{expected_month or '?'}月"
                issues.append(
                    ContinuityIssue(
                        code="date_mismatch",
                        category="timeline",
                        subject="当前日期",
                        expected=expected,
                        observed=observed,
                        message=f"账本当前日期为{expected}，正文却写成{observed}",
                    )
                )
        return issues

    def _validate_ages(
        self, story_text: str, date_info: Mapping[str, Any]
    ) -> List[ContinuityIssue]:
        expected_age = _int_or_none(date_info.get("age"))
        if expected_age is None:
            return []
        issues = []
        for name in self.immutable_identities:
            patterns = [
                rf"([0-9]{{1,3}}|[一二两三四五六七八九十]{{1,4}})岁的{re.escape(name)}",
                rf"{re.escape(name)}.{{0,6}}?([0-9]{{1,3}}|[一二两三四五六七八九十]{{1,4}})岁",
            ]
            for pattern in patterns:
                match = re.search(pattern, story_text)
                if not match:
                    continue
                context = story_text[
                    max(0, match.start() - 24) : min(len(story_text), match.end() + 12)
                ]
                if any(word in context for word in _MEMORY_WORDS):
                    break
                observed_age = (
                    int(match.group(1))
                    if match.group(1).isdigit()
                    else _chinese_number(match.group(1))
                )
                if observed_age is not None and observed_age != expected_age:
                    issues.append(
                        ContinuityIssue(
                            code="age_mismatch",
                            category="identity",
                            subject=name,
                            expected=str(expected_age),
                            observed=str(observed_age),
                            message=f"权威年龄为{expected_age}岁，正文写成{observed_age}岁",
                        )
                    )
                break
        return issues

    def _validate_identities(self, story_text: str) -> List[ContinuityIssue]:
        issues: List[ContinuityIssue] = []
        for name, identity in self.immutable_identities.items():
            if name not in story_text:
                continue
            if identity.get(
                "life_status"
            ) == "deceased" and self._has_active_deceased_action(story_text, name):
                issues.append(
                    ContinuityIssue(
                        code="deceased_active",
                        category="identity",
                        subject=name,
                        expected="已去世，只能在回忆/梦境/资料中出现",
                        observed="当前场景主动行为",
                        message="已去世人物在非回忆场景中执行主动行为",
                    )
                )

            current_career = self.mutable_states.get("facts", {}).get(
                f"career:{name}", {}
            )
            roles = _unique_text(
                [current_career.get("fact")]
                if current_career.get("fact")
                else identity.get("roles") or []
            )
            if not roles:
                continue
            segment = _context_window(story_text, name, 28)
            observed_roles = _extract_role_claims(segment, name)
            conflicting = [
                role
                for role in observed_roles
                if not any(role in expected or expected in role for expected in roles)
                and role not in identity.get("relationships", [])
            ]
            if conflicting and not any(word in segment for word in _TRANSITION_WORDS):
                issues.append(
                    ContinuityIssue(
                        code="identity_role_conflict",
                        category="identity",
                        subject=name,
                        expected="、".join(roles),
                        observed="、".join(conflicting),
                        message=(
                            f"账本身份为{'、'.join(roles)}，正文无过渡地改成"
                            f"{'、'.join(conflicting)}"
                        ),
                    )
                )
        return issues

    def _has_active_deceased_action(self, story_text: str, name: str) -> bool:
        for match in re.finditer(re.escape(name), story_text):
            start = max(0, match.start() - 28)
            end = min(len(story_text), match.end() + 28)
            segment = story_text[start:end]
            if any(word in segment for word in _MEMORY_WORDS):
                continue
            after = story_text[match.end() : min(len(story_text), match.end() + 18)]
            if any(verb in after for verb in _ACTIVE_VERBS):
                return True
        return False

    def _validate_canonical_role_ownership(
        self, story_text: str
    ) -> List[ContinuityIssue]:
        """Reject transferring a canonical person's role to a replacement name."""
        issues: List[ContinuityIssue] = []
        action_boundary = r"(?=说道|说|走|拿|递|和|与|确认|负责|，|。|、|；|\s|$)"
        for canonical_name, identity in self.immutable_identities.items():
            for role in _unique_text(identity.get("roles") or []):
                if len(role) < 2 or role not in story_text:
                    continue
                pattern = (
                    re.escape(role)
                    + r"[：:，,\s]*(?:名叫|叫)?"
                    + r"([\u4e00-\u9fff]{2,4}?)"
                    + action_boundary
                )
                for match in re.finditer(pattern, story_text):
                    observed_name = match.group(1)
                    if (
                        observed_name == canonical_name
                        or observed_name[0] not in _COMMON_SURNAMES
                    ):
                        continue
                    issues.append(
                        ContinuityIssue(
                            code="canonical_name_conflict",
                            category="identity",
                            subject=canonical_name,
                            expected=f"{role}{canonical_name}",
                            observed=observed_name,
                            message=(
                                f"账本规定{role}的 canonical name 是{canonical_name}，"
                                f"正文却把该身份转给{observed_name}"
                            ),
                        )
                    )
        return issues

    def _validate_completed_events(self, story_text: str) -> List[ContinuityIssue]:
        issues = []
        for record in self.completed_events.values():
            subject = _text(record.get("subject"))
            if not subject or subject not in story_text:
                continue
            segment = _context_window(story_text, subject, 40)
            rollback = next((word for word in _ROLLBACK_WORDS if word in segment), "")
            if rollback:
                issues.append(
                    ContinuityIssue(
                        code="completed_event_rollback",
                        category="timeline",
                        subject=subject,
                        expected=_text(record.get("fact")),
                        observed=rollback,
                        message=(
                            f"事件已在{record.get('source_event_id')}提交完成，正文却回滚为“{rollback}”"
                        ),
                    )
                )
        return issues

    def record_committed_event(
        self,
        *,
        event_id: str,
        week: int,
        round_number: int,
        date_info: Mapping[str, Any],
        summary: str,
        choice: str,
        story_text: str,
        fact_updates: Iterable[Mapping[str, Any]],
    ) -> bool:
        if any(entry.get("event_id") == event_id for entry in self.timeline):
            return False
        if self.timeline:
            previous = self.timeline[-1]
            if (week, round_number) < (
                int(previous.get("week", 0)),
                int(previous.get("round", 0)),
            ):
                self._append_conflict(
                    code="timeline_regression",
                    subject=event_id,
                    expected=f">= {previous.get('event_id')}",
                    observed=f"w{week}-r{round_number}",
                    source_event_id=event_id,
                    week=week,
                    round_number=round_number,
                    story_text=story_text,
                )
                return False
        self.timeline.append(
            {
                "sequence": len(self.timeline),
                "event_id": event_id,
                "week": week,
                "round": round_number,
                "date_info": dict(date_info),
                "summary": summary,
                "choice": choice,
                "story_hash": _story_hash(story_text),
                "status": "committed",
            }
        )
        self.timeline = self.timeline[-MAX_TIMELINE_ENTRIES:]
        self.commit_fact_updates(
            event_id=event_id,
            week=week,
            round_number=round_number,
            story_text=story_text,
            fact_updates=fact_updates,
        )
        return True

    def commit_fact_updates(
        self,
        *,
        event_id: str,
        week: int,
        round_number: int,
        story_text: str,
        fact_updates: Iterable[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        accepted: List[Dict[str, Any]] = []
        for update in fact_updates:
            action = _text(update.get("action") or "new")
            subject = _text(update.get("subject"))
            category = _text(update.get("category") or "fact").lower()
            fact = _text(update.get("fact") or update.get("description"))
            if not subject or not fact or action == "remove":
                continue
            if (
                category in {"identity", "immutable_identity", "role"}
                and subject in self.immutable_identities
            ):
                identity = self.immutable_identities[subject]
                canonical = "；".join(
                    _unique_text(
                        list(identity.get("roles") or [])
                        + list(identity.get("relationships") or [])
                    )
                )
                if fact not in canonical and canonical not in fact:
                    self._append_conflict(
                        code="immutable_identity_update",
                        subject=subject,
                        expected=canonical,
                        observed=fact,
                        source_event_id=event_id,
                        week=week,
                        round_number=round_number,
                        story_text=story_text,
                    )
                    continue

            record = {
                "subject": subject,
                "fact": fact,
                "category": category,
                "source_event_id": event_id,
                "effective_week": week,
                "effective_round": round_number,
                "source_story_hash": _story_hash(story_text),
            }
            if category in {"completed", "completed_event", "completion", "milestone"}:
                self.completed_events[subject] = record
            elif category in {"health", "physical_state", "medical"}:
                self.mutable_states["health"][subject] = record
            elif category in {
                "relationship",
                "relationships",
                "relationship_state",
                "social_dynamic",
            }:
                self.mutable_states["relationships"][subject] = record
            else:
                self.mutable_states["facts"][f"{category}:{subject}"] = record
            accepted.append(record)
        return accepted

    def _append_conflict(
        self,
        *,
        code: str,
        subject: str,
        expected: str,
        observed: str,
        source_event_id: str,
        week: int,
        round_number: int,
        story_text: str,
    ) -> None:
        self.conflicts.append(
            {
                "code": code,
                "subject": subject,
                "expected": expected,
                "observed": observed,
                "source_event_id": source_event_id,
                "week": week,
                "round": round_number,
                "source_story_hash": _story_hash(story_text),
            }
        )
        self.conflicts = self.conflicts[-MAX_CONFLICTS:]

    def record_validation_conflicts(
        self,
        issues: Iterable[ContinuityIssue],
        *,
        week: int,
        round_number: int,
        story_text: str,
    ) -> None:
        source_event_id = f"candidate-w{week}-r{round_number}"
        for issue in issues:
            self._append_conflict(
                code=issue.code,
                subject=issue.subject,
                expected=issue.expected,
                observed=issue.observed,
                source_event_id=source_event_id,
                week=week,
                round_number=round_number,
                story_text=story_text,
            )


def _value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _unique_text(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = _text(value)
        if text and text not in result:
            result.append(text)
    return result


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _life_status(person: Mapping[str, Any]) -> str:
    explicit = _text(person.get("life_status") or person.get("status")).lower()
    if explicit in {"deceased", "dead", "死亡", "去世", "已故"}:
        return "deceased"
    combined = "；".join(_text(value) for value in person.values())
    return "deceased" if any(word in combined for word in _DECEASED_WORDS) else "alive"


def _story_hash(story_text: str) -> str:
    return hashlib.sha256(story_text.encode("utf-8")).hexdigest()[:16]


def _date_label(date_info: Mapping[str, Any]) -> str:
    year = date_info.get("year", "")
    month = date_info.get("month", "")
    week = date_info.get("week_in_month", "")
    return f"{year}年{month}月第{week}周"


def _context_window(text: str, needle: str, radius: int) -> str:
    index = text.find(needle)
    if index < 0:
        return ""
    return text[max(0, index - radius) : min(len(text), index + len(needle) + radius)]


def _extract_role_claims(segment: str, name: str) -> List[str]:
    """Return role titles grammatically asserted about ``name`` in a short segment."""
    claims: List[str] = []
    escaped_name = re.escape(name)
    for title in _ROLE_TITLES:
        escaped_title = re.escape(title)
        patterns = (
            rf"{escaped_name}.{{0,2}}(?:是|作为|担任|出任|成了|成为|转任|身份是).{{0,14}}{escaped_title}",
            rf"{escaped_name}[，,:：].{{0,12}}{escaped_title}",
            rf"{escaped_title}{escaped_name}",
        )
        if any(re.search(pattern, segment) for pattern in patterns):
            claims.append(title)
    return claims


def _chinese_number(text: str) -> Optional[int]:
    if not text:
        return None
    if text == "十":
        return 10
    if "十" in text:
        left, right = text.split("十", 1)
        tens = _CHINESE_DIGITS.get(left, 1) if left else 1
        ones = _CHINESE_DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    if len(text) == 1:
        return _CHINESE_DIGITS.get(text)
    value = 0
    for char in text:
        digit = _CHINESE_DIGITS.get(char)
        if digit is None:
            return None
        value = value * 10 + digit
    return value
