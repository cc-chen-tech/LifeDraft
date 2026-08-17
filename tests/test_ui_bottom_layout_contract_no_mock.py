"""No-mock contracts for the bottom-bar redesign and top music player."""

from __future__ import annotations

from pathlib import Path
import pytest

pytestmark = [pytest.mark.unit]



ROOT = Path(__file__).resolve().parents[1]
CHAT_BAR = ROOT / "frontend" / "src" / "components" / "game" / "ChatBar.tsx"
PLAY_PAGE = ROOT / "frontend" / "src" / "app" / "play" / "page.tsx"
LISTENING_EXPERIENCE = ROOT / "frontend" / "src" / "components" / "game" / "StoryListeningExperience.tsx"
REWRITE_E2E = ROOT / "frontend" / "e2e" / "rewrite-button-discoverable.spec.ts"
DAILY_LISTENING_E2E = ROOT / "frontend" / "e2e" / "daily-timeline.spec.ts"


def test_chatbar_owns_inline_rewrite_sheet_contract() -> None:
    source = CHAT_BAR.read_text(encoding="utf-8")

    assert "onAdjustStory" not in source
    assert "storyText" in source
    assert "onRewriteComplete" in source
    assert "streamRewrite" in source
    assert 'data-testid="inline-rewrite-sheet"' in source
    assert 'data-testid="rewrite-button"' in source


def test_play_page_no_longer_mounts_story_adjuster() -> None:
    source = PLAY_PAGE.read_text(encoding="utf-8")

    assert "StoryAdjuster" not in source
    assert "showAdjuster" not in source
    assert "setShowAdjuster" not in source
    assert "handleAdjustStory" not in source
    assert "storyText={storyText}" in source
    assert "onRewriteComplete" in source


def test_daily_listener_keeps_choices_in_a_sticky_bottom_action_area() -> None:
    source = LISTENING_EXPERIENCE.read_text(encoding="utf-8")

    assert 'data-testid="story-listening-experience"' in source
    assert "sticky bottom-0" in source
    assert "safe-area-inset-bottom" in source
    assert "OptionCards" in source


def test_e2e_specs_track_rewrite_and_daily_listening_contracts() -> None:
    rewrite_e2e = REWRITE_E2E.read_text(encoding="utf-8")
    daily_e2e = DAILY_LISTENING_E2E.read_text(encoding="utf-8")

    assert "collapsed chat bar exposes rewrite/regenerate/summary actions" in rewrite_e2e
    assert "inline rewrite sheet" in rewrite_e2e
    assert "从第 2 段开始朗读" in daily_e2e
    assert "expect(musicCalls).toBe(0)" in daily_e2e
