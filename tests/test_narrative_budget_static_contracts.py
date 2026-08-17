"""Static gates preventing narrative-budget drift from returning."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from config.prompts.story_prompts import (get_event_generation_prompt,
                                          get_result_generation_prompt,
                                          get_story_only_prompt)
from src.ai.narrative.style_manifest import StyleLoader
import pytest

pytestmark = [pytest.mark.unit]


ROOT = Path(__file__).resolve().parents[1]
CRITICAL_PROVIDER_FILES = (
    "src/ai/story_generator.py",
    "src/ai/story_rewriter.py",
    "src/ai/generator.py",
    "src/ai/consistency_validator.py",
    "src/ai/harness/polish_controller.py",
    "src/game/round/event_generator.py",
)


def _literal_token_call_sites(relative_path: str) -> list[tuple[int, int]]:
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    violations: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if (
                keyword.arg == "max_tokens"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value in {4096, 8192}
            ):
                violations.append((node.lineno, int(keyword.value.value)))
    return violations


def test_critical_narrative_calls_have_no_literal_4096_or_8192() -> None:
    violations = {
        path: _literal_token_call_sites(path)
        for path in CRITICAL_PROVIDER_FILES
        if _literal_token_call_sites(path)
    }

    assert violations == {}


def test_style_manifests_use_relative_density_without_numeric_length_ranges() -> None:
    numeric_length = re.compile(r"\d+\s*(?:-|–|到|至)\s*\d+\s*(?:字|词|words?)", re.I)
    violations: dict[str, str] = {}
    for path in sorted((ROOT / "config/styles").glob("*.style.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = str(payload.get("structure", {}).get("chapter_rules", {}).get("avg_length", ""))
        if numeric_length.search(value):
            violations[path.name] = value

    assert violations == {}


def test_story_only_prompt_uses_enabled_fast_budget_without_conflicting_ranges(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "true")
    prompt = get_story_only_prompt(
        player_state={"week": 1, "current_round": 0, "relationships": {}},
        language="zh",
        character_settings={},
        quality_level="fast",
    )

    assert "400-700字" in prompt
    assert "800-1200字" not in prompt
    assert "1500-2000字" not in prompt


def test_english_prompt_uses_english_fast_band_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "true")
    prompt = get_event_generation_prompt(
        player_state={"week": 1, "current_round": 0, "relationships": {}},
        language="en",
        character_settings={},
        quality_level="fast",
    )

    assert "Story should be 250-450 words" in prompt
    assert "800-1200 words" not in prompt
    assert "1500-2000 words" not in prompt


def test_narrative_prompt_templates_do_not_embed_product_length_ranges() -> None:
    forbidden = re.compile(r"\d+\s*(?:-|–|to)\s*\d+\s*(?:字|chars?|words?)", re.I)
    violations: dict[str, list[str]] = {}
    for relative_path in (
        "config/prompts/story_prompts.py",
        "src/ai/system_prompts.py",
    ):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        active_source = "\n".join(
            line for line in source.splitlines() if "LEGACY_COMPAT" not in line
        )
        matches = [match.group(0) for match in forbidden.finditer(active_source)]
        if matches:
            violations[relative_path] = matches

    assert violations == {}


def test_enabled_continuation_has_no_independent_numeric_paragraph_budget(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "true")
    for language in ("zh", "en"):
        prompt = get_result_generation_prompt("story", "choice", {}, language=language)
        assert "150-300" not in prompt
        assert "500字无换行" not in prompt
        assert "500 words without" not in prompt


def test_disabled_flag_restores_legacy_prompt_and_style_inputs(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "false")
    prompt = get_event_generation_prompt(
        player_state={"week": 1, "current_round": 0, "relationships": {}},
        language="zh",
        character_settings={},
    )
    continuation = get_result_generation_prompt("story", "choice", {}, language="zh")
    style = StyleLoader().get_style("magical_realism")

    assert "每段控制在200-400字" in prompt
    assert '"event_description": "对情况的生动描述（1500-2000字' in prompt
    assert "每段控制在150-300字" in continuation
    assert style is not None
    assert style.structure.chapter_rules.avg_length.startswith("每章1800-3000字")
