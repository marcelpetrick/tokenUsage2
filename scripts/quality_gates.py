# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Enforce the pipeline's coverage and mutation-score bars from tool reports.

``coverage`` reads a Cobertura ``coverage.xml`` and requires the line rate and
the branch rate to reach the bar separately; pytest-cov's own gate only checks
their combined total. ``mutation`` reads mutmut's ``mutmut-cicd-stats.json``
and requires killed (or timed-out) mutants to reach the bar among the mutants
that were actually tested.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


class GateError(ValueError):
    """A report is missing, malformed or below its bar."""


def coverage_rates(path: Path) -> tuple[float, float]:
    """(line %, branch %) from a Cobertura report."""
    try:
        root = ET.parse(path).getroot()
        return float(root.attrib["line-rate"]) * 100, float(root.attrib["branch-rate"]) * 100
    except (OSError, ET.ParseError, KeyError, ValueError) as error:
        raise GateError(f"unreadable coverage report {path}: {error}") from error


def mutation_score(path: Path) -> tuple[float, int, int]:
    """(score %, killed, tested) from mutmut's CI/CD statistics."""
    try:
        stats = json.loads(path.read_text(encoding="utf-8"))
        killed = int(stats["killed"]) + int(stats.get("timeout", 0))
        tested = int(stats["total"]) - int(stats.get("skipped", 0))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise GateError(f"unreadable mutation statistics {path}: {error}") from error
    if tested <= 0:
        raise GateError(f"no tested mutants in {path}")
    return killed / tested * 100, killed, tested


def check_coverage(path: Path, bar: float) -> str:
    lines, branches = coverage_rates(path)
    summary = f"lines {lines:.2f}%, branches {branches:.2f}% (bar {bar:g}% each)"
    if lines < bar or branches < bar:
        raise GateError(f"coverage below the bar: {summary}")
    return summary


def check_mutation(path: Path, bar: float) -> str:
    score, killed, tested = mutation_score(path)
    summary = f"mutation score {score:.2f}% ({killed}/{tested} killed, bar {bar:g}%)"
    if score < bar:
        raise GateError(f"mutation score below the bar: {summary}")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=("coverage", "mutation"))
    parser.add_argument("report", type=Path)
    parser.add_argument("--bar", type=float, required=True, help="minimum percentage")
    args = parser.parse_args(argv)
    check = check_coverage if args.kind == "coverage" else check_mutation
    try:
        print(check(args.report, args.bar))
    except GateError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
