"""Append-only story history for cache-friendly DeepSeek prompts.

The raw round history remains the source of truth.  This module only renders
that history into a stable prompt prefix and stores compact, derived snapshots
when the prefix would become too large.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Union, cast

from config.feature_flags import get_feature

logger = logging.getLogger(__name__)

EVENT_LOG_HEADER = "EVENT_LOG_V1\n"


def is_deepseek_v4_model(model: object) -> bool:
    """Return whether a model supports the DeepSeek V4 long-context path."""
    return str(model or "").strip().lower().startswith("deepseek-v4-")


def prepend_history_prefix(history_prefix: str, dynamic_prompt: str) -> str:
    """Keep immutable history byte-stable before all changing request data."""
    if not history_prefix:
        return dynamic_prompt
    return f"{history_prefix}\n[CURRENT_REQUEST]\n{dynamic_prompt}"


class TokenCounter(Protocol):
    """Small adapter so tests and deployments can provide an exact tokenizer."""

    def count(self, text: str) -> int:
        raise NotImplementedError


class DeepSeekTokenCounter:
    """Use the official DeepSeek tokenizer when it is configured locally.

    The default artifact is the official DeepSeek offline tokenizer committed
    with this module. An environment override is useful for provider upgrades.
    If loading fails, count every character as one token; this is deliberately
    conservative and cannot under-budget normal text.
    """

    def __init__(self, tokenizer_path: Optional[str] = None) -> None:
        self._tokenizer = None
        path = (
            tokenizer_path
            or os.getenv("DEEPSEEK_TOKENIZER_PATH")
            or str(Path(__file__).with_name("deepseek_tokenizer") / "tokenizer.json")
        )
        try:
            from tokenizers import Tokenizer

            self._tokenizer = Tokenizer.from_file(path)
            logger.info("Loaded configured official DeepSeek tokenizer")
        except Exception as exc:  # pragma: no cover - depends on deployment artifact
            logger.warning(
                "Could not load DeepSeek tokenizer; using conservative counter: %s", exc
            )

    def count(self, text: str) -> int:
        if self._tokenizer is not None:
            return len(self._tokenizer.encode(text).ids)
        return len(text)


@dataclass(frozen=True)
class StoryContextSettings:
    input_token_budget: int = 800_000
    snapshot_target_tokens: int = 12_000
    dynamic_token_reserve: int = 80_000

    @property
    def history_token_budget(self) -> int:
        # Keep a small percentage for state, world model, retries, and output
        # instructions. Tests may set a small budget, so never reserve more
        # than one tenth there.
        reserve = min(self.dynamic_token_reserve, self.input_token_budget // 10)
        return max(1, self.input_token_budget - reserve)


@dataclass(frozen=True)
class StoryHistoryContext:
    history_prefix: str
    input_tokens: int
    used_snapshot: bool
    dynamic_tail: str = ""


class LongContextBudgetError(ValueError):
    """Required request context cannot fit the absolute model input limit."""


@dataclass(frozen=True)
class DynamicContextParts:
    """Request context ordered from non-negotiable to most disposable."""

    current_request: str
    character_authority: str = ""
    ledger_facts: str = ""
    recent_events: Sequence[str] = ()
    old_history: Sequence[str] = ()


class LongStoryContextBuilder:
    """Build a stable history prefix and compact only its oldest event range."""

    def __init__(
        self,
        token_counter: Optional[TokenCounter] = None,
        settings: Optional[StoryContextSettings] = None,
    ) -> None:
        self._counter = token_counter or DeepSeekTokenCounter()
        self._settings = settings or StoryContextSettings()

    def build(self, player_state: Union[Mapping[str, Any], Any]) -> StoryHistoryContext:
        """Render committed rounds, updating derived snapshots in-place if needed."""
        events = self._canonical_events(self._value(player_state, "round_history", []))
        source_events = self._events_with_ledger(player_state, events)
        snapshots = self._snapshots(player_state)
        snapshot_end = self._validated_prefix_snapshot_end(
            snapshots,
            events,
            source_events,
        )

        prefix = self._render(events, snapshots, snapshot_end)
        budget = self._settings.history_token_budget
        if self._counter.count(prefix) > budget and events:
            snapshot_end = self._compact_prefix(
                events, player_state, budget, snapshot_end
            )
            snapshots = self._snapshots(player_state)
            prefix = self._render(events, snapshots, snapshot_end)

        # Never replace truthful raw history with a header-only placeholder.
        if self._counter.count(prefix) > budget:
            logger.warning(
                "Long context remains above budget without lossy truncation: "
                "tokens=%d budget=%d events=%d",
                self._counter.count(prefix),
                budget,
                len(events),
            )

        return StoryHistoryContext(
            history_prefix=prefix,
            input_tokens=self._counter.count(prefix),
            used_snapshot=snapshot_end >= 0,
        )

    def build_for_request(
        self,
        player_state: Union[Mapping[str, Any], Any],
        dynamic_tail: Union[str, DynamicContextParts],
    ) -> StoryHistoryContext:
        """Build history against the remaining space in one complete request."""
        rendered_tail = (
            self.fit_dynamic_context(dynamic_tail)
            if isinstance(dynamic_tail, DynamicContextParts)
            else dynamic_tail
        )
        remaining = self._settings.input_token_budget - self._counter.count(
            rendered_tail
        )
        if remaining < 1:
            raise LongContextBudgetError(
                "Required dynamic context exceeds the configured absolute input budget"
            )
        request_settings = StoryContextSettings(
            input_token_budget=remaining,
            snapshot_target_tokens=self._settings.snapshot_target_tokens,
            dynamic_token_reserve=0,
        )
        context = LongStoryContextBuilder(self._counter, request_settings).build(
            player_state
        )
        return StoryHistoryContext(
            history_prefix=context.history_prefix,
            input_tokens=context.input_tokens,
            used_snapshot=context.used_snapshot,
            dynamic_tail=rendered_tail,
        )

    def fit_dynamic_context(self, parts: DynamicContextParts) -> str:
        """Keep required blocks and admit optional complete units by priority."""

        def block(label: str, value: str) -> str:
            clean = str(value or "").strip()
            return f"[{label}]\n{clean}\n" if clean else ""

        required = "".join(
            (
                block("CURRENT_REQUEST", parts.current_request),
                block("CHARACTER_AUTHORITY", parts.character_authority),
                block("LEDGER_FACTS", parts.ledger_facts),
            )
        )
        absolute = self._settings.input_token_budget
        required_tokens = self._counter.count(required)
        if required_tokens > absolute:
            raise LongContextBudgetError(
                "Required dynamic context exceeds the configured absolute input budget "
                f"({required_tokens}>{absolute})"
            )

        rendered = required
        for label, values in (
            ("RECENT_EVENT", parts.recent_events),
            ("OLD_HISTORY", parts.old_history),
        ):
            for value in values:
                candidate = block(label, str(value))
                if candidate and self._counter.count(rendered + candidate) <= absolute:
                    rendered += candidate
        return rendered

    @staticmethod
    def _value(player_state: Union[Mapping[str, Any], Any], field: str, default: Any) -> Any:
        if isinstance(player_state, Mapping):
            return player_state.get(field, default)
        return getattr(player_state, field, default)

    def _snapshots(self, player_state: Union[Mapping[str, Any], Any]) -> List[Dict[str, Any]]:
        snapshots = self._value(player_state, "long_context_snapshots", None)
        if isinstance(snapshots, list):
            snapshots[:] = [item for item in snapshots if isinstance(item, dict)]
            return snapshots
        if isinstance(player_state, dict):
            player_state["long_context_snapshots"] = []
            return cast(List[Dict[str, Any]], player_state["long_context_snapshots"])
        setattr(player_state, "long_context_snapshots", [])
        return cast(
            List[Dict[str, Any]], getattr(player_state, "long_context_snapshots")
        )

    def _canonical_events(self, history: Any) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        if not isinstance(history, list):
            return candidates
        for item in history:
            if not isinstance(item, dict):
                continue
            story = str(
                item.get("event_description")
                or item.get("story_text")
                or item.get("full_story")
                or ""
            ).strip()
            if not story:
                continue
            week = int(item.get("week", 0) or 0)
            round_number = int(item.get("round", 0) or 0)
            candidates.append(
                {
                    "event_id": f"w{week}-r{round_number}",
                    "week": week,
                    "round": round_number,
                    "story": story,
                    "continuation": str(item.get("story_continuation") or "").strip(),
                    "choice": str(item.get("choice") or "").strip(),
                    "date": str(
                        (item.get("date_info") or {}).get("date_string") or ""
                    ).strip(),
                }
            )

        result: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for event in sorted(candidates, key=lambda item: (item["week"], item["round"])):
            if event["event_id"] not in seen:
                result.append(event)
                seen.add(event["event_id"])
        return result

    def _events_with_ledger(
        self,
        player_state: Union[Mapping[str, Any], Any],
        events: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Enrich only exact source-linked events with authoritative ledger data."""
        if not get_feature("structured_story_memory"):
            return events
        stored = self._value(player_state, "continuity_ledger", {})
        if not isinstance(stored, Mapping):
            return events
        timeline = stored.get("timeline")
        if not isinstance(timeline, list):
            return events
        by_id = {
            str(entry.get("event_id")): entry
            for entry in timeline
            if isinstance(entry, Mapping) and entry.get("event_id")
        }
        enriched: List[Dict[str, Any]] = []
        for event in events:
            item = dict(event)
            ledger = by_id.get(event["event_id"])
            if ledger is not None:
                summary = str(ledger.get("summary") or "").strip()
                choice = str(ledger.get("choice") or "").strip()
                effects = ledger.get("effects")
                if summary:
                    item["summary"] = summary
                if choice:
                    item["choice"] = choice
                if isinstance(effects, Mapping):
                    item["effects"] = dict(effects)
            enriched.append(item)
        return enriched

    @staticmethod
    def _event_block(event: Mapping[str, Any]) -> str:
        date = f" date={event['date']}" if event.get("date") else ""
        continuation = (
            f"\n[CONTINUATION] {event['continuation']}"
            if event.get("continuation")
            else ""
        )
        choice = f"\n[CHOICE] {event['choice']}" if event.get("choice") else ""
        return f"[EVENT {event['event_id']}{date}]\n{event['story']}{choice}{continuation}\n"

    @staticmethod
    def _digest(events: List[Dict[str, Any]]) -> str:
        raw = "".join(LongStoryContextBuilder._event_block(event) for event in events)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _validated_prefix_snapshot_end(
        self,
        snapshots: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        source_events: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        if not snapshots or not events:
            return -1
        snapshot = snapshots[0]
        schema_version = int(snapshot.get("schema_version") or 1)
        end_id = snapshot.get("end_event_id")
        if not isinstance(end_id, str):
            return -1
        end_index = next(
            (i for i, event in enumerate(events) if event["event_id"] == end_id), -1
        )
        if end_index < 0:
            return -1
        covered_events = events[: end_index + 1]
        if snapshot.get("source_digest") != self._digest(covered_events):
            snapshots.clear()
            return -1
        if schema_version < 2:
            logger.info(
                "Long context snapshot scheduled for lazy v2 rebuild: schema=%d covered=%d",
                schema_version,
                len(covered_events),
            )
            return -1
        expected_ids = [event["event_id"] for event in covered_events]
        expected_entries = [
            self._snapshot_entry(event)
            for event in (source_events or events)[: end_index + 1]
        ]
        covered_ids = snapshot.get("covered_event_ids")
        entries = snapshot.get("entries")
        entry_ids = (
            [entry.get("event_id") for entry in entries if isinstance(entry, Mapping)]
            if isinstance(entries, list)
            else []
        )
        expected_content = (
            "".join(self._render_snapshot_entry(entry) for entry in entries)
            if isinstance(entries, list)
            else ""
        )
        if (
            covered_ids != expected_ids
            or entry_ids != expected_ids
            or entries != expected_entries
            or snapshot.get("content") != expected_content
            or snapshot.get("token_count") != self._counter.count(expected_content)
        ):
            snapshots.clear()
            return -1
        return end_index

    def _render(
        self,
        events: List[Dict[str, Any]],
        snapshots: List[Dict[str, Any]],
        snapshot_end: int,
    ) -> str:
        parts = [EVENT_LOG_HEADER]
        if snapshot_end >= 0 and snapshots:
            snapshot = snapshots[0]
            parts.append(
                f"[SNAPSHOT {snapshot['start_event_id']}..{snapshot['end_event_id']}]\n"
                f"{snapshot['content']}\n"
            )
        parts.extend(self._event_block(event) for event in events[snapshot_end + 1 :])
        return "".join(parts)

    def _compact_prefix(
        self,
        events: List[Dict[str, Any]],
        player_state: Union[Mapping[str, Any], Any],
        budget: int,
        current_end: int,
    ) -> int:
        del current_end
        snapshots = self._snapshots(player_state)
        source_events = self._events_with_ledger(player_state, events)
        snapshot = self._make_snapshot(source_events, events, budget)
        if snapshot is None:
            snapshots.clear()
            logger.warning(
                "Long context compaction degraded without snapshot: "
                "reason=no_complete_event_fit"
            )
            return -1
        snapshots[:] = [snapshot]
        covered_count = len(snapshot["covered_event_ids"])
        logger.info(
            "Long context snapshot written: schema=2 covered=%d tokens=%d reason=budget",
            covered_count,
            snapshot["token_count"],
        )
        return covered_count - 1

    @staticmethod
    def _snapshot_entry(event: Mapping[str, Any]) -> Dict[str, Any]:
        effects = event.get("effects")
        return {
            "event_id": str(event["event_id"]),
            "summary": str(event.get("summary") or event.get("story") or "").strip(),
            "choice": str(event.get("choice") or "").strip(),
            "effects": dict(effects) if isinstance(effects, Mapping) else {},
        }

    @staticmethod
    def _render_snapshot_entry(entry: Mapping[str, Any]) -> str:
        def one_line(value: Any) -> str:
            return " ".join(str(value or "").split())

        event_id = one_line(entry["event_id"])
        summary = one_line(entry["summary"])
        choice = one_line(entry.get("choice"))
        effects = entry.get("effects")
        encoded_effects = (
            json.dumps(
                dict(effects),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            if isinstance(effects, Mapping) and effects
            else ""
        )
        return f"{event_id}\t{summary}\t{choice}\t{encoded_effects}\n"

    def _make_snapshot(
        self,
        source_events: List[Dict[str, Any]],
        raw_events: List[Dict[str, Any]],
        budget: int,
    ) -> Optional[Dict[str, Any]]:
        max_snapshot_tokens = max(
            1,
            min(
                self._settings.snapshot_target_tokens,
                budget - self._counter.count(EVENT_LOG_HEADER),
            ),
        )
        entries: List[Dict[str, Any]] = []
        content = ""
        for event in source_events:
            entry = self._snapshot_entry(event)
            rendered_entry = self._render_snapshot_entry(entry)
            candidate_content = content + rendered_entry
            wrapper = (
                f"[SNAPSHOT {source_events[0]['event_id']}..{event['event_id']}]\n\n"
            )
            if self._counter.count(wrapper + candidate_content) > max_snapshot_tokens:
                break
            entries.append(entry)
            content = candidate_content
        if not entries:
            return None

        covered_count = len(entries)
        covered_raw = raw_events[:covered_count]
        covered_ids = [entry["event_id"] for entry in entries]
        start_id = covered_ids[0]
        end_id = covered_ids[-1]
        return {
            "schema_version": 2,
            "snapshot_id": f"epoch:{start_id}-{end_id}",
            "start_event_id": start_id,
            "end_event_id": end_id,
            "covered_event_ids": covered_ids,
            "source_digest": self._digest(covered_raw),
            "content": content,
            "entries": entries,
            "token_count": self._counter.count(content),
        }
