"""Append-only story history for cache-friendly DeepSeek prompts.

The raw round history remains the source of truth.  This module only renders
that history into a stable prompt prefix and stores compact, derived snapshots
when the prefix would become too large.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol


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
        path = tokenizer_path or os.getenv("DEEPSEEK_TOKENIZER_PATH") or str(
            Path(__file__).with_name("deepseek_tokenizer") / "tokenizer.json"
        )
        try:
            from tokenizers import Tokenizer  # type: ignore[import-not-found]

            self._tokenizer = Tokenizer.from_file(path)
            logger.info("Loaded configured official DeepSeek tokenizer")
        except Exception as exc:  # pragma: no cover - depends on deployment artifact
            logger.warning("Could not load DeepSeek tokenizer; using conservative counter: %s", exc)

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


class LongStoryContextBuilder:
    """Build a stable history prefix and compact only its oldest event range."""

    def __init__(
        self,
        token_counter: Optional[TokenCounter] = None,
        settings: Optional[StoryContextSettings] = None,
    ) -> None:
        self._counter = token_counter or DeepSeekTokenCounter()
        self._settings = settings or StoryContextSettings()

    def build(self, player_state: Mapping[str, Any] | Any) -> StoryHistoryContext:
        """Render committed rounds, updating derived snapshots in-place if needed."""
        events = self._canonical_events(self._value(player_state, "round_history", []))
        snapshots = self._snapshots(player_state)
        snapshot_end = self._validated_prefix_snapshot_end(snapshots, events)

        prefix = self._render(events, snapshots, snapshot_end)
        budget = self._settings.history_token_budget
        if self._counter.count(prefix) > budget and events:
            snapshot_end = self._compact_prefix(events, player_state, budget, snapshot_end)
            snapshots = self._snapshots(player_state)
            prefix = self._render(events, snapshots, snapshot_end)

        # A pathological tiny test budget can only fit a header. Production's
        # 800k budget never reaches this branch, but it preserves a hard cap.
        if self._counter.count(prefix) > budget:
            prefix = EVENT_LOG_HEADER

        return StoryHistoryContext(
            history_prefix=prefix,
            input_tokens=self._counter.count(prefix),
            used_snapshot=bool(snapshots),
        )

    def build_for_request(
        self, player_state: Mapping[str, Any] | Any, dynamic_tail: str
    ) -> StoryHistoryContext:
        """Build history against the remaining space in one complete request."""
        remaining = self._settings.input_token_budget - self._counter.count(dynamic_tail)
        if remaining < 1:
            raise ValueError("Dynamic story request exceeds the configured input budget")
        request_settings = StoryContextSettings(
            input_token_budget=remaining,
            snapshot_target_tokens=self._settings.snapshot_target_tokens,
            dynamic_token_reserve=0,
        )
        return LongStoryContextBuilder(self._counter, request_settings).build(player_state)

    @staticmethod
    def _value(player_state: Mapping[str, Any] | Any, field: str, default: Any) -> Any:
        if isinstance(player_state, Mapping):
            return player_state.get(field, default)
        return getattr(player_state, field, default)

    def _snapshots(self, player_state: Mapping[str, Any] | Any) -> List[Dict[str, Any]]:
        snapshots = self._value(player_state, "long_context_snapshots", None)
        if isinstance(snapshots, list):
            snapshots[:] = [item for item in snapshots if isinstance(item, dict)]
            return snapshots
        if isinstance(player_state, dict):
            player_state["long_context_snapshots"] = []
            return player_state["long_context_snapshots"]
        setattr(player_state, "long_context_snapshots", [])
        return getattr(player_state, "long_context_snapshots")

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
                    "date": str((item.get("date_info") or {}).get("date_string") or "").strip(),
                }
            )

        result: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for event in sorted(candidates, key=lambda item: (item["week"], item["round"])):
            if event["event_id"] not in seen:
                result.append(event)
                seen.add(event["event_id"])
        return result

    @staticmethod
    def _event_block(event: Mapping[str, Any]) -> str:
        date = f" date={event['date']}" if event.get("date") else ""
        continuation = f"\n[CONTINUATION] {event['continuation']}" if event.get("continuation") else ""
        choice = f"\n[CHOICE] {event['choice']}" if event.get("choice") else ""
        return f"[EVENT {event['event_id']}{date}]\n{event['story']}{choice}{continuation}\n"

    @staticmethod
    def _digest(events: List[Dict[str, Any]]) -> str:
        raw = "".join(LongStoryContextBuilder._event_block(event) for event in events)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _validated_prefix_snapshot_end(
        self, snapshots: List[Dict[str, Any]], events: List[Dict[str, Any]]
    ) -> int:
        if not snapshots or not events:
            return -1
        snapshot = snapshots[0]
        end_id = snapshot.get("end_event_id")
        if not isinstance(end_id, str):
            return -1
        end_index = next((i for i, event in enumerate(events) if event["event_id"] == end_id), -1)
        if end_index < 0:
            return -1
        if snapshot.get("source_digest") != self._digest(events[: end_index + 1]):
            snapshots.clear()
            return -1
        return end_index

    def _render(self, events: List[Dict[str, Any]], snapshots: List[Dict[str, Any]], snapshot_end: int) -> str:
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
        player_state: Mapping[str, Any] | Any,
        budget: int,
        current_end: int,
    ) -> int:
        snapshots = self._snapshots(player_state)
        selected_end = current_end
        for end in range(max(0, current_end + 1), len(events)):
            snapshot = self._make_snapshot(events[: end + 1], budget)
            candidate = [snapshot]
            rendered = self._render(events, candidate, end)
            if self._counter.count(rendered) <= budget or end == len(events) - 1:
                snapshots[:] = candidate
                return end
            selected_end = end
        return selected_end

    def _make_snapshot(self, events: List[Dict[str, Any]], budget: int) -> Dict[str, Any]:
        start_id = events[0]["event_id"]
        end_id = events[-1]["event_id"]
        wrapper = f"[SNAPSHOT {start_id}..{end_id}]\n\n"
        # The snapshot itself must leave room for the fixed header and any
        # remaining raw events. A deterministic fallback is preferable to
        # blocking story generation on a summarizer call.
        max_tokens = max(1, min(self._settings.snapshot_target_tokens, budget - self._counter.count(EVENT_LOG_HEADER + wrapper)))
        entries = [
            f"{event['event_id']}: {event['story']}" + (f" | choice={event['choice']}" if event["choice"] else "")
            for event in events
        ]
        content = " ".join(entries)
        while self._counter.count(content) > max_tokens and content:
            content = content[:-1]
        return {
            "schema_version": 1,
            "snapshot_id": f"epoch:{start_id}-{end_id}",
            "start_event_id": start_id,
            "end_event_id": end_id,
            "source_digest": self._digest(events),
            "content": content,
            "token_count": self._counter.count(content),
        }
