# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("history_chart", ROOT / "scripts/history_chart.py")
assert _spec is not None
assert _spec.loader is not None
history = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = history
_spec.loader.exec_module(history)


@pytest.mark.parametrize(
    ("path", "area"),
    [
        ("src/tokenusage2/aggregate.py", "core"),
        ("src/tokenusage2/render.py", "ui"),
        ("tests/test_render.py", "tests"),
        ("scripts/profile_app.py", "tooling"),
        (".github/workflows/release.yml", "tooling"),
        ("README.md", "docs"),
        ("docs/history/loc-history.svg", None),
        ("media/tour.gif", None),
    ],
)
def test_files_are_assigned_to_stable_areas(path: str, area: str | None) -> None:
    assert history.classify(path) == area


def test_line_count_ignores_blank_and_source_comments_but_keeps_markdown_headings() -> None:
    assert history.count_lines("thing.py", b"# comment\n\nvalue = 1\n  # another\n") == 1
    assert history.count_lines("README.md", b"# Heading\n\ntext\n<!-- comment -->\n") == 3


def point(version: str, values: tuple[int, int, int, int, int], commit: str = "a") -> object:
    lines = {area.key: value for area, value in zip(history.AREAS, values, strict=True)}
    files = {area.key: 1 for area in history.AREAS}
    return history.Point(commit * 40, "2026-10-07", "subject", version, lines, files)


def test_svg_is_deterministic_valid_and_describes_both_axes() -> None:
    points = [point("0.1.0", (10, 5, 8, 3, 2)), point("0.2.0", (20, 8, 18, 6, 4))]
    first = history.render_svg(points, [(0, "v0.1.0")])
    assert history.render_svg(points, [(0, "v0.1.0")]) == first
    ET.fromstring(first)
    assert "Lines of code per area" in first
    assert "test / product-code ratio" in first
    assert "release v0.1.0" in first
    assert "v0.2.0" in first


def test_a_tag_on_head_does_not_change_the_stable_current_marker(monkeypatch) -> None:
    points = [point("0.1.0", (1, 1, 1, 1, 1)), point("0.2.0", (2, 2, 2, 2, 2), "b")]

    def git(*args: str, root: Path) -> bytes:
        if args[0] == "tag":
            return b"v0.1.0\nv0.2.0\n"
        return (points[0].commit if args[-1] == "v0.1.0" else points[1].commit).encode()

    monkeypatch.setattr(history, "_git", git)
    assert history.release_positions(points) == [(0, "v0.1.0")]


def test_current_table_adds_up_and_reports_the_test_ratio() -> None:
    text = history.render_current(point("0.2.0", (20, 10, 30, 5, 5)))
    assert "**70**" in text
    assert "**1.00x**" in text
    assert "`terminal UI`" in text
