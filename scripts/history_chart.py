# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Generate the repository's lines-of-code history chart from Git objects.

The working tree is never checked out or modified while measuring. Generated
history files are excluded from the count, which makes ``generate, amend,
check`` deterministic for the commit that introduces a documentation change.
"""

from __future__ import annotations

import argparse
import html
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = (
    Path("docs/history/loc-history.svg"),
    Path("docs/history/loc-current.md"),
)
EXCLUDED = {path.as_posix() for path in OUTPUTS}
TEXT_SUFFIXES = {".md", ".py", ".rst", ".sh", ".toml", ".txt", ".yaml", ".yml"}
UI_FILES = {"cli.py", "render.py", "tui.py"}


@dataclass(frozen=True, slots=True)
class Area:
    key: str
    label: str
    colour: str


AREAS = (
    Area("core", "core", "#1f6feb"),
    Area("ui", "terminal UI", "#8250df"),
    Area("tests", "tests", "#2da44e"),
    Area("tooling", "tooling", "#cf222e"),
    Area("docs", "documentation", "#6e7781"),
)


@dataclass(frozen=True, slots=True)
class Point:
    commit: str
    date: str
    subject: str
    version: str | None
    lines: dict[str, int]
    files: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.lines.values())

    @property
    def test_ratio(self) -> float:
        product = self.lines["core"] + self.lines["ui"]
        return self.lines["tests"] / product if product else 0.0


def _git(*args: str, root: Path = ROOT) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout


def classify(path: str) -> str | None:
    """Map one tracked text file to the chart area it contributes to."""
    if path in EXCLUDED:
        return None
    item = Path(path)
    if item.suffix not in TEXT_SUFFIXES and path != "localPipeline.sh":
        return None
    if path.startswith("src/tokenusage2/") and item.suffix == ".py":
        return "ui" if item.name in UI_FILES else "core"
    if path.startswith("tests/") and item.suffix == ".py":
        return "tests"
    if (
        path.startswith("scripts/")
        or path.startswith(".github/workflows/")
        or path in {"localPipeline.sh", "pyproject.toml"}
    ):
        return "tooling"
    if (
        path.startswith("docs/")
        or path.startswith("media/")
        or path in {"README.md", "PLAN.md", "CHANGELOG.md", "review.md"}
    ):
        return "docs"
    return None


def count_lines(path: str, content: bytes) -> int:
    """Count non-blank, non-comment-only lines (all non-blank Markdown lines)."""
    markdown = Path(path).suffix in {".md", ".rst"}
    count = 0
    for raw in content.decode("utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line and (markdown or not line.startswith("#")):
            count += 1
    return count


def _tree(commit: str, root: Path) -> list[tuple[str, str]]:
    records = _git("ls-tree", "-r", "-z", commit, root=root).split(b"\0")
    found = []
    for record in records:
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        found.append((metadata.split()[2].decode(), raw_path.decode("utf-8", errors="replace")))
    return found


def measure_history(root: Path = ROOT) -> list[Point]:
    """Measure every first-parent commit reachable from HEAD, oldest first."""
    commits = _git("rev-list", "--first-parent", "--reverse", "HEAD", root=root).decode().split()
    blob_cache: dict[tuple[str, bool], int] = {}
    points = []
    version_pattern = re.compile(rb'__version__\s*=\s*["\']([^"\']+)["\']')
    for commit in commits:
        fields = _git("show", "-s", "--format=%aI%x00%s", commit, root=root).decode().split("\0")
        date, subject = fields[0][:10], fields[1].rstrip("\n")
        lines = {area.key: 0 for area in AREAS}
        files = {area.key: 0 for area in AREAS}
        version = None
        for blob, path in _tree(commit, root):
            area = classify(path)
            if area is None:
                continue
            content = _git("cat-file", "blob", blob, root=root)
            key = (blob, Path(path).suffix in {".md", ".rst"})
            measured = blob_cache.get(key)
            if measured is None:
                measured = blob_cache[key] = count_lines(path, content)
            lines[area] += measured
            files[area] += 1
            if path == "src/tokenusage2/version.py":
                match = version_pattern.search(content)
                version = match.group(1).decode() if match else None
        points.append(Point(commit, date, subject, version, lines, files))
    return points


def release_positions(points: list[Point], root: Path = ROOT) -> list[tuple[int, str]]:
    """Return earlier release tags; HEAD stays the stable blue current marker.

    A release tag is created after this file passes CI. Ignoring a tag on HEAD
    keeps regeneration identical immediately before and after that operation.
    On the next commit the same tag naturally becomes an earlier red marker.
    """
    positions = {point.commit: index for index, point in enumerate(points)}
    tags = _git("tag", "--list", "v*", "--sort=version:refname", root=root).decode().split()
    found = []
    for tag in tags:
        commit = _git("rev-list", "-n", "1", tag, root=root).decode().strip()
        if commit in positions and positions[commit] != len(points) - 1:
            found.append((positions[commit], tag))
    return found


def _nice_ceiling(value: int) -> int:
    if value <= 10:
        return 10
    magnitude = 10 ** math.floor(math.log10(value))
    for multiple in (1, 2, 5, 10):
        ceiling = multiple * magnitude
        if ceiling >= value:
            return ceiling
    raise AssertionError("unreachable")


def _coordinates(
    values: list[float],
    maximum: float,
    left: float,
    top: float,
    width: float,
    height: float,
) -> list[tuple[float, float]]:
    count = max(1, len(values) - 1)
    return [
        (left + index / count * width, top + height - value / maximum * height)
        for index, value in enumerate(values)
    ]


def _points(values: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in values)


def render_svg(points: list[Point], releases: list[tuple[int, str]]) -> str:
    """Render a deterministic, dependency-free stacked-area SVG."""
    if not points:
        raise ValueError("history has no commits")
    left, top, plot_width, plot_height = 72.0, 58.0, 828.0, 330.0
    bottom = top + plot_height
    line_max = _nice_ceiling(max(point.total for point in points))
    ratio_max = max(1.0, math.ceil(max(point.test_ratio for point in points) * 2) / 2)
    totals = [0.0] * len(points)
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" '
        'viewBox="0 0 960 540" role="img" font-family="Helvetica, Arial, sans-serif" '
        'font-size="12">',
        "<title>Lines of code per area across the tokenUsage2 project history</title>",
        (
            f"<desc>Stacked area chart of non-blank, non-comment lines over {len(points)} "
            "first-parent commits, with the test-to-product-code ratio on the right axis.</desc>"
        ),
        '<rect x="0.5" y="0.5" width="959" height="539" rx="8" fill="#ffffff" stroke="#d0d7de"/>',
        (
            '<text x="72" y="30" font-size="16" font-weight="bold" fill="#24292f">'
            "Lines of code per area</text>"
        ),
        (
            f'<text x="900" y="30" text-anchor="end" fill="#57606a">{len(points)} commits, '
            f"v{html.escape(points[-1].version or 'unknown')}, "
            f"{points[-1].total:,} lines now</text>"
        ),
    ]
    for step in range(5):
        value = line_max * step / 4
        y = bottom - plot_height * step / 4
        pieces.extend(
            (
                f'<line x1="{left:g}" y1="{y:.1f}" x2="{left + plot_width:g}" '
                f'y2="{y:.1f}" stroke="#eaeef2"/>',
                f'<text x="64" y="{y + 4:.1f}" text-anchor="end" '
                f'fill="#57606a">{value:,.0f}</text>',
            )
        )
    pieces.append(
        f'<text x="16" y="{top + plot_height / 2:.1f}" text-anchor="middle" fill="#57606a" '
        f'transform="rotate(-90 16 {top + plot_height / 2:.1f})">lines of code</text>'
    )
    for area in AREAS:
        lower = totals[:]
        totals = [
            total + point.lines[area.key] for total, point in zip(totals, points, strict=True)
        ]
        upper_xy = _coordinates(totals, line_max, left, top, plot_width, plot_height)
        lower_xy = list(reversed(_coordinates(lower, line_max, left, top, plot_width, plot_height)))
        pieces.append(
            f'<polygon points="{_points(upper_xy + lower_xy)}" fill="{area.colour}" '
            f'fill-opacity="0.9" stroke="#ffffff" stroke-width="0.6">'
            f"<title>{area.label}</title></polygon>"
        )
    count = max(1, len(points) - 1)
    release_indexes = {index for index, _ in releases}
    labelled_minors: set[str] = set()
    for release_index, (index, tag) in enumerate(releases):
        x = left + index / count * plot_width
        pieces.append(
            f'<line x1="{x:.1f}" y1="50" x2="{x:.1f}" y2="{bottom:g}" stroke="#cf222e" '
            f'stroke-width="0.8" stroke-opacity="0.65" stroke-dasharray="3 3">'
            f"<title>release {tag}</title></line>"
        )
        parts = tag.removeprefix("v").split(".")
        minor = ".".join(parts[:2])
        label = minor not in labelled_minors or release_index == len(releases) - 1
        labelled_minors.add(minor)
        if label:
            pieces.append(
                f'<text x="{x:.1f}" y="47" text-anchor="middle" font-size="11" '
                f'font-weight="bold" fill="#cf222e">{html.escape(tag)}</text>'
            )
    latest_x = left + plot_width
    latest_version = f"v{points[-1].version}" if points[-1].version else points[-1].date
    if len(points) - 1 not in release_indexes:
        pieces.extend(
            (
                f'<line x1="{latest_x:g}" y1="50" x2="{latest_x:g}" '
                f'y2="{bottom:g}" stroke="#0969da" '
                'stroke-width="1" stroke-dasharray="2 2"><title>current version</title></line>',
                f'<text x="{latest_x:g}" y="47" text-anchor="end" '
                'font-size="11" font-weight="bold" '
                f'fill="#0969da">{html.escape(latest_version)}</text>',
            )
        )
    ratios = [point.test_ratio for point in points]
    ratio_xy = _coordinates(ratios, ratio_max, left, top, plot_width, plot_height)
    pieces.append(
        f'<polyline points="{_points(ratio_xy)}" fill="none" stroke="#24292f" stroke-width="1.6">'
        "<title>test-to-product-code ratio</title></polyline>"
    )
    for step in range(3):
        value = ratio_max * step / 2
        y = bottom - plot_height * step / 2
        pieces.append(f'<text x="908" y="{y + 4:.1f}" fill="#57606a">{value:.1f}x</text>')
    tick_count = min(8, len(points))
    indexes = sorted(
        {
            round(position * (len(points) - 1) / max(1, tick_count - 1))
            for position in range(tick_count)
        }
    )
    for index in indexes:
        x = left + index / count * plot_width
        label = f"v{points[index].version}" if points[index].version else points[index].date
        pieces.append(
            f'<text x="{x:.1f}" y="405" text-anchor="end" fill="#57606a" '
            f'transform="rotate(-35 {x:.1f} 405)">{html.escape(label)}</text>'
        )
    for position, area in enumerate(AREAS):
        x = 72 + (position % 3) * 245
        y = 458 + (position // 3) * 25
        pieces.extend(
            (
                f'<rect x="{x}" y="{y - 11}" width="12" height="12" rx="2" fill="{area.colour}"/>',
                f'<text x="{x + 18}" y="{y}">{area.label}</text>',
            )
        )
    pieces.extend(
        (
            '<line x1="562" y1="491" x2="592" y2="491" stroke="#24292f" stroke-width="1.6"/>',
            '<text x="600" y="495">test / product-code ratio (right axis)</text>',
            '<line x1="562" y1="516" x2="592" y2="516" stroke="#cf222e" stroke-dasharray="3 3"/>',
            '<text x="600" y="520">release tag; blue marker is the current version</text>',
            "</svg>",
        )
    )
    return "\n".join(pieces) + "\n"


def render_current(point: Point) -> str:
    rows = []
    for area in AREAS:
        lines = point.lines[area.key]
        share = lines / point.total * 100 if point.total else 0
        rows.append(f"| `{area.label}` | {point.files[area.key]:,} | {lines:,} | {share:.1f}% |")
    version = f"v{point.version}" if point.version else "an unversioned commit"
    return "\n".join(
        (
            "<!--",
            "SPDX-FileCopyrightText: 2026 Marcel Petrick",
            "",
            "SPDX-License-Identifier: GPL-3.0-or-later",
            "-->",
            "",
            "# Current lines of code",
            "",
            "Generated by `scripts/history_chart.py`; do not edit. Counts exclude blank and",
            "comment-only lines (Markdown counts every non-blank line) and the generated",
            "history files.",
            "",
            f"Current version: **{version}** · {point.total:,} lines across "
            f"{sum(point.files.values()):,} files.",
            "",
            "| Area | Files | Lines | Share |",
            "| --- | ---: | ---: | ---: |",
            *rows,
            f"| **total** | **{sum(point.files.values()):,}** | **{point.total:,}** | **100.0%** |",
            "",
            f"Test-to-product-code ratio: **{point.test_ratio:.2f}x**.",
            "",
        )
    )


def generated(root: Path = ROOT) -> dict[Path, str]:
    points = measure_history(root)
    return {
        OUTPUTS[0]: render_svg(points, release_positions(points, root)),
        OUTPUTS[1]: render_current(points[-1]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if committed outputs are stale")
    args = parser.parse_args(argv)
    results = generated()
    stale = []
    for path, content in results.items():
        target = ROOT / path
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != content:
                stale.append(path.as_posix())
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    if stale:
        print("history chart is stale: " + ", ".join(stale), file=sys.stderr)
        print("run: .venv/bin/python scripts/history_chart.py", file=sys.stderr)
        return 1
    action = "verified" if args.check else "wrote"
    print(f"{action} {', '.join(path.as_posix() for path in OUTPUTS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
