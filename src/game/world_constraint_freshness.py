"""Build a safe hard-validation view when legacy world projection is stale."""

import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from src.game.world_projection_coverage import detect_world_change_signals


_WORLD_PATCH_FIELDS = (
    "fact_updates",
    "habit_updates",
    "location_updates",
    "career_updates",
    "commitment_updates",
    "causal_updates",
    "foreshadowing_seeds",
)


@dataclass(frozen=True)
class WorldConstraintFreshness:
    stale_from_day_index: Optional[int]
    reason: Optional[str]

    @property
    def world_derivations_are_fresh(self) -> bool:
        return self.stale_from_day_index is None


@dataclass(frozen=True)
class ValidationWorldModelView:
    world_model: Any
    freshness: WorldConstraintFreshness
    soft_context: str
    hard_established_facts: tuple[Any, ...]


def _day_index(record: Mapping[str, Any]) -> int:
    try:
        return int(record.get("day_index") or 0)
    except (TypeError, ValueError):
        return 0


def _world_patch_is_empty(patch: Any) -> bool:
    if not isinstance(patch, Mapping):
        return True
    return not any(patch.get(field) for field in _WORLD_PATCH_FIELDS)


def derive_legacy_freshness(
    day_history: Sequence[Any],
    tracked_state: Any = None,
) -> WorldConstraintFreshness:
    """Find the first day whose derived world state cannot be trusted as current."""

    records = sorted(
        (record for record in day_history if isinstance(record, Mapping)),
        key=_day_index,
    )
    for record in records:
        status = str(record.get("postprocessing_status") or "")
        if status == "pending":
            return WorldConstraintFreshness(
                _day_index(record),
                "world_projection_pending",
            )
        if status == "failed":
            return WorldConstraintFreshness(
                _day_index(record),
                "world_projection_failed",
            )
        if status != "complete":
            continue
        postprocessing = record.get("postprocessing")
        world_patch = (
            postprocessing.get("world")
            if isinstance(postprocessing, Mapping)
            else None
        )
        signals = detect_world_change_signals(
            str(record.get("event_description") or ""),
            record.get("options") or [record.get("choice") or ""],
            tracked_state,
        )
        if signals.requires_nonempty_patch and _world_patch_is_empty(world_patch):
            return WorldConstraintFreshness(
                _day_index(record),
                "suspicious_empty_world_projection",
            )
    return WorldConstraintFreshness(None, None)


def _record_payload(value: Any) -> Any:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(value, Mapping):
        return dict(value)
    return str(value)


def _canonical_history_context(day_history: Sequence[Any], limit: int = 8) -> str:
    lines = []
    for record in day_history[-limit:]:
        if not isinstance(record, Mapping):
            continue
        story = str(record.get("event_description") or "").strip()
        choice = str(record.get("choice") or "").strip()
        if story:
            lines.append(f"第{_day_index(record) + 1}天已接受故事：{story}")
        if choice:
            lines.append(f"玩家已接受选择：{choice}")
    return "\n".join(lines)


def build_validation_world_model(player_state: Any) -> ValidationWorldModelView:
    """Return hard constraints plus canonical history and downgraded soft hints."""

    from src.game.world_model import WorldModel

    world_model = WorldModel.from_player_state(player_state)
    day_history = getattr(player_state, "day_history", None) or []
    tracked_state = getattr(player_state, "world_model_data", None) or {}
    freshness = derive_legacy_freshness(day_history, tracked_state)
    established_facts = getattr(player_state, "established_facts", None) or []
    hard_established_facts = list(established_facts)
    soft_sections = []
    canonical_context = _canonical_history_context(day_history)
    if canonical_context:
        soft_sections.append(
            "【已接受故事与选择（事实依据）】\n" + canonical_context
        )

    if not freshness.world_derivations_are_fresh:
        stale_fact_categories = {
            "location",
            "commitment",
            "causal",
            "cause",
            "consequence",
        }
        downgraded_legacy_facts = [
            fact
            for fact in established_facts
            if isinstance(fact, Mapping)
            and str(fact.get("category") or "").lower()
            in stale_fact_categories
        ]
        hard_established_facts = [
            fact for fact in established_facts if fact not in downgraded_legacy_facts
        ]
        removed = {
            "character_locations": {
                name: _record_payload(value)
                for name, value in world_model.character_locations.items()
            },
            "active_commitments": [
                _record_payload(value) for value in world_model.active_commitments
            ],
            "causal_chains": [
                _record_payload(value) for value in world_model.causal_chains
            ],
            "legacy_established_facts": downgraded_legacy_facts,
        }
        world_model.character_locations = {}
        world_model.active_commitments = []
        world_model.causal_chains = []
        soft_sections.append(
            "【陈旧世界投影（仅供提示，不得据此拒绝候选故事）】\n"
            + json.dumps(removed, ensure_ascii=False, sort_keys=True)
        )

    world_model.hard_established_facts = tuple(hard_established_facts)
    world_model.soft_context = "\n\n".join(soft_sections)
    world_model.constraint_freshness = freshness

    return ValidationWorldModelView(
        world_model=world_model,
        freshness=freshness,
        soft_context=world_model.soft_context,
        hard_established_facts=tuple(hard_established_facts),
    )
