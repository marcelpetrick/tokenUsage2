# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import re
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = tuple(
    sorted((*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md"), *(ROOT / "media").rglob("*.md")))
)
LINK = re.compile(r"\]\(([^)]+)\)")


def _body(path: Path) -> list[str]:
    """Return Markdown outside fenced code blocks."""
    outside, fenced = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            outside.append(line)
    assert not fenced, f"unclosed code fence in {path.relative_to(ROOT)}"
    return outside


def test_every_markdown_document_has_a_valid_heading_hierarchy() -> None:
    for path in MARKDOWN:
        levels = [
            len(match.group(1)) for line in _body(path) if (match := re.match(r"^(#+) ", line))
        ]
        assert levels, f"missing heading in {path.relative_to(ROOT)}"
        assert levels[0] == 1, f"missing top-level heading in {path.relative_to(ROOT)}"
        assert all(current <= previous + 1 for previous, current in pairwise(levels)), (
            f"skipped heading level in {path.relative_to(ROOT)}: {levels}"
        )


def test_every_local_markdown_link_resolves() -> None:
    for path in MARKDOWN:
        for target in LINK.findall("\n".join(_body(path))):
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative = target.split("#", 1)[0]
            assert (path.parent / relative).exists(), (
                f"missing link target {target!r} in {path.relative_to(ROOT)}"
            )


def test_markdown_has_no_trailing_whitespace() -> None:
    for path in MARKDOWN:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        trailing = [
            number for number, line in enumerate(lines, 1) if line.rstrip("\r\n") != line.rstrip()
        ]
        assert not trailing, f"trailing whitespace in {path.relative_to(ROOT)}: {trailing}"
