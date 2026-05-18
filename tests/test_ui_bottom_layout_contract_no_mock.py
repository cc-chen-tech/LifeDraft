"""No-mock contracts for the bottom-bar redesign and top music player."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHAT_BAR = ROOT / "frontend" / "src" / "components" / "game" / "ChatBar.tsx"
PLAY_PAGE = ROOT / "frontend" / "src" / "app" / "play" / "page.tsx"
MUSIC_PLAYER = ROOT / "frontend" / "src" / "components" / "game" / "GlobalMusicPlayer.tsx"
REWRITE_E2E = ROOT / "frontend" / "e2e" / "rewrite-button-discoverable.spec.ts"
PLAYLIST_E2E = ROOT / "frontend" / "e2e" / "music-playlist-persistence.spec.ts"


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


def test_global_music_player_mobile_top_desktop_bottom_contract() -> None:
    source = MUSIC_PLAYER.read_text(encoding="utf-8")

    assert 'data-testid="global-music-player"' in source
    assert 'data-testid="global-music-mini-bar"' in source
    assert "top-16" in source
    assert "safe-area-pt" in source
    assert "md:bottom-4" not in source
    assert "bottom-0 left-0 right-0" not in source


def test_e2e_specs_track_new_bottom_and_music_contracts() -> None:
    rewrite_e2e = REWRITE_E2E.read_text(encoding="utf-8")
    playlist_e2e = PLAYLIST_E2E.read_text(encoding="utf-8")

    assert "collapsed chat bar exposes rewrite/regenerate/summary actions" in rewrite_e2e
    assert "inline rewrite sheet" in rewrite_e2e
    assert 'data-testid="global-music-mini-bar"' in playlist_e2e
    assert ".bottom-0" not in playlist_e2e
