#!/usr/bin/env python3
"""Minimal wiki integrity checks for CI.

Checks:
1. docs/wiki/README.md exists.
2. Required wiki pages exist.
3. README links in docs/wiki/README.md point to existing files.
4. ADR example file exists.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = ROOT / "docs" / "wiki"
WIKI_INDEX = WIKI_DIR / "README.md"
ADR_EXAMPLE = WIKI_DIR / "adr" / "ADR-20260419-sse-over-websocket.md"

REQUIRED_PAGES = [
    "01-quick-start.md",
    "02-system-architecture.md",
    "03-api-and-session.md",
    "04-development-and-testing.md",
    "05-upgrade-and-feature-design.md",
    "06-api-call-matrix.md",
    "07-state-and-data-ownership.md",
    "08-troubleshooting.md",
    "09-feature-playbooks.md",
    "10-release-and-change-checklist.md",
    "11-module-index.md",
    "12-glossary.md",
    "13-documentation-governance.md",
    "14-pr-template.md",
    "15-adr-template.md",
    "16-incident-retro-template.md",
    "17-role-based-reading-paths.md",
    "18-wiki-changelog.md",
]


def fail(msg: str) -> None:
    print(f"[wiki-check] ERROR: {msg}")
    sys.exit(1)


def main() -> int:
    if not WIKI_INDEX.exists():
        fail("docs/wiki/README.md not found")

    for rel in REQUIRED_PAGES:
        p = WIKI_DIR / rel
        if not p.exists():
            fail(f"required wiki page missing: {p.relative_to(ROOT)}")

    if not ADR_EXAMPLE.exists():
        fail(f"ADR example missing: {ADR_EXAMPLE.relative_to(ROOT)}")

    content = WIKI_INDEX.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\((\./[^)]+)\)", content)
    if not links:
        fail("no local links found in docs/wiki/README.md")

    for link in links:
        rel = link[2:] if link.startswith("./") else link
        target = WIKI_DIR / rel
        if not target.exists():
            fail(f"broken wiki index link: {link} -> {target.relative_to(ROOT)}")

    print("[wiki-check] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
