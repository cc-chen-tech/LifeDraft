"""Read-only, evidence-grounded answers for the in-game story assistant.

The assistant is allowed to read structured character settings and committed
continuity-ledger records. Narrative prose is display output and is never used
as authority here.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from src.utils.financial_narrative import contains_precise_financial_fact

MAX_EVIDENCE_RECORDS = 160
MAX_ATTEMPTS = 2

_COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻"
    "柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛雷贺倪汤滕殷毕郝"
    "邬安常乐于傅皮卞齐康伍余元顾孟平黄和穆萧尹姚邵汪祁毛禹狄米贝明臧计伏成"
    "戴宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄江童颜郭梅盛林钟徐邱骆高"
    "夏蔡田樊胡凌霍虞万支柯管卢莫房裘缪干解应宗丁宣邓郁单杭洪包左石崔吉龚程"
    "陆荣翁荀羊甄曲封芮储靳井段富巫乌焦巴牧山谷车侯全班仰秋仲伊宫宁栾甘厉祖"
    "武符刘景詹束龙叶黎乔闻党翟谭劳姬申冉桑桂牛寿边燕浦尚农温庄柴瞿阎连茹艾"
    "向古易廖都耿满弘匡国文寇广东欧利越隆师巩聂晁融冷辛阚简饶曾沙关查游权盖"
)
_GENERIC_PERSON_TERMS = {
    "主角",
    "玩家",
    "朋友",
    "好友",
    "同事",
    "家人",
    "父母",
    "父亲",
    "母亲",
    "老师",
    "医生",
    "方案",
    "项目",
    "故事",
    "最近",
    "现在",
}
_ZH_QUERY_PATTERNS = (
    re.compile(
        r"([\u4e00-\u9fff]{2,4})(?:是谁|的职业|多大|住在哪里|去世了吗|结婚了吗)"
    ),
    re.compile(r"(?:我和|我与)([\u4e00-\u9fff]{2,4})(?:是什么|的)?关系"),
)
_EN_QUERY_PATTERN = re.compile(
    r"\b(?:who is|what happened to|do i know)\s+([A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)?)",
    re.IGNORECASE,
)
_CONCRETE_TOKEN = re.compile(
    r"\d+(?:\.\d+)?|[一二两三四五六七八九十百千万两]+(?=年|月|日|周|岁|元|万|%|％)"
)


def _value(source: Any, key: str, default: Any) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _safe_component(value: Any) -> str:
    return re.sub(r"[\[\]{}\n\r]", "", _clean(value))[:80]


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    kind: str
    subject: str
    fact: str
    source_event_id: Optional[str] = None
    effective_week: Optional[int] = None
    effective_round: Optional[int] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "kind": self.kind,
            "subject": self.subject,
            "fact": self.fact,
        }
        if self.source_event_id:
            result["source_event_id"] = self.source_event_id
        if self.effective_week is not None:
            result["effective_week"] = self.effective_week
        if self.effective_round is not None:
            result["effective_round"] = self.effective_round
        if self.metadata:
            result["metadata"] = dict(self.metadata)
        return result


@dataclass
class AssistantEvidence:
    records: Dict[str, EvidenceRecord] = field(default_factory=dict)
    known_people: List[str] = field(default_factory=list)

    @classmethod
    def from_player_state(cls, player_state: Any) -> "AssistantEvidence":
        evidence = cls()
        settings = _value(player_state, "character_settings", {})
        if isinstance(settings, Mapping):
            evidence._add_setting_scalars(settings)

        life_vision = _clean(_value(player_state, "life_vision", ""))
        if life_vision:
            evidence._add_authoritative(
                EvidenceRecord(
                    evidence_id="initial:life_vision",
                    kind="initial_premise",
                    subject="玩家初始人生设定",
                    fact=life_vision,
                    metadata={"authoritative_field": "player_state.life_vision"},
                )
            )

        ledger = _value(player_state, "continuity_ledger", {})
        if not isinstance(ledger, Mapping):
            ledger = {}

        identities = ledger.get("immutable_identities") or {}
        if isinstance(identities, Mapping):
            for name, raw_identity in identities.items():
                if not isinstance(raw_identity, Mapping):
                    continue
                canonical = _clean(raw_identity.get("canonical_name") or name)
                if not canonical:
                    continue
                facts = [
                    *list(raw_identity.get("roles") or []),
                    *list(raw_identity.get("relationships") or []),
                ]
                if raw_identity.get("life_status") == "deceased":
                    facts.append("已去世")
                age = raw_identity.get("age_baseline")
                if age is not None:
                    facts.append(f"初始年龄{age}岁")
                evidence._add(
                    EvidenceRecord(
                        evidence_id=f"identity:{_safe_component(canonical)}",
                        kind="identity",
                        subject=canonical,
                        fact="；".join(_unique(facts)) or "权威角色身份",
                        metadata={
                            "source": copy.deepcopy(raw_identity.get("source") or {})
                        },
                    )
                )
                evidence.known_people.append(canonical)
                evidence.known_people.extend(_unique(raw_identity.get("aliases") or []))

        timeline = ledger.get("timeline") or []
        if isinstance(timeline, Sequence) and not isinstance(timeline, (str, bytes)):
            for raw_event in timeline:
                if (
                    not isinstance(raw_event, Mapping)
                    or raw_event.get("status") != "committed"
                ):
                    continue
                event_id = _clean(raw_event.get("event_id"))
                if not event_id:
                    continue
                fact = _clean(raw_event.get("summary") or raw_event.get("choice"))
                if not fact:
                    fact = "已提交事件"
                evidence._add(
                    EvidenceRecord(
                        evidence_id=f"event:{_safe_component(event_id)}",
                        kind="committed_event",
                        subject=event_id,
                        fact=fact,
                        source_event_id=event_id,
                        effective_week=_int_or_none(raw_event.get("week")),
                        effective_round=_int_or_none(raw_event.get("round")),
                        metadata={
                            "date_info": copy.deepcopy(raw_event.get("date_info") or {})
                        },
                    )
                )

        completed = ledger.get("completed_events") or {}
        if isinstance(completed, Mapping):
            for key, raw_record in completed.items():
                if isinstance(raw_record, Mapping):
                    evidence._add_ledger_record("completed", key, raw_record)

        mutable = ledger.get("mutable_states") or {}
        if isinstance(mutable, Mapping):
            for category in ("health", "relationships", "facts"):
                records = mutable.get(category) or {}
                if not isinstance(records, Mapping):
                    continue
                for key, raw_record in records.items():
                    if not isinstance(raw_record, Mapping):
                        continue
                    record_key = key if category == "facts" else f"{category}:{key}"
                    evidence._add_ledger_record("state", record_key, raw_record)

        evidence.known_people = _unique(evidence.known_people)
        return evidence

    def _add_setting_scalars(self, settings: Mapping[str, Any]) -> None:
        def visit(value: Any, path: List[str]) -> None:
            if len(self.records) >= MAX_EVIDENCE_RECORDS:
                return
            if isinstance(value, Mapping):
                for key, child in value.items():
                    visit(child, path + [_safe_component(key)])
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                for index, child in enumerate(value[:24]):
                    visit(child, path + [str(index)])
            elif value is not None and path:
                text = _clean(value)
                if text:
                    dotted = ".".join(path)
                    self._add(
                        EvidenceRecord(
                            evidence_id=f"setting:{dotted}",
                            kind="character_setting",
                            subject=dotted,
                            fact=text,
                        )
                    )

        visit(settings, [])

    def _add_ledger_record(
        self, prefix: str, key: Any, raw_record: Mapping[str, Any]
    ) -> None:
        subject = _clean(raw_record.get("subject") or key)
        fact = _clean(raw_record.get("fact"))
        source_event_id = _clean(raw_record.get("source_event_id"))
        if not subject or not fact or not source_event_id:
            return
        self._add(
            EvidenceRecord(
                evidence_id=f"{prefix}:{_safe_component(key)}",
                kind=prefix,
                subject=subject,
                fact=fact,
                source_event_id=source_event_id,
                effective_week=_int_or_none(raw_record.get("effective_week")),
                effective_round=_int_or_none(raw_record.get("effective_round")),
                metadata={"category": _clean(raw_record.get("category"))},
            )
        )

    def _add(self, record: EvidenceRecord) -> None:
        if contains_precise_financial_fact(
            record.subject,
            record.fact,
            record.metadata.get("category", ""),
        ):
            return
        if len(self.records) < MAX_EVIDENCE_RECORDS:
            self.records[record.evidence_id] = record

    def _add_authoritative(self, record: EvidenceRecord) -> None:
        """Keep numeric authorities even when verbose settings fill the evidence cap."""
        if len(self.records) >= MAX_EVIDENCE_RECORDS:
            removable = next(
                (key for key in reversed(self.records) if key.startswith("setting:")),
                None,
            )
            if removable is None:
                removable = next(reversed(self.records), None)
            if removable is not None:
                del self.records[removable]
        self._add(record)

    def render(self, language: str = "zh") -> str:
        heading = (
            "权威结构化证据"
            if language == "zh"
            else "Authoritative structured evidence"
        )
        lines = [heading]
        for evidence_id, record in self.records.items():
            lines.append(
                f"[{evidence_id}] "
                + json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True)
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class GroundedAssistantAnswer:
    reply: str
    citations: List[str]
    uncertain: bool


class AssistantGroundingService:
    """Generate an answer and accept it only when its evidence validates."""

    def __init__(self, ai_generator: Any, *, max_attempts: int = MAX_ATTEMPTS):
        self.ai_generator = ai_generator
        self.max_attempts = max(1, int(max_attempts))

    def answer(
        self, message: str, player_state: Any, *, language: str = "zh"
    ) -> GroundedAssistantAnswer:
        evidence = AssistantEvidence.from_player_state(player_state)
        unknown = _unknown_queried_person(message, evidence.known_people)
        if unknown:
            if language == "zh":
                reply = f"当前权威记录中没有找到“{unknown}”，我无法把这个人物当作已发生事实。"
            else:
                reply = (
                    f'I could not find "{unknown}" in the authoritative game records.'
                )
            return GroundedAssistantAnswer(reply=reply, citations=[], uncertain=True)

        validation_feedback = ""
        for _attempt in range(self.max_attempts):
            prompt = message
            if validation_feedback:
                prompt += f"\n\nPrevious answer rejected: {validation_feedback}"
            payload = self.ai_generator.generate_completion_json(
                prompt=prompt,
                system_prompt=self._system_prompt(evidence, language),
                temperature=0.1,
                max_tokens=1200,
            )
            answer, validation_feedback = self._validate_payload(
                payload, evidence, language
            )
            if answer is not None:
                return answer

        return self._fallback(language)

    def _system_prompt(self, evidence: AssistantEvidence, language: str) -> str:
        evidence_text = evidence.render(language)
        if language == "zh":
            return f"""你是只读的游戏事实助手。只能依据下面带 ID 的权威结构化证据回答。
禁止把故事草稿、猜测、未来计划或常识补全成已经发生的事实。
证据不足时必须明确说无法确认。不要修改或建议修改游戏状态。
只返回 JSON 对象：{{"reply":"给玩家的简洁回答","citations":["证据ID"],"uncertain":false}}。
每个具体人物、事件、日期和数字都必须由 citations 中的记录直接支持；不确定回答使用空 citations 和 uncertain=true。

{evidence_text}"""
        return f"""You are a read-only game facts assistant. Use only the authoritative,
ID-addressed structured evidence below. Never turn drafts, guesses, future plans,
or general knowledge into events that already happened. If evidence is insufficient,
say so explicitly. Return only JSON with reply, citations, and uncertain. Every
specific person, event, date, and number must be directly supported by cited records.

{evidence_text}"""

    def _validate_payload(
        self,
        payload: Any,
        evidence: AssistantEvidence,
        language: str,
    ) -> tuple[Optional[GroundedAssistantAnswer], str]:
        if not isinstance(payload, Mapping):
            return None, "response was not a JSON object"
        reply = _clean(payload.get("reply"))
        raw_citations = payload.get("citations")
        uncertain = payload.get("uncertain") is True
        if not reply:
            return None, "reply was empty"
        if uncertain:
            return (
                GroundedAssistantAnswer(reply=reply, citations=[], uncertain=True),
                "",
            )
        if not isinstance(raw_citations, list) or not raw_citations:
            return None, "factual answer had no citations"
        citations = [_clean(value) for value in raw_citations if _clean(value)]
        missing = [value for value in citations if value not in evidence.records]
        if missing:
            return None, f"unknown evidence IDs: {', '.join(missing)}"
        cited_text = "\n".join(
            json.dumps(
                evidence.records[value].to_dict(), ensure_ascii=False, sort_keys=True
            )
            for value in citations
        )
        unsupported_tokens = [
            token for token in _CONCRETE_TOKEN.findall(reply) if token not in cited_text
        ]
        if unsupported_tokens:
            return None, f"unsupported concrete values: {', '.join(unsupported_tokens)}"
        unknown_people = _unknown_people_in_reply(reply, evidence.known_people)
        if unknown_people:
            return None, f"unsupported people: {', '.join(unknown_people)}"
        if not _has_lexical_support(reply, cited_text):
            return None, "reply did not overlap the cited fact"
        return (
            GroundedAssistantAnswer(
                reply=reply,
                citations=list(dict.fromkeys(citations)),
                uncertain=False,
            ),
            "",
        )

    @staticmethod
    def _fallback(language: str) -> GroundedAssistantAnswer:
        if language == "zh":
            reply = "我无法确认；当前权威记录中没有足够证据支持这个回答。"
        else:
            reply = "I cannot confirm that from the current authoritative game records."
        return GroundedAssistantAnswer(reply=reply, citations=[], uncertain=True)


def _unknown_queried_person(message: str, known_people: Iterable[str]) -> str:
    known = set(known_people)
    for pattern in _ZH_QUERY_PATTERNS:
        match = pattern.search(message)
        if match:
            candidate = match.group(1).strip()
            if candidate not in known and candidate not in _GENERIC_PERSON_TERMS:
                return candidate
    match = _EN_QUERY_PATTERN.search(message)
    if match:
        candidate = match.group(1).strip()
        if candidate.casefold() not in {name.casefold() for name in known}:
            return candidate
    return ""


def _unknown_people_in_reply(reply: str, known_people: Iterable[str]) -> List[str]:
    known = set(known_people)
    candidates: List[str] = []
    pattern = re.compile(
        r"([\u4e00-\u9fff]{2,3})(?=已经|曾经|目前|现在|是|与|和|住|去|来|说|结婚|去世)"
    )
    for match in pattern.finditer(reply):
        candidate = match.group(1)
        if (
            candidate[0] in _COMMON_SURNAMES
            and candidate not in known
            and candidate not in _GENERIC_PERSON_TERMS
        ):
            candidates.append(candidate)
    return _unique(candidates)


def _has_lexical_support(reply: str, cited_text: str) -> bool:
    normalized_reply = re.sub(r"\s+", "", reply)
    normalized_evidence = re.sub(r"\s+", "", cited_text)
    for start in range(max(0, len(normalized_reply) - 1)):
        fragment = normalized_reply[start : start + 2]
        if (
            len(fragment) == 2
            and all("\u4e00" <= char <= "\u9fff" for char in fragment)
            and fragment not in {"已经", "目前", "现在", "无法", "确认", "记录", "根据"}
            and fragment in normalized_evidence
        ):
            return True
    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", reply.lower())
    return any(word in normalized_evidence.lower() for word in words)


def _unique(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = _clean(value)
        if text and text not in result:
            result.append(text)
    return result


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None
