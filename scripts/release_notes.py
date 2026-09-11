#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Print one version's section of CHANGELOG.md — the notes of its GitHub release.

Usage: scripts/release_notes.py [VERSION]   (default: the version in version.py)
Exits with status 1 when the changelog has no section for the version.
"""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def current_version() -> str:
    return str(runpy.run_path(str(ROOT / "src" / "tokenusage2" / "version.py"))["__version__"])


def section(changelog: str, version: str) -> str | None:
    """The body under ``## <version>``, up to the next ``## `` heading."""
    lines = changelog.splitlines()
    heading = f"## {version}"
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return None
    body = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body).strip() or None


def main(argv: list[str]) -> int:
    version = argv[1] if len(argv) > 1 else current_version()
    notes = section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    if notes is None:
        print(f"CHANGELOG.md has no section for {version}", file=sys.stderr)
        return 1
    print(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
